"""Nektron login -> explicit OAuth consent -> resource-bound MCP access.

Authlib handles the OAuth grants and PKCE. Credentials never reach ChatGPT.
No dynamic clients, external discovery fetches, or email-based account linking.
"""
import json
import re
import secrets
import time
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

import jwt
from authlib.integrations.flask_oauth2 import AuthorizationServer
from authlib.oauth2.rfc6749 import ClientMixin
from authlib.oauth2.rfc6749.errors import InvalidGrantError, OAuth2Error
from authlib.oauth2.rfc6749.grants import AuthorizationCodeGrant, RefreshTokenGrant
from authlib.oauth2.rfc6750 import BearerTokenGenerator
from authlib.oauth2.rfc7636 import CodeChallenge
from connector_oauth_store import OAuthStore
from cryptography.hazmat.primitives.serialization import load_pem_private_key
from flask import Blueprint, jsonify, make_response, redirect, render_template_string, request, session

ISSUER = 'https://nektron.ai'
PREFIX = '/api/account/oauth'
RESOURCE = 'https://3frqh3q39i.execute-api.us-east-2.amazonaws.com/mcp'
READ = 'database-connector/read'
MANAGE = 'database-connector/manage'
CHATGPT_CLIENT = 'nektron-database-connector-chatgpt'
MANAGEMENT_CLIENT = 'nektron-database-connector-account'
VERIFIED = 'https://nektron.ai/database-connector/email_verified'


def has_connector_database(token):
    """Read the same identity-scoped registry as setup. No database SQL or writes."""
    class NoRedirect(HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None
    req = Request('https://3frqh3q39i.execute-api.us-east-2.amazonaws.com/setup/api/connections',
                  headers={'Authorization': 'Bearer '+token, 'Origin': ISSUER, 'Accept': 'application/json'})
    try:
        with build_opener(NoRedirect).open(req, timeout=8) as response:
            raw = response.read(131073)
        if len(raw) > 131072:
            raise ValueError()
        data = json.loads(raw)
        if not isinstance(data, dict) or not isinstance(data.get('connections'), list):
            raise ValueError()
        return bool(data['connections'])
    except HTTPError as error:
        # New/unapproved accounts go to setup, which enforces enrollment policy.
        # No OAuth code is issued until registry access and a connection exist.
        if error.code == 403:
            return False
        raise RuntimeError('Connection status is temporarily unavailable') from None
    except (URLError, OSError, ValueError):
        raise RuntimeError('Connection status is temporarily unavailable') from None


class Client(ClientMixin):
    def __init__(self, callback, client_id=CHATGPT_CLIENT):
        self.callback, self.client_id = callback, client_id

    def get_client_id(self):
        return self.client_id

    def get_default_redirect_uri(self):
        return None  # An explicit, exact registered redirect is mandatory.

    def get_allowed_scope(self, scope):
        return READ if scope == READ else ''

    def check_redirect_uri(self, value):
        return value == self.callback

    def check_client_secret(self, value):
        return False

    def check_endpoint_auth_method(self, method, endpoint):
        return method == 'none' and endpoint == 'token'

    def check_response_type(self, value):
        return value == 'code'

    def check_grant_type(self, value):
        return value in {'authorization_code', 'refresh_token'}


@dataclass
class User:
    user_id: str
    auth_tag: str


class Credential:
    def __init__(self, data):
        self.data = data
        self.code_challenge = data['code_challenge']
        self.code_challenge_method = 'S256'

    def get_redirect_uri(self):
        return self.data['redirect_uri']

    def get_scope(self):
        return READ

    def check_client(self, client):
        return self.data['client_id'] == client.get_client_id()


def register_connector_oauth(app, settings, accounts, oauth_store=None):
    if settings.get('NEKTRON_CONNECTOR_OAUTH_ENABLED') != 'true':
        return
    if settings.get('NEKTRON_SITE_ORIGIN') != ISSUER:
        raise ValueError('Native connector OAuth requires the canonical Nektron origin')
    callback = settings['NEKTRON_CONNECTOR_CHATGPT_CALLBACK']
    if not re.fullmatch(r'https://chatgpt\.com/(connector/oauth/[A-Za-z0-9_-]+|connector_platform_oauth_redirect)', callback):
        raise ValueError('Use the exact callback shown by ChatGPT')
    key = load_pem_private_key(settings['NEKTRON_CONNECTOR_SIGNING_PEM'].encode(), password=None)
    if getattr(key, 'key_size', 0) < 2048 or not hasattr(key.public_key(), 'public_numbers'):
        raise ValueError('An RSA signing key of at least 2048 bits is required')
    public = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key()))
    kid = settings['NEKTRON_CONNECTOR_SIGNING_KID']
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', kid):
        raise ValueError('Invalid signing key identifier')
    public.update(kid=kid, use='sig', alg='RS256')
    store = oauth_store or OAuthStore(accounts)
    client = Client(callback)
    blueprint = Blueprint('connector_oauth', __name__)

    def current_user():
        uid, tag = session.get('user_id'), session.get('auth_tag')
        if uid and accounts.get_user(uid, tag):
            return User(uid, tag)
        return None

    def access_token(client, grant_type, user, scope):
        if not user or not accounts.get_user(user.user_id, user.auth_tag):
            raise InvalidGrantError()
        now = int(time.time())
        return jwt.encode({'iss': ISSUER, 'sub': user.user_id, 'aud': RESOURCE,
            'iat': now, 'exp': now+300, 'jti': secrets.token_urlsafe(24),
            'client_id': client.get_client_id(), 'scope': scope, VERIFIED: True},
            key, algorithm='RS256', headers={'kid': kid, 'typ': 'at+jwt'})

    def save_token(token, req):
        credential = req.authorization_code if req.payload.grant_type == 'authorization_code' else req.refresh_token
        store.save_refresh(token['refresh_token'], credential.data)

    def database_ready(user):
        return has_connector_database(access_token(Client('', MANAGEMENT_CLIENT), 'native_session', user, MANAGE))

    def setup_redirect(user, params):
        session['connector_oauth_pending'] = {'params': params.to_dict(), 'created': int(time.time()),
                                              'user_id': user.user_id}
        return '/database-connector-setup.html?returnTo=connector-authorize#add'

    server = AuthorizationServer(app, query_client=lambda cid: client if cid == CHATGPT_CLIENT else None,
                                 save_token=save_token)
    server.register_token_generator('default', BearerTokenGenerator(access_token,
        refresh_token_generator=lambda **kwargs: secrets.token_urlsafe(48), expires_generator=lambda *args: 300))

    class CodeGrant(AuthorizationCodeGrant):
        TOKEN_ENDPOINT_AUTH_METHODS = ['none']

        def save_authorization_code(self, code, req):
            store.create_code(code, {'user_id': req.user.user_id, 'auth_tag': req.user.auth_tag,
                'client_id': CHATGPT_CLIENT, 'redirect_uri': req.payload.redirect_uri,
                'code_challenge': req.payload.data['code_challenge']})

        def query_authorization_code(self, code, requesting_client):
            data = store.consume(code, 'code', requesting_client.get_client_id())
            return Credential(data) if data else None

        def delete_authorization_code(self, code):
            pass  # Atomically consumed before exchange; failures cannot replay it.

        def authenticate_user(self, code):
            data = code.data
            return User(data['user_id'], data['auth_tag']) if accounts.get_user(data['user_id'], data['auth_tag']) else None

    class RefreshGrant(RefreshTokenGrant):
        TOKEN_ENDPOINT_AUTH_METHODS = ['none']
        INCLUDE_NEW_REFRESH_TOKEN = True

        def authenticate_refresh_token(self, raw):
            data = store.consume(raw, 'refresh', self.request.client.get_client_id())
            return Credential(data) if data else None

        def authenticate_user(self, credential):
            data = credential.data
            return User(data['user_id'], data['auth_tag']) if accounts.get_user(data['user_id'], data['auth_tag']) else None

        def revoke_old_credential(self, credential):
            pass  # Already atomically consumed; reuse revokes the family.

    class S256(CodeChallenge):
        SUPPORTED_CODE_CHALLENGE_METHOD = ['S256']

    server.register_grant(CodeGrant, [S256(required=True)])
    server.register_grant(RefreshGrant)

    def limited(action, limit=60):
        return not accounts.allow_request('connector:'+action+':'+(request.remote_addr or 'unknown'), limit=limit, seconds=600)

    def clean_parameters(values, allowed):
        return (not set(values)-set(allowed) and all(len(values.getlist(k)) == 1 and
            len(values[k]) <= 2048 and not any(ord(c)<32 for c in values[k]) for k in values))

    @blueprint.get('/.well-known/oauth-authorization-server')
    def metadata():
        return jsonify(issuer=ISSUER, authorization_endpoint=ISSUER+PREFIX+'/authorize',
            token_endpoint=ISSUER+PREFIX+'/token', revocation_endpoint=ISSUER+PREFIX+'/revoke',
            jwks_uri=ISSUER+PREFIX+'/jwks', response_types_supported=['code'],
            grant_types_supported=['authorization_code','refresh_token'],
            token_endpoint_auth_methods_supported=['none'], code_challenge_methods_supported=['S256'],
            scopes_supported=[READ], response_modes_supported=['query'],
            authorization_response_iss_parameter_supported=True)

    @blueprint.get(PREFIX+'/jwks')
    def jwks():
        return jsonify(keys=[public])

    @blueprint.route(PREFIX+'/authorize', methods=['GET','POST'])
    def authorize():
        params = request.args
        allowed = {'client_id','redirect_uri','response_type','scope','state','resource','code_challenge','code_challenge_method','response_mode','ui_locales'}
        if (not clean_parameters(params, allowed) or params.get('resource') != RESOURCE
                or params.get('scope') != READ or params.get('response_type') != 'code'
                or params.get('response_mode', 'query') != 'query' or not params.get('state')
                or (params.get('ui_locales') is not None and (len(params['ui_locales']) > 64 or not re.fullmatch(r'[A-Za-z0-9-]+(?: [A-Za-z0-9-]+)*', params['ui_locales'])))
                or params.get('code_challenge_method') != 'S256'
                or not re.fullmatch(r'[A-Za-z0-9_-]{43}', params.get('code_challenge','')) or limited('authorize')):
            return jsonify(error='invalid_request'), 400
        try:
            server.get_consent_grant(end_user=current_user())
        except OAuth2Error:
            # Never redirect an unvalidated request to a caller-supplied URL.
            return jsonify(error='invalid_request'), 400
        user = current_user()
        if not user:
            session['connector_oauth_pending'] = {'params': params.to_dict(), 'created': int(time.time())}
            return redirect('/login.html?returnTo=connector-authorize')
        if request.method == 'GET':
            try:
                ready = database_ready(user)
            except RuntimeError:
                return jsonify(error='SETUP_UNAVAILABLE', message='Could not check your databases. Retry connecting from ChatGPT.'), 503
            if not ready:
                return redirect(setup_redirect(user, params))
            session['connector_consent'] = {'nonce': secrets.token_urlsafe(32), 'params': params.to_dict(),
                                            'created': int(time.time()), 'user_id': user.user_id}
            session.setdefault('csrf', secrets.token_urlsafe(32))
            return render_template_string(CONSENT, csrf=session['csrf'], nonce=session['connector_consent']['nonce'])
        consent = session.pop('connector_consent', {})
        body = request.get_json(silent=True)
        if (not isinstance(body, dict) or set(body) != {'approve','nonce'} or type(body['approve']) is not bool
                or not consent or body['nonce'] != consent.get('nonce') or consent.get('params') != params.to_dict()
                or consent.get('user_id') != user.user_id or not 0 <= time.time()-consent['created'] <= 600):
            return jsonify(error='invalid_request'), 400
        if body['approve']:
            try:
                ready = database_ready(user)
            except RuntimeError:
                return jsonify(error='SETUP_UNAVAILABLE'), 503
            if not ready:
                return jsonify(redirect=setup_redirect(user, params))
        response = server.create_authorization_response(grant_user=user if body['approve'] else None)
        location = response.headers.get('Location')
        if not location:
            return response
        parsed = urlsplit(location)
        if urlunsplit((parsed.scheme,parsed.netloc,parsed.path,'','')) != callback:
            return jsonify(error='invalid_request'), 400
        pairs = parse_qsl(parsed.query, keep_blank_values=True)
        location = urlunsplit((parsed.scheme,parsed.netloc,parsed.path,urlencode(pairs+[('iss',ISSUER)]),''))
        return jsonify(redirect=location)

    @blueprint.get(PREFIX+'/resume')
    def resume():
        pending = session.pop('connector_oauth_pending', {})
        if not pending or not 0 <= time.time()-pending.get('created',0) <= 600:
            return 'This connection request expired. Return to ChatGPT and connect Database Connector again.', 400
        user = current_user()
        if pending.get('user_id') and (not user or user.user_id != pending['user_id']):
            return 'The signed-in account changed. Restart the connection from ChatGPT.', 400
        return redirect(PREFIX+'/authorize?'+urlencode(pending['params']))

    @blueprint.post(PREFIX+'/token')
    def token():
        allowed = {'grant_type','client_id','code','redirect_uri','code_verifier','resource','refresh_token','scope'}
        if (request.mimetype != 'application/x-www-form-urlencoded' or request.args
                or request.headers.get('Cookie') or request.headers.get('Authorization')
                or not clean_parameters(request.form, allowed) or request.form.get('resource') != RESOURCE
                or request.form.get('client_id') != CHATGPT_CLIENT or limited('token', 120)):
            return jsonify(error='invalid_request'), 400
        return server.create_token_response()

    @blueprint.post(PREFIX+'/cancel-setup')
    def cancel_setup():
        pending = session.get('connector_oauth_pending', {})
        user = current_user()
        if (request.get_json(silent=True) != {} or not user or not pending
                or pending.get('user_id') != user.user_id
                or not 0 <= time.time()-pending.get('created', 0) <= 600):
            return jsonify(error='invalid_request'), 400
        session.pop('connector_oauth_pending', None)
        return jsonify(redirect=callback+'?'+urlencode({'error':'access_denied',
            'state':pending['params']['state'], 'iss':ISSUER}))

    @blueprint.post(PREFIX+'/revoke')
    def revoke():
        if (request.mimetype != 'application/x-www-form-urlencoded' or request.args
                or request.headers.get('Cookie') or not clean_parameters(request.form, {'client_id','token','token_type_hint'})
                or request.form.get('client_id') != CHATGPT_CLIENT or not request.form.get('token') or limited('revoke')):
            return jsonify(error='invalid_request'), 400
        store.revoke(request.form['token'], CHATGPT_CLIENT)
        return '', 200

    @blueprint.post('/api/account/connector-token')
    def management_token():
        user = current_user()
        if not user:
            return jsonify(error='AUTH_REQUIRED'), 401
        if request.get_json(silent=True) != {} or limited('management'):
            return jsonify(error='INVALID_INPUT'), 400
        token = access_token(Client('', MANAGEMENT_CLIENT), 'native_session', user, MANAGE)
        return jsonify(access_token=token, token_type='Bearer', expires_in=300)

    @blueprint.get(PREFIX+'/consent.js')
    def consent_script():
        response = make_response(CONSENT_JS)
        response.mimetype = 'application/javascript'
        return response

    app.register_blueprint(blueprint)


CONSENT = '''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><meta name="referrer" content="no-referrer">
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; form-action 'self'">
<title>Connect ChatGPT · NektronAI</title><link rel="stylesheet" href="/assets/database-connector-setup/app.css">
<script defer src="/api/account/oauth/consent.js"></script></head><body><main>
<p class="eyebrow">NEKTRON, INC.</p><h1>Connect Database Connector to ChatGPT</h1>
<p>Allow ChatGPT to list your connected databases, inspect their permitted tables, and run read-only queries.</p>
<p>Query results are shared with ChatGPT when you use the connector. Database passwords stay with Nektron.</p>
<p>You can revoke this connection. This permission does not allow changing your database connections or billing.</p>
<form id="consent" data-csrf="{{ csrf }}" data-nonce="{{ nonce }}">
<button class="primary" type="submit" value="yes">Allow connection</button>
<button class="secondary" type="submit" value="no">Cancel</button></form>
<p id="status" role="status"></p></main></body></html>'''

CONSENT_JS = '''const form=document.getElementById('consent');let busy=false;
form.addEventListener('submit',async e=>{e.preventDefault();if(busy)return;busy=true;
try{const response=await fetch(location.pathname+location.search,{method:'POST',credentials:'same-origin',
headers:{'Content-Type':'application/json','X-CSRF-Token':form.dataset.csrf},
body:JSON.stringify({approve:e.submitter.value==='yes',nonce:form.dataset.nonce})});
const result=await response.json();if(!response.ok||!result.redirect)throw Error();
location.assign(result.redirect);}catch{document.getElementById('status').textContent='The connection could not be completed. Restart the connection from ChatGPT.';}finally{busy=false;}});'''
