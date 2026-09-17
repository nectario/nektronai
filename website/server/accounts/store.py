"""Native website accounts, hashed action tokens, and opaque sessions."""
import hashlib
import json
import hmac
import secrets
import uuid
import ssl
import time
from contextlib import contextmanager
from pathlib import Path

import pymysql

from credentials import credential_tag
from account_profile import COUNTRIES


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
        self.migrate_profile()

    def migrate_profile(self):
        with self.connection() as connection, connection.cursor() as cur:
            cur.execute("SELECT DATA_TYPE,CHARACTER_MAXIMUM_LENGTH,IS_NULLABLE FROM information_schema.COLUMNS "
                        "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='User' AND COLUMN_NAME='CountryCode'")
            column = cur.fetchone()
            if not column:
                # Existing accounts and other products may not have country information.
                cur.execute("ALTER TABLE `User` ADD COLUMN CountryCode CHAR(2) "
                            "CHARACTER SET ascii COLLATE ascii_bin NULL DEFAULT NULL")
            elif (column["DATA_TYPE"] != "char" or column["CHARACTER_MAXIMUM_LENGTH"] != 2
                  or column["IS_NULLABLE"] != "YES"):
                raise RuntimeError("Existing CountryCode definition differs; manual review required")

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

    def find_account(self, email):
        with self.connection() as c, c.cursor() as cur:
            cur.execute("SELECT UserId,Email,PasswordHash,FirstName,LastName,AccountStatus,EmailVerified "
                        "FROM `User` WHERE Email=%s", (email,))
            return cur.fetchone()

    def create_pending(self, email, hashed_password, first_name, last_name, middle_name, country_code, phone_number):
        with self.connection() as c, c.cursor() as cur:
            try:
                cur.execute(
                    "INSERT INTO `User` (UserId,Email,PasswordHash,FirstName,LastName,MiddleName,CountryCode,PhoneNumber,Role,AccountStatus,EmailVerified) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'user','pending',0)",
                    ("native:" + str(uuid.uuid4()), email, hashed_password, first_name, last_name,
                     middle_name or None, country_code, phone_number or None))
                return True
            except pymysql.IntegrityError:
                # A repeated signup never replaces an existing password or account state.
                return False

    def finish_login(self, user_id, expected_hash):
        with self.connection() as c, c.cursor() as cur:
            cur.execute("SELECT PasswordHash,AccountStatus,EmailVerified FROM `User` WHERE UserId=%s FOR UPDATE", (user_id,))
            row = cur.fetchone()
            if (not row or row["AccountStatus"] != "active" or row["EmailVerified"] != 1
                    or not hmac.compare_digest(row["PasswordHash"], expected_hash)):
                return None
            cur.execute("UPDATE `User` SET LastLoginDate=UTC_TIMESTAMP() WHERE UserId=%s", (user_id,))
            return {"user_id": user_id, "auth_tag": credential_tag(expected_hash)}

    def issue_token(self, email, purpose):
        now = int(time.time())
        with self.connection() as c, c.cursor() as cur:
            # Lock the user first in both issuance and consumption.
            cur.execute("SELECT UserId,Email,PasswordHash,AccountStatus,EmailVerified FROM `User` WHERE Email=%s FOR UPDATE", (email,))
            row = cur.fetchone()
            if not row or row["AccountStatus"] not in ("pending", "active"):
                return None
            if purpose == "verify" and (row["EmailVerified"] == 1 or row["AccountStatus"] != "pending"):
                return None
            if purpose not in ("verify", "reset"):
                raise ValueError("Unknown token purpose")
            raw = secrets.token_urlsafe(32)
            digest = hashlib.sha256(raw.encode()).hexdigest()
            expiry = now + (86400 if purpose == "verify" else 1800)
            cur.execute("DELETE FROM WebsiteActionToken WHERE UserId=%s AND Purpose=%s", (row["UserId"], purpose))
            cur.execute("INSERT INTO WebsiteActionToken (TokenHash,UserId,Purpose,CredentialTag,ExpiresAt) "
                        "VALUES (%s,%s,%s,%s,%s)",
                        (digest, row["UserId"], purpose, credential_tag(row["PasswordHash"]), expiry))
            cur.execute("DELETE FROM WebsiteActionToken WHERE ExpiresAt<%s LIMIT 100", (now,))
            return {"email": row["Email"], "token": raw}

    def mark_token_sent(self, raw):
        digest = hashlib.sha256(raw.encode()).hexdigest()
        with self.connection() as c, c.cursor() as cur:
            cur.execute("UPDATE WebsiteActionToken SET SentAt=%s WHERE TokenHash=%s", (int(time.time()), digest))

    def consume_token(self, raw, purpose, new_hash=None):
        digest = hashlib.sha256(raw.encode()).hexdigest()
        with self.connection() as c, c.cursor() as cur:
            cur.execute("SELECT UserId FROM WebsiteActionToken WHERE TokenHash=%s", (digest,))
            hint = cur.fetchone()
            if not hint:
                return False
            cur.execute("SELECT UserId,PasswordHash,AccountStatus FROM `User` WHERE UserId=%s FOR UPDATE", (hint["UserId"],))
            user = cur.fetchone()
            cur.execute("SELECT * FROM WebsiteActionToken WHERE TokenHash=%s FOR UPDATE", (digest,))
            token = cur.fetchone()
            if (not user or not token or token["UserId"] != user["UserId"]
                    or token["Purpose"] != purpose or token["ExpiresAt"] <= int(time.time())
                    or user["AccountStatus"] not in ("active", "pending")
                    or not hmac.compare_digest(token["CredentialTag"], credential_tag(user["PasswordHash"]))):
                return False
            if purpose == "verify":
                if user["AccountStatus"] != "pending":
                    return False
                cur.execute("UPDATE `User` SET EmailVerified=1,AccountStatus='active' WHERE UserId=%s", (user["UserId"],))
            elif purpose == "reset" and new_hash:
                cur.execute("UPDATE `User` SET PasswordHash=%s,EmailVerified=1,AccountStatus='active' WHERE UserId=%s",
                            (new_hash, user["UserId"]))
            else:
                return False
            cur.execute("DELETE FROM WebsiteActionToken WHERE UserId=%s", (user["UserId"],))
            cur.execute("DELETE FROM WebsiteSession WHERE JSON_UNQUOTE(JSON_EXTRACT(Data,'$.user_id'))=%s", (user["UserId"],))
            return True

    def get_user(self, user_id, auth_tag=None):
        with self.connection() as c, c.cursor() as cur:
            cur.execute("SELECT UserId,Email,FirstName,LastName,MiddleName,CountryCode,PhoneNumber,EmailVerified,AccountStatus,PasswordHash "
                        "FROM `User` WHERE UserId=%s", (user_id,))
            row = cur.fetchone()
            if (not row or row["AccountStatus"] != "active" or row["EmailVerified"] != 1
                    or not isinstance(auth_tag, str) or not row["PasswordHash"].startswith("$argon2id$")
                    or not hmac.compare_digest(auth_tag, credential_tag(row["PasswordHash"]))):
                return None
            return {"email": row["Email"], "firstName": row["FirstName"] or "",
                    "lastName": row["LastName"] or "", "middleName": row["MiddleName"] or "",
                    "countryCode": row["CountryCode"] or "", "country": COUNTRIES.get(row["CountryCode"], ""),
                    "phoneNumber": row["PhoneNumber"] or "", "emailVerified": True}
