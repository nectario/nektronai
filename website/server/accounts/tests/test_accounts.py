import copy
import hashlib
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import COOKIE, ServerSession, create_app
from store import AccountUnavailable
from joserfc import jwt
from joserfc.jwk import RSAKey

ORIGIN = "https://nektron.ai"
ISSUER = "https://identity.example.test/"
SETTINGS = {"NEKTRON_SITE_ORIGIN": ORIGIN, "NEKTRON_ACCOUNT_ENABLED": "true",
            "NEKTRON_AUTH_ISSUER": ISSUER, "NEKTRON_AUTH_CLIENT_ID": "website-test"}


class MemoryStore:
    def __init__(self):
        self.sessions = {}
        self.user = None
        self.allow = True
        self.blocked = False
        self.last_claims = None

    def read_session(self, digest):
        value = self.sessions.get(digest)
        return copy.deepcopy(value) if value and value[1] > time.time() else None

    def save_session(self, digest, data, expires, new):
        if new or digest in self.sessions:
            self.sessions[digest] = (copy.deepcopy(data), expires)

    def delete_session(self, digest):
        self.sessions.pop(digest, None)

    def allow_request(self, key):
        return self.allow

    def sync_profile(self, issuer, claims):
        if self.blocked:
            raise AccountUnavailable()
        self.last_claims = dict(claims)
        self.user = {"email": claims["email"], "firstName": "Test", "lastName": "Member",
                     "emailVerified": True}
        return "opaque-test-user"

    def get_user(self, user_id):
        return None if self.blocked else self.user


class AccountTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.key = RSAKey.generate_key(2048, parameters={"kid": "known"})
        cls.unknown_key = RSAKey.generate_key(2048, parameters={"kid": "known"})

    def setUp(self):
        self.store = MemoryStore()
        self.app = create_app(SETTINGS, self.store)
        self.app.testing = True
        self.client = self.app.test_client()
        self.remote = self.app.extensions["authlib.integrations.flask_client"].create_client("identity")
        metadata = {"issuer": ISSUER, "authorization_endpoint": ISSUER + "authorize",
                    "token_endpoint": ISSUER + "oauth/token", "jwks_uri": ISSUER + "jwks",
                    "id_token_signing_alg_values_supported": ["RS256"]}
        self.metadata = patch.object(self.remote, "load_server_metadata", return_value=metadata)
        self.jwks = patch.object(self.remote, "fetch_jwk_set",
                                 return_value={"keys": [self.key.as_dict(private=False)]})
        self.metadata.start()
        self.jwks.start()
        self.addCleanup(self.metadata.stop)
        self.addCleanup(self.jwks.stop)

    def get(self, path):
        return self.client.get(path, base_url=ORIGIN)

    def begin(self, query=""):
        response = self.get("/api/account/login" + query)
        self.assertEqual(response.status_code, 302)
        parameters = parse_qs(urlparse(response.location).query)
        self.assertEqual(parameters["code_challenge_method"], ["S256"])
        self.assertEqual(parameters["scope"], ["openid profile email"])
        self.assertEqual(parameters["redirect_uri"], [ORIGIN + "/api/account/callback"])
        self.assertNotIn("code_verifier", parameters)
        return parameters

    def finish(self, parameters, changes=None, key=None, state=None):
        claims = {"iss": ISSUER, "sub": "auth0|synthetic", "aud": "website-test",
                  "exp": int(time.time()) + 300, "iat": int(time.time()),
                  "nonce": parameters["nonce"][0], "email": "test@example.invalid",
                  "email_verified": True}
        claims.update(changes or {})
        encoded = jwt.encode({"alg": "RS256", "kid": "known"}, claims, key or self.key)
        token = {"access_token": "test-access-token", "token_type": "Bearer", "id_token": encoded}
        with patch.object(self.remote, "fetch_access_token", return_value=token) as fetch:
            response = self.get("/api/account/callback?code=synthetic&state=" + (state or parameters["state"][0]))
        return response, fetch

    def test_anonymous_session_does_not_create_cookie(self):
        response = self.get("/api/account/session")
        self.assertEqual(response.json, {"authenticated": False})
        self.assertNotIn("Set-Cookie", response.headers)
        self.assertEqual(response.headers["Cache-Control"], "no-store")

    def test_signup_uses_hosted_signup_and_safe_redirect(self):
        p = self.begin("?mode=signup&returnTo=https://evil.example")
        self.assertEqual(p["screen_hint"], ["signup"])
        response, fetch = self.finish(p)
        self.assertEqual(response.location, "/account.html")
        self.assertTrue(fetch.call_args.kwargs.get("code_verifier"))

    def test_verified_login_rotates_session_and_never_exposes_tokens(self):
        p = self.begin()
        old_cookie = self.client.get_cookie(COOKIE, domain="nektron.ai").value
        response, _ = self.finish(p)
        new_cookie = self.client.get_cookie(COOKIE, domain="nektron.ai").value
        self.assertNotEqual(old_cookie, new_cookie)
        self.assertNotIn(hashlib.sha256(old_cookie.encode()).hexdigest(), self.store.sessions)
        for flag in ("Secure", "HttpOnly", "SameSite=Lax", "Path=/"):
            self.assertIn(flag, response.headers["Set-Cookie"])
        self.assertNotIn("Domain=", response.headers["Set-Cookie"])
        profile = self.get("/api/account/session")
        self.assertTrue(profile.json["authenticated"])
        self.assertNotIn("access_token", profile.text)
        self.assertNotIn("id_token", repr(self.store.sessions))

    def test_wrong_state_does_not_exchange_code(self):
        p = self.begin()
        response, fetch = self.finish(p, state="tampered")
        self.assertEqual(response.location, "/login.html?error=signin_failed")
        fetch.assert_not_called()

    def test_bad_signed_claims_are_rejected(self):
        for changes in ({"nonce": "wrong"}, {"nonce": "wrong", "nonce_supported": False},
                        {"aud": "other-client"}, {"iss": "https://wrong.example/"},
                        {"exp": int(time.time()) - 90}, {"email_verified": False}):
            with self.subTest(changes=changes):
                p = self.begin()
                response, _ = self.finish(p, changes)
                self.assertTrue(response.location.startswith("/login.html?error="))
                self.assertFalse(self.get("/api/account/session").json["authenticated"])

    def test_unknown_signature_is_rejected(self):
        response, _ = self.finish(self.begin(), key=self.unknown_key)
        self.assertEqual(response.location, "/login.html?error=signin_failed")

    def test_replayed_callback_is_rejected(self):
        p = self.begin()
        self.finish(p)
        response, fetch = self.finish(p)
        self.assertEqual(response.location, "/login.html?error=expired")
        fetch.assert_not_called()
        self.assertTrue(self.get("/api/account/session").json["authenticated"])

    def test_cross_site_login_cannot_clear_session(self):
        self.finish(self.begin())
        response = self.client.get("/api/account/login", base_url=ORIGIN,
                                    headers={"Sec-Fetch-Site": "cross-site"})
        self.assertEqual(response.status_code, 403)
        self.assertTrue(self.get("/api/account/session").json["authenticated"])

    def test_session_write_failure_never_reports_success(self):
        p = self.begin()
        with patch.object(self.store, "save_session", side_effect=RuntimeError("storage offline")):
            response, _ = self.finish(p)
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("Location", response.headers)

    def test_logout_requires_origin_and_csrf_then_revokes_session(self):
        self.finish(self.begin())
        csrf = self.get("/api/account/session").json["csrfToken"]
        for headers in ({}, {"Origin": ORIGIN}, {"Origin": "https://evil.example", "X-CSRF-Token": csrf}):
            self.assertEqual(self.client.post("/api/account/logout", base_url=ORIGIN, headers=headers).status_code, 403)
        response = self.client.post("/api/account/logout", base_url=ORIGIN,
                                    headers={"Origin": ORIGIN, "X-CSRF-Token": csrf})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(self.get("/api/account/session").json["authenticated"])
        self.assertFalse(self.store.sessions)

    def test_account_disabled_after_login_is_rejected(self):
        self.finish(self.begin())
        self.store.blocked = True
        self.assertFalse(self.get("/api/account/session").json["authenticated"])

    def test_rate_limit_blocks_login(self):
        self.store.allow = False
        self.assertEqual(self.get("/api/account/login").status_code, 429)

    def test_unconfigured_service_is_explicit(self):
        app = create_app({}, MemoryStore())
        response = app.test_client().get("/api/account/session", base_url=ORIGIN)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json["error"], "ACCOUNT_UNAVAILABLE")


if __name__ == "__main__":
    unittest.main()
