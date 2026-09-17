"""Auth0 login with PKCE, verified identity profiles, and server-side sessions."""
import hashlib
import json
import os
import re
import secrets
import time
from pathlib import Path
from urllib.parse import urlparse

import boto3
from authlib.integrations.flask_client import OAuth
from flask import Flask, jsonify, redirect, request, session
from flask.sessions import SecureCookieSession, SessionInterface
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix

from store import AccountUnavailable, Store

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


def create_app(settings=None, store=None, remote=None):
    settings = settings if settings is not None else load_settings()
    app = Flask(__name__, static_folder=None)
    # The service binds only loopback; nginx overwrites these forwarded headers.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)
    app.config.update(MAX_CONTENT_LENGTH=4096, SECRET_KEY=secrets.token_hex(32))
    origin = settings.get("NEKTRON_SITE_ORIGIN", "https://nektron.ai").rstrip("/")
    issuer = settings.get("NEKTRON_AUTH_ISSUER", "").rstrip("/") + "/"
    enabled = settings.get("NEKTRON_ACCOUNT_ENABLED") == "true"
    if enabled and (urlparse(origin).scheme != "https" or urlparse(issuer).scheme != "https"
                    or not settings.get("NEKTRON_AUTH_CLIENT_ID")):
        raise ValueError("HTTPS origin, issuer and Auth0 client ID are required")
    backend = store or (Store(settings) if enabled else None)
    app.session_interface = DatabaseSessions(backend)
    if remote is None and enabled:
        oauth = OAuth(app)
        remote = oauth.register(
            "identity", client_id=settings["NEKTRON_AUTH_CLIENT_ID"],
            client_secret=settings.get("NEKTRON_AUTH_CLIENT_SECRET") or None,
            server_metadata_url=issuer + ".well-known/openid-configuration",
            client_kwargs={"scope": "openid profile email", "code_challenge_method": "S256", "default_timeout": 10,
                           "token_endpoint_auth_method": "client_secret_post" if settings.get("NEKTRON_AUTH_CLIENT_SECRET") else "none"},
        )

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
            if not csrf or not secrets.compare_digest(csrf, session.get("csrf", "")):
                return jsonify(error="INVALID_CSRF"), 403

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
        # Do not log exception strings, request URLs, codes, tokens, or DB credentials.
        if isinstance(error, HTTPException):
            return jsonify(error="REQUEST_FAILED"), error.code
        app.logger.error("account_request_failed type=%s", type(error).__name__)
        return jsonify(error="ACCOUNT_UNAVAILABLE"), 503

    @app.get("/api/account/health")
    def health():
        if enabled:
            backend.read_session("0" * 64)
        return jsonify(status="ready" if enabled else "not_configured"), 200 if enabled else 503

    @app.get("/api/account/session")
    def current_user():
        user_id = session.get("user_id")
        if not user_id:
            return jsonify(authenticated=False)
        user = backend.get_user(user_id)
        if user is None:
            session.clear()
            return jsonify(authenticated=False)
        return jsonify(authenticated=True, user=user, csrfToken=session["csrf"])

    @app.get("/api/account/login")
    def login():
        if request.headers.get("Sec-Fetch-Site") == "cross-site":
            return jsonify(error="INVALID_ORIGIN"), 403
        if request.host != urlparse(origin).netloc:
            mode = "signup" if request.args.get("mode") == "signup" else "login"
            return redirect(origin + "/api/account/login?mode=" + mode)
        if not backend.allow_request(request.remote_addr or "unknown"):
            return jsonify(error="TRY_LATER"), 429
        return_to = request.args.get("returnTo", "/account.html")
        if return_to not in ("/account.html", "/database-connector.html"):
            return_to = "/account.html"
        # New flow invalidates an older login flow and prevents session fixation.
        app.session_interface.rotate(session)
        session.expires = int(time.time()) + 600
        session["return_to"] = return_to
        session["flow_started"] = int(time.time())
        session["flow_nonce"] = secrets.token_urlsafe(32)
        parameters = {"screen_hint": "signup"} if request.args.get("mode") == "signup" else {}
        return remote.authorize_redirect(origin + "/api/account/callback", nonce=session["flow_nonce"], **parameters)

    @app.get("/api/account/callback")
    def callback():
        started = session.get("flow_started", 0)
        if not started or not 0 <= time.time() - started <= 600:
            if not session.get("user_id"):
                session.clear()
            return redirect("/login.html?error=expired")
        try:
            # Authlib validates state, PKCE exchange, JWKS signature, issuer,
            # audience, expiry and the OIDC nonce before returning userinfo.
            token = remote.authorize_access_token(leeway=30)
            claims = token.get("userinfo")
            if (not token.get("id_token") or not claims or claims.get("iss") != issuer
                    or not claims.get("sub") or claims.get("nonce") != session.get("flow_nonce")):
                raise AccountUnavailable()
            if claims.get("email_verified") is not True:
                session.clear()
                return redirect("/login.html?error=verify_email")
            user_id = backend.sync_profile(issuer, claims)
        except Exception:
            session.clear()
            return redirect("/login.html?error=signin_failed")
        destination = session.get("return_to", "/account.html")
        if destination not in ("/account.html", "/database-connector.html"):
            destination = "/account.html"
        app.session_interface.rotate(session)
        session.update(user_id=user_id, csrf=secrets.token_urlsafe(32))
        return redirect(destination)

    @app.post("/api/account/logout")
    def logout():
        session.clear()
        # End this website session without signing the user out of other products.
        return jsonify(signedOut=True)

    return app
