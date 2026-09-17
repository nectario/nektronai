"""Same-origin email/password authentication for the Nektron website."""
import hashlib
import json
import os
import re
import secrets
import time
from pathlib import Path
from urllib.parse import urlparse

import boto3
from flask import Flask, jsonify, redirect, request, session
from flask.sessions import SecureCookieSession, SessionInterface
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix

from store import Store
from credentials import normalize_email, password_hash, password_matches, password_valid
from mail import Mailer
from account_profile import signup_profile

COOKIE = "__Host-nektron_session"


class ServerSession(SecureCookieSession):
    def __init__(self, data=None, token=None, expires=None):
        super().__init__(data or {})
        self.token = token or secrets.token_urlsafe(32)
        self.expires = expires or int(time.time()) + 600
        self.new = token is None
        self.failed = False

    @property
    def digest(self):
        return hashlib.sha256(self.token.encode()).hexdigest()


class DatabaseSessions(SessionInterface):
    def __init__(self, store):
        self.store = store

    def open_session(self, app, req):
        token = req.cookies.get(COOKIE, "")
        if re.fullmatch(r"[A-Za-z0-9_-]{43}", token):
            try:
                record = self.store.read_session(hashlib.sha256(token.encode()).hexdigest())
                if record:
                    return ServerSession(record[0], token, record[1])
            except Exception:
                failed = ServerSession()
                failed.failed = True
                return failed
        return ServerSession()

    def save_session(self, app, current, response):
        if current.failed:
            return
        if not current:
            if not current.new:
                self.store.delete_session(current.digest)
                response.delete_cookie(COOKIE, path="/", secure=True, httponly=True, samesite="Lax")
            return
        if current.modified or current.new:
            try:
                self.store.save_session(current.digest, dict(current), current.expires, current.new)
            except Exception:
                # Never report successful login when session persistence failed.
                response.status_code = 503
                response.headers.pop("Location", None)
                response.set_data('{"error":"ACCOUNT_UNAVAILABLE"}')
                response.content_type = "application/json"
                response.delete_cookie(COOKIE, path="/", secure=True, httponly=True, samesite="Lax")
                return
            response.set_cookie(COOKIE, current.token, path="/",
                                max_age=max(0, current.expires - int(time.time())),
                                secure=True, httponly=True, samesite="Lax")

    def rotate(self, current):
        if not current.new:
            self.store.delete_session(current.digest)
        current.clear()
        current.token = secrets.token_urlsafe(32)
        current.expires = int(time.time()) + 8 * 3600
        current.new = True


def load_settings():
    settings = {k: v for k, v in os.environ.items() if k.startswith("NEKTRON_")}
    arn = settings.get("NEKTRON_ACCOUNT_SECRET_ARN")
    if arn:
        secret = boto3.client("secretsmanager", region_name=os.getenv("AWS_REGION", "us-east-2")).get_secret_value(SecretId=arn)
        settings.update(json.loads(secret["SecretString"]))
    settings.setdefault("NEKTRON_DB_CA_FILE", str(Path(__file__).with_name("rds-ca.pem")))
    return settings


def create_app(settings=None, store=None, mailer=None):
    settings = settings if settings is not None else load_settings()
    app = Flask(__name__, static_folder=None)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)
    app.config.update(MAX_CONTENT_LENGTH=4096, SECRET_KEY=secrets.token_hex(32))
    origin = settings.get("NEKTRON_SITE_ORIGIN", "https://nektron.ai").rstrip("/")
    enabled = settings.get("NEKTRON_ACCOUNT_ENABLED") == "true"
    if enabled and urlparse(origin).scheme != "https":
        raise ValueError("HTTPS site origin is required")
    backend = store or (Store(settings) if enabled else None)
    delivery = mailer or (Mailer(settings) if enabled else None)
    app.session_interface = DatabaseSessions(backend)

    @app.before_request
    def require_ready():
        if not enabled and request.path != "/api/account/health":
            return jsonify(error="ACCOUNT_UNAVAILABLE"), 503
        if session.failed:
            return jsonify(error="ACCOUNT_UNAVAILABLE"), 503
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            if request.headers.get("Origin") != origin:
                return jsonify(error="INVALID_ORIGIN"), 403
            csrf = request.headers.get("X-CSRF-Token", "")
            expected = session.get("csrf", "")
            if not csrf.isascii() or not csrf or not secrets.compare_digest(csrf, expected):
                return jsonify(error="INVALID_CSRF"), 403
            if not request.is_json:
                return jsonify(error="JSON_REQUIRED"), 415

    @app.after_request
    def private_response(response):
        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Vary"] = "Cookie"
        return response

    @app.errorhandler(Exception)
    def error_response(error):
        if isinstance(error, HTTPException):
            return jsonify(error="REQUEST_FAILED"), error.code
        app.logger.error("account_request_failed type=%s", type(error).__name__)
        return jsonify(error="ACCOUNT_UNAVAILABLE"), 503

    def payload(allowed):
        data = request.get_json(silent=True)
        if not isinstance(data, dict) or set(data) - set(allowed):
            raise ValueError("INVALID_INPUT")
        return data

    def limited(action, email=None, limit=20, seconds=600):
        ip = request.remote_addr or "unknown"
        if not backend.allow_request(action + ":ip:" + ip, limit=limit, seconds=seconds):
            return True
        if email and not backend.allow_request(action + ":email:" + email,
                                               limit=min(limit, 10), seconds=seconds):
            return True
        return False

    def send_link(email, purpose):
        result = backend.issue_token(email, purpose)
        if result:
            try:
                delivery.send(result["email"], purpose, result["token"])
                backend.mark_token_sent(result["token"])
            except Exception as error:
                # Do not reveal existence via delivery errors, or log the link/email.
                app.logger.error("account_email_delivery_failed type=%s", type(error).__name__)

    def accepted(start):
        # Give existing and missing accounts the same response and a timing floor.
        if not app.testing:
            time.sleep(max(0, 1.0 - (time.monotonic() - start)))
        return jsonify(accepted=True), 202

    @app.get("/api/account/health")
    def health():
        if enabled:
            backend.read_session("0" * 64)
        return jsonify(status="ready" if enabled else "not_configured"), 200 if enabled else 503

    @app.get("/api/account/csrf")
    def csrf_token():
        if request.headers.get("Sec-Fetch-Site") == "cross-site":
            return jsonify(error="INVALID_ORIGIN"), 403
        if limited("csrf", limit=120):
            return jsonify(error="TRY_LATER"), 429
        if "csrf" not in session:
            session["csrf"] = secrets.token_urlsafe(32)
        return jsonify(csrfToken=session["csrf"])

    @app.get("/api/account/session")
    def current_user():
        user_id = session.get("user_id")
        if not user_id:
            return jsonify(authenticated=False)
        user = backend.get_user(user_id, session.get("auth_tag"))
        if user is None:
            session.clear()
            return jsonify(authenticated=False)
        return jsonify(authenticated=True, user=user, csrfToken=session["csrf"])

    @app.post("/api/account/signup")
    def signup():
        start = time.monotonic()
        try:
            data = payload(("email", "password", "firstName", "lastName", "middleName", "phoneNumber", "countryCode"))
            email = normalize_email(data.get("email"))
            password = data.get("password")
            if not password_valid(password):
                raise ValueError("INVALID_PASSWORD")
            profile = signup_profile(data)
        except ValueError as error:
            return jsonify(error=str(error)), 400
        if limited("signup", email, limit=5, seconds=3600):
            return jsonify(error="TRY_LATER"), 429
        created = backend.create_pending(email, password_hash(password), **profile)
        if created:
            send_link(email, "verify")
        else:
            account = backend.find_account(email)
            if account and account["AccountStatus"] == "pending":
                # The address owner must replace a pre-registered password,
                # not accidentally activate a password chosen by someone else.
                send_link(email, "reset")
        return accepted(start)

    @app.post("/api/account/login")
    def login():
        try:
            data = payload(("email", "password"))
            email = normalize_email(data.get("email"))
            password = data.get("password")
            if not isinstance(password, str) or not 1 <= len(password) <= 128:
                raise ValueError("INVALID_INPUT")
        except ValueError:
            return jsonify(error="INVALID_CREDENTIALS"), 401
        if limited("login", email, limit=30):
            return jsonify(error="TRY_LATER"), 429
        account = backend.find_account(email)
        matches = password_matches(account["PasswordHash"] if account else None, password)
        if not account or not matches or account["AccountStatus"] not in ("active", "pending"):
            return jsonify(error="INVALID_CREDENTIALS"), 401
        if account["EmailVerified"] != 1 or account["AccountStatus"] == "pending":
            return jsonify(error="EMAIL_NOT_VERIFIED"), 403
        identity = backend.finish_login(account["UserId"], account["PasswordHash"])
        if not identity:
            return jsonify(error="INVALID_CREDENTIALS"), 401
        app.session_interface.rotate(session)
        session.update(identity)
        session["csrf"] = secrets.token_urlsafe(32)
        return jsonify(authenticated=True, redirect="/account.html")

    @app.post("/api/account/request-verification")
    def request_verification():
        start = time.monotonic()
        try:
            email = normalize_email(payload(("email",)).get("email"))
        except ValueError:
            return jsonify(error="INVALID_EMAIL"), 400
        if limited("verify_request", email, limit=3, seconds=3600):
            return jsonify(error="TRY_LATER"), 429
        send_link(email, "verify")
        return accepted(start)

    @app.post("/api/account/request-reset")
    def request_reset():
        start = time.monotonic()
        try:
            email = normalize_email(payload(("email",)).get("email"))
        except ValueError:
            return jsonify(error="INVALID_EMAIL"), 400
        if limited("reset_request", email, limit=3, seconds=3600):
            return jsonify(error="TRY_LATER"), 429
        send_link(email, "reset")
        return accepted(start)

    def read_token(data):
        token = data.get("token")
        if not isinstance(token, str) or not re.fullmatch(r"[A-Za-z0-9_-]{43}", token):
            raise ValueError("INVALID_LINK")
        return token

    @app.post("/api/account/verify-email")
    def verify_email():
        if limited("verify", limit=20):
            return jsonify(error="TRY_LATER"), 429
        try:
            token = read_token(payload(("token",)))
        except ValueError:
            return jsonify(error="INVALID_LINK"), 400
        if not backend.consume_token(token, "verify"):
            return jsonify(error="INVALID_LINK"), 400
        return jsonify(verified=True)

    @app.post("/api/account/reset-password")
    def reset_password():
        if limited("reset", limit=20):
            return jsonify(error="TRY_LATER"), 429
        try:
            data = payload(("token", "password"))
            token = read_token(data)
            new_hash = password_hash(data.get("password"))
        except ValueError as error:
            return jsonify(error=str(error)), 400
        if not backend.consume_token(token, "reset", new_hash):
            return jsonify(error="INVALID_LINK"), 400
        session.clear()
        return jsonify(reset=True)

    @app.post("/api/account/logout")
    def logout():
        session.clear()
        return jsonify(signedOut=True)

    @app.get("/api/account/login")
    def old_login_link():
        return redirect("/signup.html" if request.args.get("mode") == "signup" else "/login.html")

    @app.get("/api/account/callback")
    def old_callback():
        return redirect("/login.html")

    return app
