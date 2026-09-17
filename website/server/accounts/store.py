"""Website profiles and opaque sessions. Never match or link accounts by email."""
import hashlib
import json
import ssl
import time
from contextlib import contextmanager
from pathlib import Path

import pymysql


class AccountUnavailable(Exception):
    pass


class Store:
    def __init__(self, settings):
        self.settings = settings
        self.tls = ssl.create_default_context(cafile=settings["NEKTRON_DB_CA_FILE"])

    @contextmanager
    def connection(self):
        s = self.settings
        connection = pymysql.connect(
            host=s["NEKTRON_DB_HOST"], port=int(s.get("NEKTRON_DB_PORT", 3306)),
            user=s["NEKTRON_DB_USER"], password=s["NEKTRON_DB_PASSWORD"],
            database=s["NEKTRON_DB_NAME"], ssl=self.tls, charset="utf8mb4",
            connect_timeout=5, read_timeout=10, write_timeout=10,
            cursorclass=pymysql.cursors.DictCursor,
            init_command="SET time_zone = '+00:00'",
        )
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def migrate(self):
        with self.connection() as connection, connection.cursor() as cur:
            for statement in Path(__file__).with_name("schema.sql").read_text().split(";"):
                if statement.strip():
                    cur.execute(statement)

    def read_session(self, digest):
        with self.connection() as c, c.cursor() as cur:
            cur.execute("SELECT Data, ExpiresAt FROM WebsiteSession WHERE TokenHash=%s AND ExpiresAt>%s",
                        (digest, int(time.time())))
            row = cur.fetchone()
            return (json.loads(row["Data"]), row["ExpiresAt"]) if row else None

    def save_session(self, digest, data, expires, new):
        with self.connection() as c, c.cursor() as cur:
            if new:
                cur.execute("INSERT INTO WebsiteSession (TokenHash,Data,ExpiresAt) VALUES (%s,%s,%s)",
                            (digest, json.dumps(data), expires))
            else:
                # An in-flight request cannot recreate a session after logout.
                cur.execute("UPDATE WebsiteSession SET Data=%s WHERE TokenHash=%s AND ExpiresAt>%s",
                            (json.dumps(data), digest, int(time.time())))

    def delete_session(self, digest):
        with self.connection() as c, c.cursor() as cur:
            cur.execute("DELETE FROM WebsiteSession WHERE TokenHash=%s", (digest,))

    def allow_request(self, key, limit=20, seconds=600):
        now = int(time.time())
        bucket = hashlib.sha256(f"{key}:{now // seconds}".encode()).hexdigest()
        with self.connection() as c, c.cursor() as cur:
            cur.execute("INSERT INTO WebsiteRateLimit (BucketKey,Attempts,ExpiresAt) VALUES (%s,1,%s) "
                        "ON DUPLICATE KEY UPDATE Attempts=Attempts+1", (bucket, now + seconds * 2))
            cur.execute("SELECT Attempts FROM WebsiteRateLimit WHERE BucketKey=%s", (bucket,))
            attempts = cur.fetchone()["Attempts"]
            cur.execute("DELETE FROM WebsiteRateLimit WHERE ExpiresAt<%s LIMIT 100", (now,))
            cur.execute("DELETE FROM WebsiteSession WHERE ExpiresAt<%s LIMIT 100", (now,))
            return attempts <= limit

    def sync_profile(self, issuer, claims):
        subject = claims.get("sub")
        email = claims.get("email")
        if not isinstance(subject, str) or not subject or not isinstance(email, str) or not email:
            raise AccountUnavailable()
        if len(email) > 320 or claims.get("email_verified") is not True:
            raise AccountUnavailable()
        user_id = "oidc:" + hashlib.sha256((issuer + "\n" + subject).encode()).hexdigest()
        with self.connection() as c, c.cursor() as cur:
            cur.execute("SELECT UserId,AccountStatus FROM `User` WHERE UserId=%s FOR UPDATE", (user_id,))
            user = cur.fetchone()
            if user and user["AccountStatus"] != "active":
                raise AccountUnavailable()
            if user:
                cur.execute("UPDATE `User` SET LastLoginDate=UTC_TIMESTAMP() WHERE UserId=%s", (user_id,))
            else:
                try:
                    # This deliberately cannot be interpreted as a usable local password.
                    cur.execute(
                        "INSERT INTO `User` (UserId,Email,PasswordHash,FirstName,LastName,Role,"
                        "AccountStatus,EmailVerified,LastLoginDate) VALUES (%s,%s,%s,%s,%s,'user','active',1,UTC_TIMESTAMP())",
                        (user_id, email, "!external-auth:oidc", str(claims.get("given_name") or "")[:100],
                         str(claims.get("family_name") or "")[:100]))
                except pymysql.IntegrityError:
                    # Duplicate email is not permission to merge identities or restore accounts.
                    raise AccountUnavailable() from None
        return user_id

    def get_user(self, user_id):
        with self.connection() as c, c.cursor() as cur:
            cur.execute("SELECT UserId,Email,FirstName,LastName,EmailVerified,AccountStatus "
                        "FROM `User` WHERE UserId=%s", (user_id,))
            row = cur.fetchone()
            if not row or row["AccountStatus"] != "active" or row["EmailVerified"] != 1:
                return None
            return {"email": row["Email"], "firstName": row["FirstName"] or "",
                    "lastName": row["LastName"] or "", "emailVerified": True}
