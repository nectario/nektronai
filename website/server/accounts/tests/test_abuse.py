"""Abuse regressions use production budget logic with an in-memory SQL adapter."""
import copy
import io
import json
import threading
import unittest
from contextlib import contextmanager
from unittest.mock import patch

import pymysql

from test_accounts import MemoryStore, CaptureMailer, SETTINGS, ORIGIN, EMAIL, PASSWORD, PROFILE
from app import create_app
from abuse import MailAbuseGuard
from store import Store


class BudgetStore(MemoryStore):
    def __init__(self):
        super().__init__()
        self.rows = {}
        self.lock = threading.Lock()
        self.now = 100000

    @contextmanager
    def connection(self):
        with self.lock:
            yield self

    @contextmanager
    def cursor(self):
        yield self

    def execute(self, sql, args):
        if sql.startswith("INSERT INTO WebsiteRateLimit"):
            key, expiry = args
            self.rows.setdefault(key, {"Attempts": 0, "ExpiresAt": expiry})
        elif sql.startswith("SELECT Attempts,ExpiresAt"):
            self.result = copy.deepcopy(self.rows[args[0]])
        elif sql.startswith("UPDATE WebsiteRateLimit SET Attempts"):
            attempts, expiry, key = args
            self.rows[key] = {"Attempts": attempts, "ExpiresAt": expiry}
        else:
            raise AssertionError(sql)

    def fetchone(self):
        return self.result

    def allow_account_email(self, email, ip):
        with patch("store.time.time", return_value=self.now):
            return Store.allow_account_email(self, email, ip)


class AccountAbuseTests(unittest.TestCase):
    def setUp(self):
        self.store, self.mail = BudgetStore(), CaptureMailer()
        self.app = create_app(SETTINGS, self.store, self.mail)
        self.app.testing = True
        self.client = self.app.test_client()

    def post(self, action, data, ip="198.51.100.1"):
        env = {"REMOTE_ADDR": ip}
        csrf = self.client.get("/api/account/csrf", base_url=ORIGIN, environ_overrides=env).json["csrfToken"]
        return self.client.post("/api/account/" + action, json=data, base_url=ORIGIN,
                                environ_overrides=env, headers={"Origin": ORIGIN, "X-CSRF-Token": csrf})

    def signup(self, email=EMAIL, **extras):
        return self.post("signup", {"email": email, "password": PASSWORD, **PROFILE, **extras})

    def test_signup_reset_and_verification_share_recipient_cooldown_across_ips(self):
        self.assertEqual(self.signup().status_code, 202)
        first_token = self.mail.sent[-1][2]
        for action in ("request-reset", "request-verification"):
            self.assertEqual(self.post(action, {"email": EMAIL}, ip="198.51.100.2").json, {"accepted": True})
        self.assertEqual(len(self.mail.sent), 1)
        self.assertEqual(self.post("verify-email", {"token": first_token}).status_code, 200)
        self.store.now += 61
        self.assertEqual(self.post("request-reset", {"email": EMAIL}).status_code, 202)
        self.assertEqual(len(self.mail.sent), 2)

    def test_honeypot_and_sms_gateway_do_not_create_users_or_send_mail(self):
        self.assertEqual(self.signup(website="spam.example").status_code, 202)
        self.assertEqual(self.signup(email="2095057922@TXT.ATT.NET").status_code, 400)
        self.assertEqual(self.post("request-reset", {"email": "2095057922@txt.att.net"}).status_code, 400)
        self.assertFalse(self.store.users)
        self.assertFalse(self.mail.sent)

    def test_unknown_and_existing_addresses_have_identical_throttled_responses(self):
        self.signup()
        known = self.post("request-reset", {"email": EMAIL})
        unknown = self.post("request-reset", {"email": "unknown@example.com"})
        unknown_again = self.post("request-reset", {"email": "unknown@example.com"})
        self.assertEqual((known.status_code, known.json), (unknown.status_code, unknown.json))
        self.assertEqual(known.json, unknown_again.json)
        self.assertEqual(len(self.mail.sent), 1)

    def test_ip_limit_applies_before_password_hashing_and_account_creation(self):
        for n in range(3):
            self.assertEqual(self.signup(f"user{n}@example.com").status_code, 202)
        with patch("app.password_hash") as hashing:
            self.assertEqual(self.signup("extra@example.com").status_code, 429)
            hashing.assert_not_called()
        self.assertEqual(len(self.store.users), 3)

    def test_budget_failure_is_fail_closed(self):
        with patch.object(self.store, "allow_account_email", side_effect=RuntimeError("private details")):
            result = self.signup()
        self.assertEqual(result.status_code, 503)
        self.assertNotIn("private details", result.text)
        self.assertFalse(self.store.users)
        self.assertFalse(self.mail.sent)

    def test_deadlocks_retry_with_bounded_attempts_and_other_errors_fail_closed(self):
        real_connection = self.store.connection
        with patch.object(self.store, "connection", side_effect=[
                pymysql.OperationalError(1213, "deadlock"), real_connection()]):
            self.assertIsNone(self.store.allow_account_email(EMAIL, "198.51.100.1"))
        for code, attempts in ((1213, 3), (1205, 3), (2003, 1)):
            with patch.object(self.store, "connection", side_effect=pymysql.OperationalError(code, "unavailable")) as call:
                with self.assertRaises(pymysql.OperationalError):
                    self.store.allow_account_email(EMAIL, "198.51.100.1")
                self.assertEqual(call.call_count, attempts)

    def test_recipient_hourly_and_daily_limits_span_endpoints(self):
        for n in range(3):
            self.assertIsNone(self.store.allow_account_email(EMAIL, f"198.51.100.{n}"))
            self.store.now += 61
        self.assertEqual(self.store.allow_account_email(EMAIL, "198.51.100.99"), "recipient")
        self.store.now += 3600
        for n in range(3):
            self.assertIsNone(self.store.allow_account_email(EMAIL, f"198.51.100.{n+10}"))
            self.store.now += 61
        self.store.now += 3600
        self.assertEqual(self.store.allow_account_email(EMAIL, "198.51.100.99"), "recipient")
        self.store.now += 86400
        self.assertIsNone(self.store.allow_account_email(EMAIL, "198.51.100.99"))

    def test_cooldown_cannot_be_bypassed_by_crossing_clock_boundary(self):
        self.store.now = 119
        self.assertIsNone(self.store.allow_account_email(EMAIL, "198.51.100.1"))
        self.store.now = 120
        self.assertEqual(self.store.allow_account_email(EMAIL, "198.51.100.2"), "recipient")
        self.store.now = 179
        self.assertIsNone(self.store.allow_account_email(EMAIL, "198.51.100.2"))

    def test_distributed_requests_have_site_wide_burst_hourly_and_daily_caps(self):
        for n in range(100):
            if n and n % 30 == 0: self.store.now += 3600
            elif n and n % 10 == 0: self.store.now += 61
            self.assertIsNone(self.store.allow_account_email(f"user{n}@example.com", f"198.51.100.{n+1}"))
            if n == 9:
                self.assertEqual(self.store.allow_account_email("burst@example.com", "203.0.113.1"), "site")
            if n == 29:
                self.store.now += 61
                self.assertEqual(self.store.allow_account_email("hour@example.com", "203.0.113.1"), "site")
        self.store.now += 3600
        self.assertEqual(self.store.allow_account_email("daily@example.com", "203.0.113.1"), "site")

    def test_rejected_recipient_does_not_spend_other_mail_budgets(self):
        self.store.allow_account_email(EMAIL, "198.51.100.1")
        before = copy.deepcopy(self.store.rows)
        for _ in range(20): self.store.allow_account_email(EMAIL, "198.51.100.1")
        self.assertEqual(self.store.rows, before)

    def test_failed_resend_does_not_invalidate_the_earlier_link(self):
        self.signup()
        original = self.mail.sent[-1][2]
        self.store.now += 61
        with patch.object(self.mail, "send", side_effect=RuntimeError("delivery failed")):
            self.assertEqual(self.post("request-verification", {"email": EMAIL}).status_code, 202)
        self.assertEqual(len(self.store.tokens), 2)
        self.assertEqual(self.post("verify-email", {"token": original}).status_code, 200)
        self.assertFalse(self.store.tokens)


class TurnstileTests(unittest.TestCase):
    def setUp(self):
        self.settings = {**SETTINGS, "NEKTRON_TURNSTILE_SITE_KEY": "public-test-key",
                         "NEKTRON_TURNSTILE_SECRET_KEY": "private-test-key"}
        self.guard = MailAbuseGuard(self.settings)

    def test_keys_are_optional_but_partial_configuration_fails(self):
        self.assertTrue(MailAbuseGuard(SETTINGS).verify(None, "signup", "198.51.100.1"))
        for missing in ("NEKTRON_TURNSTILE_SITE_KEY", "NEKTRON_TURNSTILE_SECRET_KEY"):
            with self.assertRaises(ValueError): MailAbuseGuard({k:v for k,v in self.settings.items() if k != missing})

    def test_custom_blocked_domains_match_only_the_domain_or_its_subdomains(self):
        guard = MailAbuseGuard({**SETTINGS, "NEKTRON_ACCOUNT_BLOCKED_EMAIL_DOMAINS": " abuse.example, "})
        self.assertTrue(guard.blocked_recipient("test@abuse.example"))
        self.assertTrue(guard.blocked_recipient("test@sub.abuse.example"))
        self.assertFalse(guard.blocked_recipient("test@notabuse.example"))

    def test_validates_exact_hostname_action_and_success(self):
        for overrides, expected in (({}, True), ({"success": False}, False),
                                    ({"hostname": "evil.example"}, False), ({"action": "request-reset"}, False)):
            result = {"success": True, "hostname": "nektron.ai", "action": "signup", **overrides}
            with patch("abuse.urlopen", return_value=io.BytesIO(json.dumps(result).encode())) as call:
                self.assertEqual(self.guard.verify("test-token", "signup", "198.51.100.1"), expected)
                self.assertEqual(call.call_args.args[0].full_url, "https://challenges.cloudflare.com/turnstile/v0/siteverify")
                self.assertEqual(call.call_args.kwargs["timeout"], 5)

    def test_missing_oversized_or_invalid_tokens_never_call_provider(self):
        with patch("abuse.urlopen") as provider:
            for token in (None, "", [], 123, "x" * 2049):
                self.assertFalse(self.guard.verify(token, "signup", "198.51.100.1"))
            provider.assert_not_called()

    def test_challenge_is_required_on_every_mail_endpoint_not_login_or_token_consumption(self):
        store, mail = MemoryStore(), CaptureMailer()
        app = create_app(self.settings, store, mail); app.testing = True
        client = app.test_client()
        def post(action, data):
            csrf = client.get("/api/account/csrf", base_url=ORIGIN).json["csrfToken"]
            return client.post("/api/account/" + action, json=data, base_url=ORIGIN,
                               headers={"Origin": ORIGIN, "X-CSRF-Token": csrf})
        for action in ("signup", "request-reset", "request-verification"):
            data = {"email": EMAIL, **({"password": PASSWORD, **PROFILE} if action == "signup" else {})}
            self.assertEqual(post(action, data).json["error"], "HUMAN_VERIFICATION_REQUIRED")
        self.assertFalse(store.users)
        self.assertFalse(mail.sent)
        with patch("abuse.urlopen", side_effect=TimeoutError("private details")):
            r = post("signup", {"email": EMAIL, "password": PASSWORD, **PROFILE, "turnstileToken": "token"})
            self.assertEqual(r.status_code, 503)
            self.assertNotIn("private details", r.text)
        with patch("abuse.urlopen", return_value=io.BytesIO(json.dumps(
                {"success": True, "hostname": "nektron.ai", "action": "signup"}).encode())):
            self.assertEqual(post("signup", {"email": EMAIL, "password": PASSWORD, **PROFILE, "turnstileToken": "token"}).status_code, 202)
        self.assertEqual(post("verify-email", {"token": mail.sent[-1][2]}).status_code, 200)
        self.assertEqual(post("login", {"email": EMAIL, "password": PASSWORD}).status_code, 200)
        config = client.get("/api/account/csrf", base_url=ORIGIN)
        self.assertEqual(config.json["turnstileSiteKey"], "public-test-key")
        self.assertNotIn("private-test-key", config.text)


if __name__ == "__main__":
    unittest.main()
