import copy
import hashlib
import secrets
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import COOKIE, create_app
from credentials import credential_tag, password_hash, password_matches
from account_profile import COUNTRIES

ORIGIN = "https://nektron.ai"
EMAIL = "native-user@example.com"
PASSWORD = "a unique test passphrase 123"
NEW_PASSWORD = "a second unique passphrase 456"
SETTINGS = {"NEKTRON_SITE_ORIGIN": ORIGIN, "NEKTRON_ACCOUNT_ENABLED": "true"}
PROFILE = {"firstName":"Test", "lastName":"Member", "countryCode":"US"}


class MemoryStore:
    def __init__(self):
        self.sessions, self.users, self.tokens = {}, {}, {}
        self.allow = True

    def read_session(self, digest):
        row = self.sessions.get(digest)
        return copy.deepcopy(row) if row and row[1] > time.time() else None

    def save_session(self, digest, data, expires, new):
        if new or digest in self.sessions:
            self.sessions[digest] = (copy.deepcopy(data), expires)

    def delete_session(self, digest):
        self.sessions.pop(digest, None)

    def allow_request(self, key, **kwargs):
        return self.allow

    def find_account(self, email):
        return copy.deepcopy(self.users.get(email))

    def create_pending(self, email, hashed, first_name, last_name, middle_name, country_code, phone_number):
        if email in self.users:
            return False
        self.users[email] = {"UserId": "native:" + secrets.token_hex(12), "Email": email,
            "PasswordHash": hashed, "FirstName": first_name, "LastName": last_name,
            "MiddleName": middle_name or None, "CountryCode": country_code, "PhoneNumber": phone_number or None,
            "Role": "user", "AccountStatus": "pending", "EmailVerified": 0}
        return True

    def finish_login(self, user_id, expected):
        user = next(u for u in self.users.values() if u["UserId"] == user_id)
        if user["AccountStatus"] != "active" or not user["EmailVerified"] or user["PasswordHash"] != expected:
            return None
        return {"user_id": user_id, "auth_tag": credential_tag(expected)}

    def issue_token(self, email, purpose):
        user = self.users.get(email)
        if not user or user["AccountStatus"] not in ("active", "pending"):
            return None
        if purpose == "verify" and user["EmailVerified"]:
            return None
        self.tokens = {k:v for k,v in self.tokens.items() if v["email"] != email or v["purpose"] != purpose}
        raw = secrets.token_urlsafe(32)
        self.tokens[hashlib.sha256(raw.encode()).hexdigest()] = {
            "email":email,"purpose":purpose,"expires":time.time()+1800,
            "tag":credential_tag(user["PasswordHash"])}
        return {"email":email,"token":raw}

    def mark_token_sent(self, raw):
        self.tokens[hashlib.sha256(raw.encode()).hexdigest()]["sent"] = True

    def consume_token(self, raw, purpose, new_hash=None):
        key = hashlib.sha256(raw.encode()).hexdigest()
        record = self.tokens.get(key)
        if not record or record["purpose"] != purpose or record["expires"] <= time.time():
            return False
        user = self.users[record["email"]]
        if user["AccountStatus"] not in ("active","pending") or record["tag"] != credential_tag(user["PasswordHash"]):
            return False
        user.update(EmailVerified=1, AccountStatus="active")
        if purpose == "reset": user["PasswordHash"] = new_hash
        self.tokens = {k:v for k,v in self.tokens.items() if v["email"] != user["Email"]}
        self.sessions = {k:v for k,v in self.sessions.items() if v[0].get("user_id") != user["UserId"]}
        return True

    def get_user(self, user_id, auth_tag=None):
        for user in self.users.values():
            if user["UserId"] == user_id and user["AccountStatus"] == "active" and user["EmailVerified"] and auth_tag == credential_tag(user["PasswordHash"]):
                return {"email":user["Email"],"firstName":user["FirstName"],"lastName":user["LastName"],
                        "middleName":user.get("MiddleName") or "", "countryCode":user.get("CountryCode") or "",
                        "country":COUNTRIES.get(user.get("CountryCode"), ""), "phoneNumber":user.get("PhoneNumber") or "",
                        "emailVerified":True}
        return None


class CaptureMailer:
    def __init__(self): self.sent=[]
    def send(self, email, purpose, token): self.sent.append((email,purpose,token))


class AccountTests(unittest.TestCase):
    def setUp(self):
        self.store, self.mailer = MemoryStore(), CaptureMailer()
        self.app = create_app(SETTINGS, self.store, self.mailer)
        self.app.testing = True
        self.client = self.app.test_client()

    def get(self, path):
        return self.client.get("/api/account/" + path, base_url=ORIGIN)

    def post(self, path, data, headers=None):
        csrf = self.get("csrf").json["csrfToken"]
        actual = {"Origin":ORIGIN, "X-CSRF-Token":csrf} if headers is None else headers
        return self.client.post("/api/account/" + path, json=data, headers=actual, base_url=ORIGIN)

    def signup(self):
        return self.post("signup", {"email":EMAIL, "password":PASSWORD, **PROFILE})

    def verified(self):
        self.signup()
        raw = self.mailer.sent[-1][2]
        self.assertEqual(self.post("verify-email", {"token":raw}).status_code, 200)

    def login(self, password=PASSWORD, email=EMAIL):
        return self.post("login", {"email":email,"password":password})

    def test_signup_hashes_password_and_requires_email_verification(self):
        response = self.signup()
        self.assertEqual(response.status_code, 202)
        row = self.store.users[EMAIL]
        self.assertTrue(row["PasswordHash"].startswith("$argon2id$"))
        self.assertTrue(password_matches(row["PasswordHash"],PASSWORD))
        self.assertEqual((row["Role"],row["AccountStatus"],row["EmailVerified"]),("user","pending",0))
        self.assertEqual(self.login().json["error"],"EMAIL_NOT_VERIFIED")
        self.assertNotIn(PASSWORD,response.text)
        self.assertNotIn(self.mailer.sent[-1][2],response.text)

    def test_verification_is_single_use_and_does_not_log_in_automatically(self):
        self.signup()
        raw = self.mailer.sent[-1][2]
        self.assertNotIn(raw, self.store.tokens)
        self.assertEqual(self.post("verify-email",{"token":raw}).status_code,200)
        self.assertEqual(self.post("verify-email",{"token":raw}).status_code,400)
        self.assertFalse(self.get("session").json["authenticated"])

    def test_login_rotates_cookie_and_returns_profile(self):
        self.verified()
        self.get("csrf")
        previous=self.client.get_cookie(COOKIE,domain="nektron.ai").value
        response=self.login()
        self.assertEqual(response.status_code,200)
        current=self.client.get_cookie(COOKIE,domain="nektron.ai").value
        self.assertNotEqual(current,previous)
        self.assertNotIn(hashlib.sha256(previous.encode()).hexdigest(),self.store.sessions)
        for flag in ("Secure","HttpOnly","SameSite=Lax","Path=/"): self.assertIn(flag,response.headers["Set-Cookie"])
        profile=self.get("session").json
        self.assertTrue(profile["authenticated"])
        self.assertEqual(profile["user"]["email"],EMAIL)
        self.assertNotIn("PasswordHash",str(profile))

    def test_wrong_password_and_unknown_account_have_same_error(self):
        self.verified()
        self.assertEqual(self.login("wrong password").json,
                         self.login("wrong password",email="unknown@example.com").json)
        self.assertEqual(self.login("wrong password").status_code,401)

    def test_signup_cannot_assign_role_or_replace_existing_account(self):
        self.verified()
        before=copy.deepcopy(self.store.users[EMAIL])
        self.assertEqual(self.post("signup",{"email":EMAIL,"password":NEW_PASSWORD,"role":"admin"}).status_code,400)
        self.assertEqual(self.post("signup",{"email":EMAIL,"password":NEW_PASSWORD,**PROFILE,
                                              "middleName":"Other","phoneNumber":"+44 20 7946 0000","countryCode":"GB"}).status_code,202)
        self.assertEqual(self.store.users[EMAIL],before)

    def test_csrf_origin_and_json_are_required(self):
        for endpoint, body in (("signup",{"email":EMAIL,"password":PASSWORD}),("login",{"email":EMAIL,"password":PASSWORD}),("request-reset",{"email":EMAIL})):
            self.assertEqual(self.post(endpoint,body,headers={}).status_code,403)
            csrf=self.get("csrf").json["csrfToken"]
            self.assertEqual(self.post(endpoint,body,headers={"Origin":"https://evil.example","X-CSRF-Token":csrf}).status_code,403)
        csrf=self.get("csrf").json["csrfToken"]
        r=self.client.post("/api/account/login",data="x",headers={"Origin":ORIGIN,"X-CSRF-Token":csrf},base_url=ORIGIN)
        self.assertEqual(r.status_code,415)

    def test_repeated_pending_signup_requires_owner_to_choose_new_password(self):
        self.signup()
        previous_hash = self.store.users[EMAIL]["PasswordHash"]
        self.assertEqual(self.post("signup", {"email":EMAIL,"password":NEW_PASSWORD,**PROFILE}).status_code,202)
        self.assertEqual(self.store.users[EMAIL]["PasswordHash"],previous_hash)
        self.assertEqual(self.mailer.sent[-1][1],"reset")
        token=self.mailer.sent[-1][2]
        self.assertEqual(self.post("verify-email",{"token":token}).status_code,400)
        self.assertEqual(self.post("reset-password",{"token":token,"password":NEW_PASSWORD}).status_code,200)
        self.assertEqual(self.login().status_code,401)
        self.assertEqual(self.login(NEW_PASSWORD).status_code,200)

    def test_reset_is_generic_single_use_and_revokes_old_sessions(self):
        self.verified(); self.login()
        old_cookie=self.client.get_cookie(COOKIE,domain="nektron.ai").value
        found=self.post("request-reset",{"email":EMAIL})
        missing=self.post("request-reset",{"email":"unknown@example.com"})
        self.assertEqual(found.json,missing.json)
        self.assertEqual(found.status_code,202)
        raw=self.mailer.sent[-1][2]
        self.assertEqual(self.post("verify-email",{"token":raw}).status_code,400)
        self.assertEqual(self.post("reset-password",{"token":raw,"password":NEW_PASSWORD}).status_code,200)
        self.assertEqual(self.post("reset-password",{"token":raw,"password":NEW_PASSWORD}).status_code,400)
        self.client.set_cookie(COOKIE,old_cookie,domain="nektron.ai")
        self.assertFalse(self.get("session").json["authenticated"])
        self.assertEqual(self.login().status_code,401)
        self.assertEqual(self.login(NEW_PASSWORD).status_code,200)

    def test_expired_token_fails(self):
        self.signup(); raw=self.mailer.sent[-1][2]
        self.store.tokens[hashlib.sha256(raw.encode()).hexdigest()]["expires"]=time.time()-1
        self.assertEqual(self.post("verify-email",{"token":raw}).status_code,400)

    def test_disabled_or_locked_accounts_cannot_login_or_reset(self):
        self.verified()
        for state in ("disabled","locked"):
            self.store.users[EMAIL]["AccountStatus"]=state
            self.assertEqual(self.login().status_code,401)
            sent=len(self.mailer.sent)
            self.post("request-reset",{"email":EMAIL})
            self.assertEqual(len(self.mailer.sent),sent)

    def test_prior_external_account_can_set_password_only_by_email_proof(self):
        self.verified()
        row=self.store.users[EMAIL]; before=row["UserId"]
        row["PasswordHash"]="!external-auth:oidc"
        self.assertEqual(self.login().status_code,401)
        self.post("request-reset",{"email":EMAIL}); raw=self.mailer.sent[-1][2]
        self.assertEqual(self.post("reset-password",{"token":raw,"password":NEW_PASSWORD}).status_code,200)
        self.assertEqual(self.store.users[EMAIL]["UserId"],before)
        self.assertEqual(self.login(NEW_PASSWORD).status_code,200)

    def test_logout_revokes_session(self):
        self.verified();self.login()
        self.assertEqual(self.post("logout",{}).status_code,200)
        self.assertFalse(self.get("session").json["authenticated"])

    def test_short_password_invalid_email_and_bad_token_are_rejected(self):
        self.assertEqual(self.post("signup",{"email":EMAIL,"password":"short"}).status_code,400)
        self.assertEqual(self.post("signup",{"email":"not-an-email","password":PASSWORD}).status_code,400)
        self.assertEqual(self.post("reset-password",{"token":"bad","password":NEW_PASSWORD}).status_code,400)

    def test_rate_limit_stops_password_work(self):
        csrf=self.get("csrf").json["csrfToken"];self.store.allow=False
        response=self.client.post("/api/account/signup",base_url=ORIGIN,json={"email":EMAIL,"password":PASSWORD,**PROFILE},
                                  headers={"Origin":ORIGIN,"X-CSRF-Token":csrf})
        self.assertEqual(response.status_code,429)
        self.assertFalse(self.store.users)

    def test_session_storage_failure_does_not_report_success(self):
        self.verified()
        csrf=self.get("csrf").json["csrfToken"]
        with patch.object(self.store,"save_session",side_effect=RuntimeError("offline")):
            r=self.client.post("/api/account/login",base_url=ORIGIN,json={"email":EMAIL,"password":PASSWORD},
                               headers={"Origin":ORIGIN,"X-CSRF-Token":csrf})
        self.assertEqual(r.status_code,503)

    def test_legacy_routes_stay_on_nektron(self):
        self.assertEqual(self.get("login?mode=signup").location,"/signup.html")
        self.assertEqual(self.get("callback?code=old").location,"/login.html")

    def test_email_failure_does_not_disclose_account_presence(self):
        with patch.object(self.mailer,"send",side_effect=RuntimeError("SES unavailable")):
            self.assertEqual(self.signup().json,{"accepted":True})

    def test_required_profile_fields_cannot_be_omitted_or_blank(self):
        for key in ("firstName", "lastName", "countryCode"):
            for value in (None, "", "   ", 42, []):
                with self.subTest(key=key, value=value):
                    data={"email":EMAIL,"password":PASSWORD,**PROFILE}
                    if value is None: data.pop(key)
                    else: data[key]=value
                    with patch("app.password_hash") as hashing:
                        self.assertEqual(self.post("signup",data).status_code,400)
                        hashing.assert_not_called()
        self.assertFalse(self.store.users)

    def test_all_profile_fields_are_normalized_saved_and_returned(self):
        data={"email":EMAIL,"password":PASSWORD,**PROFILE,"firstName":"  Zo\u00eb ",
              "lastName":" O'Connor-Smith ","middleName":" Mei ","countryCode":"GB","phoneNumber":" +44 (20) 7946-0000 "}
        self.assertEqual(self.post("signup",data).status_code,202)
        user=self.store.users[EMAIL]
        self.assertEqual((user["FirstName"],user["MiddleName"],user["LastName"],user["CountryCode"],user["PhoneNumber"]),
                         ("Zo\u00eb","Mei","O'Connor-Smith","GB","+44 (20) 7946-0000"))
        self.post("verify-email",{"token":self.mailer.sent[-1][2]}); self.login()
        profile=self.get("session").json["user"]
        self.assertEqual(profile["country"],COUNTRIES["GB"])
        self.assertEqual(profile["middleName"],"Mei")
        self.assertEqual(profile["phoneNumber"],"+44 (20) 7946-0000")

    def test_optional_fields_can_be_omitted(self):
        self.assertEqual(self.signup().status_code,202)
        self.assertIsNone(self.store.users[EMAIL]["MiddleName"])
        self.assertIsNone(self.store.users[EMAIL]["PhoneNumber"])

    def test_invalid_profile_values_are_rejected(self):
        for field,value in (("countryCode","ZZ"),("countryCode","United States"),("countryCode","us"),
                            ("middleName","x"*101),("firstName","Test\nName"),("firstName","\u200b"),
                            ("phoneNumber","x"*31),("phoneNumber","call me"),("phoneNumber","+1\n2025550123"),
                            ("middleName",[]),("phoneNumber",{})):
            with self.subTest(field=field):
                self.assertEqual(self.post("signup",{"email":EMAIL,"password":PASSWORD,**PROFILE,field:value}).status_code,400)
        self.assertFalse(self.store.users)

    def test_legacy_accounts_can_still_log_in_without_new_fields(self):
        self.verified()
        self.store.users[EMAIL].update(FirstName=None,LastName=None,CountryCode=None,MiddleName=None,PhoneNumber=None)
        self.assertEqual(self.login().status_code,200)
        self.assertEqual(self.get("session").json["user"]["country"],"")

    def test_country_options_match_server_allowlist(self):
        from html.parser import HTMLParser
        class Countries(HTMLParser):
            def __init__(self):
                super().__init__(); self.options={}; self.code=None
            def handle_starttag(self, tag, attrs):
                if tag == "option": self.code=dict(attrs).get("value")
            def handle_endtag(self, tag):
                if tag == "option": self.code=None
            def handle_data(self, value):
                if self.code: self.options[self.code]=value
        parser=Countries()
        parser.feed((Path(__file__).resolve().parents[3]/"signup.html").read_text(encoding="utf-8"))
        self.assertEqual(parser.options,COUNTRIES)


if __name__ == "__main__": unittest.main()
