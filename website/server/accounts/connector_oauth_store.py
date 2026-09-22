"""Atomic, hashed OAuth credentials in the existing Nektron account database."""
import hashlib
import json
import secrets
import time

from authlib.oauth2.rfc6749.errors import InvalidGrantError


def digest(raw):
    return hashlib.sha256(raw.encode()).hexdigest()


class OAuthStore:
    def __init__(self, account_store):
        self.accounts = account_store

    def create_code(self, raw, data):
        now = int(time.time())
        family = secrets.token_hex(24)
        data = dict(data, family=family)
        with self.accounts.connection() as c, c.cursor() as cur:
            cur.execute("INSERT INTO WebsiteOAuthGrant (GrantId,ClientId,ExpiresAt,Revoked) VALUES (%s,%s,%s,0)",
                        (family, data['client_id'], now + 30*86400))
            cur.execute("INSERT INTO WebsiteOAuthCredential (TokenHash,GrantId,Kind,Data,ExpiresAt,Used) "
                        "VALUES (%s,%s,'code',%s,%s,0)", (digest(raw), family, json.dumps(data), now+120))

    def consume(self, raw, kind, client_id):
        """Lock grant first, then credential. Replays revoke the whole token family."""
        now = int(time.time())
        with self.accounts.connection() as c, c.cursor() as cur:
            cur.execute("SELECT GrantId FROM WebsiteOAuthCredential WHERE TokenHash=%s AND Kind=%s",
                        (digest(raw), kind))
            hint = cur.fetchone()
            if not hint:
                return None
            cur.execute("SELECT * FROM WebsiteOAuthGrant WHERE GrantId=%s FOR UPDATE", (hint['GrantId'],))
            family = cur.fetchone()
            if not family or family['ClientId'] != client_id or family['Revoked'] or family['ExpiresAt'] <= now:
                return None
            cur.execute("SELECT * FROM WebsiteOAuthCredential WHERE TokenHash=%s AND Kind=%s FOR UPDATE",
                        (digest(raw), kind))
            row = cur.fetchone()
            if not row:
                return None
            if row['Used']:
                cur.execute("UPDATE WebsiteOAuthGrant SET Revoked=1 WHERE GrantId=%s", (hint['GrantId'],))
                return None
            if row['ExpiresAt'] <= now:
                return None
            cur.execute("UPDATE WebsiteOAuthCredential SET Used=1 WHERE TokenHash=%s", (digest(raw),))
            data = json.loads(row['Data'])
            data['expires'] = family['ExpiresAt']
            return data

    def save_refresh(self, raw, data):
        with self.accounts.connection() as c, c.cursor() as cur:
            cur.execute("SELECT * FROM WebsiteOAuthGrant WHERE GrantId=%s FOR UPDATE", (data['family'],))
            family = cur.fetchone()
            if (not family or family['Revoked'] or family['ExpiresAt'] <= time.time()
                    or family['ClientId'] != data['client_id']):
                raise InvalidGrantError()
            cur.execute("INSERT INTO WebsiteOAuthCredential (TokenHash,GrantId,Kind,Data,ExpiresAt,Used) "
                        "VALUES (%s,%s,'refresh',%s,%s,0)",
                        (digest(raw), data['family'], json.dumps(data), family['ExpiresAt']))

    def revoke(self, raw, client_id):
        with self.accounts.connection() as c, c.cursor() as cur:
            cur.execute("UPDATE WebsiteOAuthGrant g JOIN WebsiteOAuthCredential t ON g.GrantId=t.GrantId "
                        "SET g.Revoked=1 WHERE t.TokenHash=%s AND g.ClientId=%s", (digest(raw), client_id))
