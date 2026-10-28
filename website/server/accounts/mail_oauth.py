"""Isolated native Mail authorization using the shared NektronAI identity.

No mailbox ownership is inferred here. The archive API applies its own exact
server-managed subject/account grants. Nothing in this module configures a
Database Connector database or issues an ID token. The separate first-party
mail_native module authenticates credentials for explicitly marked Mail sessions.
"""
import base64
import json
import re
import secrets
import time
import unicodedata
from dataclasses import dataclass
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import jwt
from authlib.integrations.flask_oauth2 import AuthorizationServer
from authlib.oauth2.rfc6749 import ClientMixin
from authlib.oauth2.rfc6749.errors import InvalidGrantError, OAuth2Error
from authlib.oauth2.rfc6749.grants import AuthorizationCodeGrant, RefreshTokenGrant
from authlib.oauth2.rfc6750 import BearerTokenGenerator
from authlib.oauth2.rfc7636 import CodeChallenge
from connector_oauth_store import OAuthStore
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey
from cryptography.hazmat.primitives.serialization import load_pem_private_key
from flask import Blueprint, g, jsonify, make_response, redirect, render_template_string, request, session
from mail_native import NATIVE_FLOW, register_native_session
from mail_archive_keys import KEY_SCOPE, register_archive_keys

ISSUER = 'https://nektron.ai'
PREFIX = '/api/account/mail-oauth'
CLIENT_ID = 'nektron-mail-windows'
RESOURCE = 'https://nektron.ai/mail'
READ = 'mail/archive.read'
INGEST = 'mail/archive.ingest'
PENDING_KEY = 'mail_oauth_pending'
CONSENT_KEY = 'mail_oauth_consent'


def valid_callback(value):
    """One literal IPv4 loopback path; no URI normalization or host aliases."""
    if not isinstance(value, str):
        return False
    match = re.fullmatch(r'http://127\.0\.0\.1:([1-9][0-9]{3,4})/nektron-mail/callback', value)
    return bool(match and 1024 <= int(match[1]) <= 65535)


class MailClient(ClientMixin):
    def __init__(self, scopes=(READ,)):
        self.scopes = frozenset(scopes)

    def get_client_id(self):
        return CLIENT_ID

    def get_default_redirect_uri(self):
        return None

    def get_allowed_scope(self, scope):
        return scope if scope in self.scopes else ''

    def check_redirect_uri(self, value):
        return valid_callback(value)

    def check_client_secret(self, value):
        return False

    def check_endpoint_auth_method(self, method, endpoint):
        return method == 'none' and endpoint == 'token'

    def check_response_type(self, value):
        return value == 'code'

    def check_grant_type(self, value):
        return value in {'authorization_code', 'refresh_token'}


@dataclass
class MailUser:
    user_id: str
    auth_tag: str
    grant_id: str | None = None


class MailCredential:
    def __init__(self, data):
        self.data = data
        self.code_challenge = data.get('code_challenge')
        self.code_challenge_method = 'S256' if self.code_challenge else None

    def get_redirect_uri(self):
        return self.data.get('redirect_uri')

    def get_scope(self):
        return self.data['scope']

    def check_client(self, client):
        return self.data['client_id'] == client.get_client_id()


def register_mail_oauth(app, settings, accounts, oauth_store=None, *, login_limited):
    if settings.get('NEKTRON_MAIL_OAUTH_ENABLED') != 'true':
        return
    if (settings.get('NEKTRON_SITE_ORIGIN') != ISSUER
            or settings.get('NEKTRON_ACCOUNT_ENABLED') != 'true'):
        raise ValueError('Mail OAuth requires enabled accounts at the canonical Nektron origin')
    key = load_pem_private_key(settings['NEKTRON_MAIL_SIGNING_PEM'].encode(), password=None)
    if (not isinstance(key, RSAPrivateKey) or not 2048 <= key.key_size <= 8192
            or key.public_key().public_numbers().e != 65537):
        raise ValueError('Mail requires a dedicated 2048-8192 bit RSA signing key with exponent 65537')
    kid = settings['NEKTRON_MAIL_SIGNING_KID']
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', kid):
        raise ValueError('Invalid Mail signing key identifier')
    # Separate audiences alone are insufficient if a deployed signer is compromised.
    # Do not let a mistaken configuration reuse the Connector signing identity.
    connector_pem = settings.get('NEKTRON_CONNECTOR_SIGNING_PEM')
    if connector_pem:
        connector_key = load_pem_private_key(connector_pem.encode(), password=None)
        if key.public_key().public_numbers() == connector_key.public_key().public_numbers():
            raise ValueError('Mail and Database Connector signing keys must be distinct')
    if kid == settings.get('NEKTRON_CONNECTOR_SIGNING_KID'):
        raise ValueError('Mail and Database Connector signing key identifiers must be distinct')
    public = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key()))
    public.update(kid=kid, use='sig', alg='RS256')
    store = oauth_store or OAuthStore(accounts)
    archive_keys_enabled = settings.get('NEKTRON_MAIL_ARCHIVE_KEYS_ENABLED') == 'true'
    # Native database-storage approval creates its own exact-scope family.
    # Browser authorization and existing refresh families never gain this scope.
    ingest_enabled = settings.get('NEKTRON_MAIL_INGEST_ENABLED') == 'true'
    scopes = frozenset(((READ, KEY_SCOPE) if archive_keys_enabled else (READ,))
                       + ((INGEST,) if ingest_enabled else ()))
    client = MailClient(scopes)
    blueprint = Blueprint('mail_oauth', __name__)

    def current_user():
        uid, tag = session.get('user_id'), session.get('auth_tag')
        if uid and accounts.get_user(uid, tag):
            return MailUser(uid, tag)
        return None

    def access_token(client, grant_type, user, scope):
        if (not user or not isinstance(user.user_id, str) or not 1 <= len(user.user_id) <= 255
                or scope not in scopes or client.get_client_id() != CLIENT_ID
                or not accounts.get_user(user.user_id, user.auth_tag)):
            raise InvalidGrantError()
        now = int(time.time())
        claims = {'iss': ISSUER, 'sub': user.user_id, 'aud': RESOURCE,
            'iat': now, 'exp': now + 300, 'jti': secrets.token_urlsafe(24),
            'client_id': CLIENT_ID, 'scope': scope}
        if scope == KEY_SCOPE:
            if not isinstance(user.grant_id, str) or not re.fullmatch(r'[a-f0-9]{48}', user.grant_id):
                raise InvalidGrantError()
            claims['grant_id'] = user.grant_id
        return jwt.encode(claims, key, algorithm='RS256',
            headers={'kid': kid, 'typ': 'at+jwt'})

    def save_token(token, req):
        credential = req.authorization_code if req.payload.grant_type == 'authorization_code' else req.refresh_token
        store.save_refresh(token['refresh_token'], credential.data)

    # Each product owns a distinct server instance, grant classes and generator.
    server = AuthorizationServer(app, query_client=lambda cid: client if cid == CLIENT_ID else None,
                                 save_token=save_token)
    server.register_token_generator('default', BearerTokenGenerator(access_token,
        refresh_token_generator=lambda **kwargs: secrets.token_urlsafe(48), expires_generator=lambda *args: 300))

    def consume(raw, kind, requesting_client):
        data = store.consume(raw, kind, requesting_client.get_client_id())
        if (not data or data.get('client_id') != CLIENT_ID or data.get('resource') != RESOURCE
                or data.get('scope') not in scopes):
            return None
        if kind == 'refresh' and request.form.get('scope', data['scope']) != data['scope']:
            return None  # Explicit scopes never upgrade or narrow a persisted grant.
        if 'authentication_flow' in data:
            # Native sessions have no invented callback or PKCE proof. This marker
            # is accepted only for refresh credentials, never authorization codes.
            if (kind != 'refresh' or data['authentication_flow'] != NATIVE_FLOW
                    or 'redirect_uri' in data or 'code_challenge' in data):
                return None
        elif not valid_callback(data.get('redirect_uri')):
            return None
        return MailCredential(data)

    def credential_user(credential):
        data = credential.data
        return MailUser(data['user_id'], data['auth_tag'], data.get('family')) if accounts.get_user(data['user_id'], data['auth_tag']) else None

    class CodeGrant(AuthorizationCodeGrant):
        TOKEN_ENDPOINT_AUTH_METHODS = ['none']

        def save_authorization_code(self, code, req):
            store.create_code(code, {'user_id': req.user.user_id, 'auth_tag': req.user.auth_tag,
                'client_id': CLIENT_ID, 'redirect_uri': req.payload.redirect_uri,
                'code_challenge': req.payload.data['code_challenge'], 'resource': RESOURCE, 'scope': READ})

        def query_authorization_code(self, code, requesting_client):
            return consume(code, 'code', requesting_client)

        def delete_authorization_code(self, code):
            pass  # Atomically consumed before exchange, including failed PKCE.

        def authenticate_user(self, code):
            return credential_user(code)

    class RefreshGrant(RefreshTokenGrant):
        TOKEN_ENDPOINT_AUTH_METHODS = ['none']
        INCLUDE_NEW_REFRESH_TOKEN = True

        def authenticate_refresh_token(self, raw):
            return consume(raw, 'refresh', self.request.client)

        def authenticate_user(self, credential):
            return credential_user(credential)

        def revoke_old_credential(self, credential):
            pass  # OAuthStore atomically consumes; replay revokes the family.

    class S256(CodeChallenge):
        SUPPORTED_CODE_CHALLENGE_METHOD = ['S256']

    server.register_grant(CodeGrant, [S256(required=True)])
    server.register_grant(RefreshGrant)

    def limited(action, limit=60):
        return not accounts.allow_request('mail-oauth:' + action + ':' + (request.remote_addr or 'unknown'),
                                          limit=limit, seconds=600)

    def clean_parameters(values, allowed):
        return (not set(values) - set(allowed) and all(len(values.getlist(k)) == 1
            and len(values[k]) <= 2048 and not any(ord(c) < 32 or ord(c) == 127 for c in values[k]) for k in values))

    @blueprint.get(PREFIX + '/jwks')
    def jwks():
        return jsonify(keys=[public])

    @blueprint.route(PREFIX + '/authorize', methods=['GET', 'POST'])
    def authorize():
        params = request.args
        allowed = {'client_id', 'redirect_uri', 'response_type', 'scope', 'state', 'resource',
                   'code_challenge', 'code_challenge_method', 'response_mode', 'screen'}
        if (not clean_parameters(params, allowed) or params.get('client_id') != CLIENT_ID
                or not valid_callback(params.get('redirect_uri')) or params.get('resource') != RESOURCE
                or params.get('scope') != READ or params.get('response_type') != 'code'
                or params.get('response_mode', 'query') != 'query' or not params.get('state')
                or params.get('screen', 'signup') != 'signup'
                or params.get('code_challenge_method') != 'S256'
                or not re.fullmatch(r'[A-Za-z0-9_-]{43}', params.get('code_challenge', ''))):
            return jsonify(error='invalid_request'), 400
        if limited('authorize'):
            return jsonify(error='temporarily_unavailable'), 429
        user = current_user()
        try:
            server.get_consent_grant(end_user=user)
        except OAuth2Error:
            return jsonify(error='invalid_request'), 400
        if not user:
            session[PENDING_KEY] = {'params': params.to_dict(), 'created': int(time.time())}
            page = 'signup' if params.get('screen') == 'signup' else 'login'
            return redirect('/' + page + '.html?returnTo=mail-authorize')
        if request.method == 'GET':
            session[CONSENT_KEY] = {'nonce': secrets.token_urlsafe(32), 'params': params.to_dict(),
                                   'created': int(time.time()), 'user_id': user.user_id}
            session.setdefault('csrf', secrets.token_urlsafe(32))
            profile = accounts.get_user(user.user_id, user.auth_tag)
            return render_template_string(CONSENT, csrf=session['csrf'], nonce=session[CONSENT_KEY]['nonce'],
                                          email=profile['email'])
        consent = session.pop(CONSENT_KEY, {})
        body = request.get_json(silent=True)
        if (not isinstance(body, dict) or set(body) != {'approve', 'nonce'} or type(body['approve']) is not bool
                or not isinstance(body['nonce'], str) or not consent
                or not secrets.compare_digest(body['nonce'].encode(), consent.get('nonce', '').encode())
                or consent.get('params') != params.to_dict() or consent.get('user_id') != user.user_id
                or not 0 <= time.time() - consent.get('created', 0) <= 600):
            return jsonify(error='invalid_request'), 400
        response = server.create_authorization_response(grant_user=user if body['approve'] else None)
        location = response.headers.get('Location')
        if not location:
            return response
        parsed = urlsplit(location)
        if urlunsplit((parsed.scheme, parsed.netloc, parsed.path, '', '')) != params['redirect_uri']:
            return jsonify(error='invalid_request'), 400
        # Keep native callbacks minimal; never forward explanatory URLs/messages.
        pairs = [(name, value) for name, value in parse_qsl(parsed.query, keep_blank_values=True)
                 if name in {'code', 'state', 'error'}]
        location = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(pairs + [('iss', ISSUER)]), ''))
        return jsonify(redirect=location)

    @blueprint.get(PREFIX + '/resume')
    def resume():
        pending = session.pop(PENDING_KEY, {})
        if not pending or not 0 <= time.time() - pending.get('created', 0) <= 600:
            return 'This sign-in request expired. Return to Nektron Mail and sign in again.', 400
        return redirect(PREFIX + '/authorize?' + urlencode(pending['params']))

    @blueprint.post(PREFIX + '/token')
    def token():
        common = {'grant_type', 'client_id', 'resource', 'scope'}
        kind = request.form.get('grant_type')
        allowed = common | ({'code', 'redirect_uri', 'code_verifier'} if kind == 'authorization_code' else {'refresh_token'})
        if (request.mimetype != 'application/x-www-form-urlencoded' or request.args
                or request.headers.get('Cookie') or request.headers.get('Authorization')
                or kind not in {'authorization_code', 'refresh_token'} or not clean_parameters(request.form, allowed)
                or request.form.get('resource') != RESOURCE or request.form.get('client_id') != CLIENT_ID
                or request.form.get('scope', READ) not in scopes):
            return jsonify(error='invalid_request'), 400
        if kind == 'authorization_code' and (request.form.get('scope', READ) != READ
                or not valid_callback(request.form.get('redirect_uri'))
                or not request.form.get('code')
                or not re.fullmatch(r'[A-Za-z0-9._~-]{43,128}', request.form.get('code_verifier', ''))):
            return jsonify(error='invalid_request'), 400
        if kind == 'refresh_token' and not re.fullmatch(r'[A-Za-z0-9_-]{64}', request.form.get('refresh_token', '')):
            return jsonify(error='invalid_request'), 400
        if limited('token', 120):
            return jsonify(error='temporarily_unavailable'), 429
        return server.create_token_response()

    @blueprint.post(PREFIX + '/revoke')
    def revoke():
        if (request.mimetype != 'application/x-www-form-urlencoded' or request.args
                or request.headers.get('Cookie') or request.headers.get('Authorization')
                or not clean_parameters(request.form, {'client_id', 'token', 'token_type_hint'})
                or request.form.get('client_id') != CLIENT_ID or not request.form.get('token')
                or request.form.get('token_type_hint', 'refresh_token') != 'refresh_token'):
            return jsonify(error='invalid_request'), 400
        if limited('revoke'):
            return jsonify(error='temporarily_unavailable'), 429
        store.revoke(request.form['token'], CLIENT_ID)
        return '', 200

    def authenticate_mail(*, required_scope=None):
        authorization = request.headers.get('Authorization', '')
        if (request.args or request.headers.get('Cookie') or not authorization.startswith('Bearer ')
                or len(authorization) > 8192 or limited('profile', 120)):
            return None
        try:
            raw = authorization[7:]
            # Reject duplicate names/constants before library JSON decoding.
            def unique_object(pairs):
                result = {}
                for name, value in pairs:
                    if name in result:
                        raise ValueError()
                    result[name] = value
                return result
            def invalid_constant(value):
                raise ValueError()
            if not re.fullmatch(r'[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+', raw):
                raise ValueError()
            for part in raw.split('.')[:2]:
                decoded = base64.b64decode(part + '=' * (-len(part) % 4), altchars=b'-_', validate=True)
                if len(decoded) > 6144 or not isinstance(json.loads(decoded, object_pairs_hook=unique_object,
                                                                 parse_constant=invalid_constant), dict):
                    raise ValueError()
            header = jwt.get_unverified_header(raw)
            if header != {'alg': 'RS256', 'kid': kid, 'typ': 'at+jwt'}:
                raise ValueError()
            claims = jwt.decode(raw, key.public_key(), algorithms=['RS256'], issuer=ISSUER, audience=RESOURCE,
                                options={'require': ['iss', 'sub', 'aud', 'iat', 'exp', 'jti', 'client_id', 'scope'],
                                         'strict_aud': True})
            if (claims['client_id'] != CLIENT_ID or claims['scope'] not in scopes
                    or (required_scope is not None and claims['scope'] != required_scope)
                    or not isinstance(claims['sub'], str) or not 1 <= len(claims['sub']) <= 255
                    or any(unicodedata.category(c) in {'Cc', 'Cs'} for c in claims['sub'])
                    or type(claims['iat']) is not int or type(claims['exp']) is not int
                    or not 0 < claims['exp'] - claims['iat'] <= 300
                    or not isinstance(claims['jti'], str) or not 1 <= len(claims['jti']) <= 128):
                raise ValueError()
            if claims['scope'] == KEY_SCOPE and (not isinstance(claims.get('grant_id'), str)
                    or not re.fullmatch(r'[a-f0-9]{48}', claims['grant_id'])):
                raise ValueError()
            member = accounts.get_mail_profile(claims['sub'])
            if not member:
                raise ValueError()
            g.mail_verified_profile = member
        except (jwt.PyJWTError, ValueError, TypeError, KeyError, UnicodeError, RecursionError):
            return None
        return claims

    @blueprint.get(PREFIX + '/profile')
    def profile():
        claims = authenticate_mail()
        if claims is None:
            response = jsonify(error='invalid_token')
            response.headers['WWW-Authenticate'] = 'Bearer error="invalid_token"'
            return response, 401
        member = g.mail_verified_profile
        return jsonify(sub=claims['sub'], email=member['email'], display_name=member['display_name'])

    @blueprint.get(PREFIX + '/consent.js')
    def consent_script():
        response = make_response(CONSENT_JS)
        response.mimetype = 'application/javascript'
        return response

    app.register_blueprint(blueprint)

    def issue_native_tokens(identity, scope=READ):
        user = MailUser(identity['user_id'], identity['auth_tag'])
        refresh = secrets.token_urlsafe(48)
        family = store.create_refresh_family(refresh, {
            'user_id': user.user_id, 'auth_tag': user.auth_tag, 'client_id': CLIENT_ID,
            'resource': RESOURCE, 'scope': scope, 'authentication_flow': NATIVE_FLOW})
        user.grant_id = family
        access = access_token(client, 'first_party_native', user, scope)
        return {'access_token': access, 'refresh_token': refresh, 'expires_in': 300,
                'token_type': 'Bearer', 'scope': scope}

    register_native_session(app, accounts, issuer=ISSUER, client_id=CLIENT_ID,
        resource=RESOURCE, scope=READ, allowed_scopes=scopes,
        login_limited=login_limited, issue_tokens=issue_native_tokens)
    register_archive_keys(app, settings, accounts, authenticate=authenticate_mail, grants=store)


CONSENT = '''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><meta name="referrer" content="no-referrer">
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; form-action 'self'">
<title>Sign in to Nektron Mail | NektronAI</title>
<link rel="stylesheet" href="/assets/styles.css"><link rel="stylesheet" href="/assets/atelier.css">
<link rel="stylesheet" href="/assets/account.css">
<script defer src="/assets/site.js"></script>
<script defer src="/api/account/mail-oauth/consent.js"></script></head>
<body class="atelier-site account-page"><main class="container"><section class="account-shell">
<div class="account-intro"><p class="section-kicker">Your NektronAI account</p>
<h1>Your mail. Your workspace.</h1><p>Sign in to Nektron Mail for Windows with the account you already know.</p></div>
<div class="account-card"><h2>Connect Nektron Mail</h2><p class="account-consent-identity">Continue as <strong>{{ email }}</strong>.</p>
<p>Allow this app to read the email archive your account is authorized to access.
This does not grant permission to send, edit, or delete your mail, or access Database Connector.</p>
<p>Your Windows app keeps its own protected local cache. Disconnecting does not erase that cache.</p>
<form id="consent" class="account-form" data-csrf="{{ csrf }}" data-nonce="{{ nonce }}">
<button class="button primary" type="submit" value="yes">Connect Nektron Mail</button>
<button class="button secondary" type="submit" value="no">Cancel</button></form>
<p id="status" class="account-status" role="status" aria-live="polite"></p>
<p><small>Nektron, Inc. · Only continue if you started this request in Nektron Mail.</small></p>
</div></section></main></body></html>'''

CONSENT_JS = '''const form=document.getElementById('consent');let busy=false;
form.addEventListener('submit',async e=>{e.preventDefault();if(busy)return;busy=true;
form.querySelectorAll('button').forEach(button=>button.disabled=true);
try{const response=await fetch(location.pathname+location.search,{method:'POST',credentials:'same-origin',
headers:{'Content-Type':'application/json','X-CSRF-Token':form.dataset.csrf},
body:JSON.stringify({approve:e.submitter.value==='yes',nonce:form.dataset.nonce}),signal:AbortSignal.timeout(20000)});
const data=await response.json();if(!response.ok||!data.redirect)throw new Error();location.assign(data.redirect);
}catch{document.getElementById('status').textContent='This connection could not finish. Return to Nektron Mail and sign in again.';}
});'''
