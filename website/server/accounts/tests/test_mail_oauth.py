"""Synthetic native authorization tests: no AWS, mail delivery, or live database."""
import base64
import copy
import hashlib
import re
import secrets
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlencode, urlsplit

import jwt
from authlib.oauth2.rfc6749.errors import InvalidGrantError
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import COOKIE, create_app
from credentials import password_hash
from mail_oauth import CLIENT_ID, CONSENT_KEY, ISSUER, PENDING_KEY, PREFIX, READ, RESOURCE, valid_callback
from test_accounts import CaptureMailer, EMAIL, MemoryStore, PASSWORD, SETTINGS

CALLBACK = 'http://127.0.0.1:54321/nektron-mail/callback'
VERIFIER = 'v' * 64
CHALLENGE = base64.urlsafe_b64encode(hashlib.sha256(VERIFIER.encode()).digest()).rstrip(b'=').decode()


class ProfileStore(MemoryStore):
    def get_mail_profile(self, user_id):
        for user in self.users.values():
            if user['UserId'] == user_id and user['AccountStatus'] == 'active' and user['EmailVerified'] == 1:
                return {'email': user['Email'], 'display_name': 'Test Member'}
        return None


class MemoryOAuthStore:
    """Same client-qualified consume/rotate/replay contract as OAuthStore."""
    def __init__(self):
        self.credentials, self.families = {}, {}

    def create_code(self, raw, data):
        family = secrets.token_hex(24)
        self.families[family] = {'client': data['client_id'], 'revoked': False, 'expires': time.time() + 30 * 86400}
        self.credentials[hashlib.sha256(raw.encode()).hexdigest()] = {
            'kind': 'code', 'used': False, 'expires': time.time() + 120, 'data': dict(data, family=family)}

    def consume(self, raw, kind, client_id):
        row = self.credentials.get(hashlib.sha256(raw.encode()).hexdigest())
        if not row or row['kind'] != kind:
            return None
        family = self.families[row['data']['family']]
        if family['client'] != client_id or family['revoked'] or family['expires'] <= time.time():
            return None
        if row['used']:
            family['revoked'] = True
            return None
        if row['expires'] <= time.time():
            return None
        row['used'] = True
        return dict(row['data'], expires=family['expires'])

    def save_refresh(self, raw, data):
        family = self.families[data['family']]
        if family['revoked'] or family['expires'] <= time.time() or family['client'] != data['client_id']:
            raise InvalidGrantError()
        self.credentials[hashlib.sha256(raw.encode()).hexdigest()] = {
            'kind': 'refresh', 'used': False, 'expires': family['expires'], 'data': copy.deepcopy(data)}

    def revoke(self, raw, client_id):
        row = self.credentials.get(hashlib.sha256(raw.encode()).hexdigest())
        if row and self.families[row['data']['family']]['client'] == client_id:
            self.families[row['data']['family']]['revoked'] = True


def pem(key):
    return key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()).decode()


class MailOAuthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.connector_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.hashed = password_hash(PASSWORD)
        cls.settings = {**SETTINGS, 'NEKTRON_MAIL_OAUTH_ENABLED': 'true',
                        'NEKTRON_MAIL_SIGNING_PEM': pem(cls.key), 'NEKTRON_MAIL_SIGNING_KID': 'mail-test-key'}

    def setUp(self):
        self.accounts, self.oauth = ProfileStore(), MemoryOAuthStore()
        self.accounts.users[EMAIL] = {'UserId': 'native:test-subject', 'Email': EMAIL, 'PasswordHash': self.hashed,
            'FirstName': 'Test', 'LastName': 'Member', 'MiddleName': '', 'CountryCode': 'US',
            'PhoneNumber': '', 'Role': 'user', 'AccountStatus': 'active', 'EmailVerified': 1}
        self.patcher = patch('mail_oauth.OAuthStore', return_value=self.oauth)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        self.app = create_app(self.settings, self.accounts, CaptureMailer())
        self.app.testing = True
        self.browser = self.app.test_client()
        self.desktop = self.app.test_client(use_cookies=False)
        self.params = {'client_id': CLIENT_ID, 'redirect_uri': CALLBACK, 'response_type': 'code', 'scope': READ,
            'resource': RESOURCE, 'state': 'test-state-' + secrets.token_urlsafe(32),
            'code_challenge': CHALLENGE, 'code_challenge_method': 'S256'}

    def login(self):
        csrf = self.browser.get('/api/account/csrf', base_url=ISSUER).json['csrfToken']
        return self.browser.post('/api/account/login', base_url=ISSUER,
            json={'email': EMAIL, 'password': PASSWORD}, headers={'Origin': ISSUER, 'X-CSRF-Token': csrf})

    def authorize(self, params=None, approve=True):
        params = self.params if params is None else params
        url = PREFIX + '/authorize?' + urlencode(params)
        response = self.browser.get(url, base_url=ISSUER)
        self.assertEqual(response.status_code, 200, response.text)
        nonce = re.search(r'data-nonce="([^"]+)"', response.text)[1]
        csrf = re.search(r'data-csrf="([^"]+)"', response.text)[1]
        response = self.browser.post(url, base_url=ISSUER, json={'approve': approve, 'nonce': nonce},
                                     headers={'Origin': ISSUER, 'X-CSRF-Token': csrf})
        self.assertEqual(response.status_code, 200, response.text)
        return parse_qs(urlsplit(response.json['redirect']).query)

    def exchange(self, code, **overrides):
        fields = {'grant_type': 'authorization_code', 'client_id': CLIENT_ID, 'redirect_uri': CALLBACK,
                  'resource': RESOURCE, 'code': code, 'code_verifier': VERIFIER}
        fields.update(overrides)
        return self.desktop.post(PREFIX + '/token', base_url=ISSUER, data=fields)

    def tokens(self):
        self.assertEqual(self.login().status_code, 200)
        result = self.exchange(self.authorize()['code'][0])
        self.assertEqual(result.status_code, 200, result.text)
        return result.json

    def refresh(self, raw, **overrides):
        return self.desktop.post(PREFIX + '/token', base_url=ISSUER, data={
            'grant_type': 'refresh_token', 'client_id': CLIENT_ID, 'resource': RESOURCE, 'refresh_token': raw, **overrides})

    def profile(self, raw):
        return self.desktop.get(PREFIX + '/profile', base_url=ISSUER, headers={'Authorization': 'Bearer ' + raw})

    def claims(self, raw):
        return jwt.decode(raw, self.key.public_key(), algorithms=['RS256'], issuer=ISSUER, audience=RESOURCE)

    def test_public_client_code_exchange_profile_and_minimal_claims(self):
        token = self.tokens()
        self.assertEqual(token['token_type'], 'Bearer')
        self.assertEqual(token['expires_in'], 300)
        self.assertEqual(token['scope'], READ)
        claims = self.claims(token['access_token'])
        self.assertEqual(claims['sub'], 'native:test-subject')
        self.assertEqual(claims['client_id'], CLIENT_ID)
        self.assertEqual(claims['exp'] - claims['iat'], 300)
        self.assertEqual(set(claims), {'iss', 'sub', 'aud', 'iat', 'exp', 'jti', 'client_id', 'scope'})
        self.assertEqual(jwt.get_unverified_header(token['access_token']),
                         {'alg': 'RS256', 'typ': 'at+jwt', 'kid': 'mail-test-key'})
        result = self.profile(token['access_token'])
        self.assertEqual(result.json, {'sub': 'native:test-subject', 'email': EMAIL, 'display_name': 'Test Member'})
        self.assertNotIn('Set-Cookie', result.headers)
        self.assertEqual(result.headers['Cache-Control'], 'no-store')
        self.assertNotIn('id_token', token)

    def test_only_public_key_is_exposed(self):
        result = self.desktop.get(PREFIX + '/jwks', base_url=ISSUER)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(set(result.json['keys'][0]), {'kty', 'n', 'e', 'kid', 'use', 'alg', 'key_ops'})
        self.assertEqual(result.json['keys'][0]['key_ops'], ['verify'])

    def test_callback_validator_is_literal_and_bounded(self):
        for port in (1024, 12345, 65535):
            self.assertTrue(valid_callback(f'http://127.0.0.1:{port}/nektron-mail/callback'))
        for callback in (None, '', CALLBACK + '?x=1', CALLBACK + '#x', CALLBACK + '/', CALLBACK.replace('http:', 'https:'),
                         CALLBACK.replace('127.0.0.1', 'localhost'), CALLBACK.replace('127.0.0.1', '[::1]'),
                         CALLBACK.replace('127.0.0.1', 'user@127.0.0.1'), CALLBACK.replace('54321', '054321'),
                         CALLBACK.replace('54321', '0'), CALLBACK.replace('54321', '1023'), CALLBACK.replace('54321', '65536'),
                         CALLBACK.replace('127.0.0.1', '127.000.0.1'), CALLBACK.replace('/callback', '/%63allback')):
            with self.subTest(callback=callback):
                self.assertFalse(valid_callback(callback))
                response = self.browser.get(PREFIX + '/authorize', base_url=ISSUER,
                                            query_string={**self.params, 'redirect_uri': callback or ''})
                self.assertEqual(response.status_code, 400)
                self.assertNotIn('Location', response.headers)
                self.assertFalse(self.accounts.sessions)

    def test_bad_authorization_parameters_never_redirect_or_save_pending(self):
        for key, value in [('client_id', 'other'), ('resource', RESOURCE + '/'), ('scope', READ + ' openid'),
                           ('state', ''), ('state', '\x7f'), ('response_type', 'token'), ('code_challenge_method', 'plain'),
                           ('code_challenge', 'short'), ('response_mode', 'fragment'), ('screen', 'other'), ('extra', 'bad')]:
            with self.subTest(key=key, value=value):
                response = self.browser.get(PREFIX + '/authorize', base_url=ISSUER,
                                            query_string={**self.params, key: value})
                self.assertEqual(response.status_code, 400)
                self.assertNotIn('Location', response.headers)
                self.assertFalse(self.accounts.sessions)
        response = self.browser.get(PREFIX + '/authorize?' + urlencode(self.params) + '&state=other', base_url=ISSUER)
        self.assertEqual(response.status_code, 400)

    def test_login_rotates_session_and_preserves_both_product_pending_requests(self):
        result = self.browser.get(PREFIX + '/authorize', base_url=ISSUER, query_string=self.params)
        self.assertEqual(result.location, '/login.html?returnTo=mail-authorize')
        old_cookie = self.browser.get_cookie(COOKIE, domain='nektron.ai').value
        record = self.accounts.sessions[hashlib.sha256(old_cookie.encode()).hexdigest()][0]
        record['connector_oauth_pending'] = {'params': {'synthetic': 'connector'}, 'created': int(time.time())}
        record[CONSENT_KEY] = {'nonce': 'must-not-survive-login'}
        self.assertEqual(self.login().status_code, 200)
        new_cookie = self.browser.get_cookie(COOKIE, domain='nektron.ai').value
        self.assertNotEqual(old_cookie, new_cookie)
        current = self.accounts.sessions[hashlib.sha256(new_cookie.encode()).hexdigest()][0]
        self.assertIn(PENDING_KEY, current)
        self.assertIn('connector_oauth_pending', current)
        self.assertNotIn(CONSENT_KEY, current)
        resumed = self.browser.get(PREFIX + '/resume', base_url=ISSUER)
        self.assertEqual(parse_qs(urlsplit(resumed.location).query)['state'], [self.params['state']])
        self.assertEqual(self.browser.get(resumed.location, base_url=ISSUER).status_code, 200)
        self.assertEqual(self.browser.get(PREFIX + '/resume', base_url=ISSUER).status_code, 400)

    def test_signup_entry_and_expired_pending(self):
        result = self.browser.get(PREFIX + '/authorize', base_url=ISSUER, query_string={**self.params, 'screen': 'signup'})
        self.assertEqual(result.location, '/signup.html?returnTo=mail-authorize')
        cookie = self.browser.get_cookie(COOKIE, domain='nektron.ai').value
        pending = self.accounts.sessions[hashlib.sha256(cookie.encode()).hexdigest()][0][PENDING_KEY]
        pending['created'] = int(time.time()) - 601
        self.assertEqual(self.login().status_code, 200)
        self.assertEqual(self.browser.get(PREFIX + '/resume', base_url=ISSUER).status_code, 400)

    def test_login_provides_only_fixed_mail_fallback_for_new_verification_tab(self):
        self.browser.get(PREFIX + '/authorize', base_url=ISSUER, query_string={**self.params, 'screen': 'signup'})
        self.assertEqual(self.login().json['redirect'], PREFIX + '/resume')
        self.browser.get(PREFIX + '/resume', base_url=ISSUER)
        self.assertEqual(self.login().json['redirect'], '/account.html')

    def test_rate_limits_fail_closed_before_credentials_are_consumed(self):
        token = self.tokens()
        self.accounts.allow = False
        self.assertEqual(self.refresh(token['refresh_token']).status_code, 429)
        self.assertEqual(self.desktop.post(PREFIX + '/revoke', base_url=ISSUER,
            data={'client_id': CLIENT_ID, 'token': token['refresh_token']}).status_code, 429)
        self.assertEqual(self.profile(token['access_token']).status_code, 401)
        self.assertEqual(self.browser.get(PREFIX + '/authorize', base_url=ISSUER, query_string=self.params).status_code, 429)
        self.accounts.allow = True
        self.assertEqual(self.refresh(token['refresh_token']).status_code, 200)

    def test_consent_is_explicit_one_use_and_state_bound(self):
        self.login()
        url = PREFIX + '/authorize?' + urlencode(self.params)
        response = self.browser.get(url, base_url=ISSUER)
        body = {'approve': True, 'nonce': re.search(r'data-nonce="([^"]+)"', response.text)[1]}
        headers = {'Origin': ISSUER, 'X-CSRF-Token': re.search(r'data-csrf="([^"]+)"', response.text)[1]}
        changed = PREFIX + '/authorize?' + urlencode({**self.params, 'state': 'changed'})
        self.assertEqual(self.browser.post(changed, base_url=ISSUER, json=body, headers=headers).status_code, 400)
        self.assertEqual(self.browser.post(url, base_url=ISSUER, json=body, headers=headers).status_code, 400)
        self.assertFalse(self.oauth.credentials)

    def test_consent_requires_website_origin_and_csrf(self):
        self.login()
        url = PREFIX + '/authorize?' + urlencode(self.params)
        for headers in ({}, {'Origin': 'https://evil.example'}, {'Origin': ISSUER, 'X-CSRF-Token': 'wrong'}):
            response = self.browser.post(url, base_url=ISSUER, json={'approve': True, 'nonce': 'wrong'}, headers=headers)
            self.assertEqual(response.status_code, 403)
        self.assertFalse(self.oauth.credentials)

    def test_cancel_returns_minimal_state_bound_denial(self):
        self.login()
        result = self.authorize(approve=False)
        self.assertEqual(result, {'error': ['access_denied'], 'state': [self.params['state']], 'iss': [ISSUER]})
        self.assertFalse(self.oauth.credentials)

    def test_exact_redirect_port_bound_to_grant(self):
        self.login()
        code = self.authorize()['code'][0]
        self.assertEqual(self.exchange(code, redirect_uri=CALLBACK.replace('54321', '54322')).status_code, 400)
        self.assertEqual(self.exchange(code).status_code, 400)

    def test_wrong_pkce_cannot_be_retried(self):
        self.login()
        code = self.authorize()['code'][0]
        self.assertEqual(self.exchange(code, code_verifier='w' * 64).status_code, 400)
        self.assertEqual(self.exchange(code).status_code, 400)

    def test_code_replay_revokes_existing_refresh_family(self):
        self.login()
        code = self.authorize()['code'][0]
        token = self.exchange(code).json
        self.assertEqual(self.exchange(code).status_code, 400)
        self.assertEqual(self.refresh(token['refresh_token']).status_code, 400)

    def test_refresh_rotates_and_replay_revokes_descendants(self):
        first = self.tokens()
        second = self.refresh(first['refresh_token'])
        self.assertEqual(second.status_code, 200, second.text)
        self.assertNotEqual(first['refresh_token'], second.json['refresh_token'])
        self.assertNotEqual(first['access_token'], second.json['access_token'])
        self.assertEqual(self.refresh(first['refresh_token']).status_code, 400)
        self.assertEqual(self.refresh(second.json['refresh_token']).status_code, 400)

    def test_refresh_resource_scope_and_client_cannot_expand(self):
        token = self.tokens()
        for overrides in ({'client_id': 'nektron-database-connector-chatgpt'}, {'scope': READ + ' openid'},
                          {'resource': RESOURCE + '/other'}, {'scope': ''}):
            self.assertEqual(self.refresh(token['refresh_token'], **overrides).status_code, 400)
        self.assertEqual(self.refresh(token['refresh_token'], scope=READ).status_code, 200)

    def test_stored_grant_resource_binding_is_checked(self):
        token = self.tokens()
        row = self.oauth.credentials[hashlib.sha256(token['refresh_token'].encode()).hexdigest()]
        row['data']['resource'] = 'https://other.example'
        self.assertEqual(self.refresh(token['refresh_token']).status_code, 400)

    def test_credentials_are_not_raw_store_keys(self):
        token = self.tokens()
        self.assertNotIn(token['refresh_token'], str(self.oauth.credentials))
        self.assertNotIn(token['access_token'], str(self.oauth.credentials))

    def test_expired_code_and_expired_family_fail(self):
        self.login()
        code = self.authorize()['code'][0]
        self.oauth.credentials[hashlib.sha256(code.encode()).hexdigest()]['expires'] = time.time() - 1
        self.assertEqual(self.exchange(code).status_code, 400)
        code = self.authorize()['code'][0]
        token = self.exchange(code).json
        for family in self.oauth.families.values():
            family['expires'] = time.time() - 1
        self.assertEqual(self.refresh(token['refresh_token']).status_code, 400)

    def test_revoke_is_idempotent_and_client_qualified(self):
        token = self.tokens()
        self.oauth.revoke(token['refresh_token'], 'nektron-database-connector-chatgpt')
        rotated = self.refresh(token['refresh_token']).json['refresh_token']
        for raw in (rotated, rotated, 'unknown'):
            result = self.desktop.post(PREFIX + '/revoke', base_url=ISSUER, data={'client_id': CLIENT_ID, 'token': raw})
            self.assertEqual(result.status_code, 200)
        self.assertEqual(self.refresh(rotated).status_code, 400)

    def test_code_refresh_recheck_password_and_account_state(self):
        self.login()
        for field, value in (('AccountStatus', 'disabled'), ('AccountStatus', 'pending'), ('EmailVerified', 0),
                             ('PasswordHash', self.hashed + 'changed')):
            with self.subTest(field=field, value=value):
                original = self.accounts.users[EMAIL][field]
                code = self.authorize()['code'][0]
                self.accounts.users[EMAIL][field] = value
                self.assertEqual(self.exchange(code).status_code, 400)
                self.accounts.users[EMAIL][field] = original
                token = self.exchange(self.authorize()['code'][0]).json
                self.accounts.users[EMAIL][field] = value
                self.assertEqual(self.refresh(token['refresh_token']).status_code, 400)
                self.accounts.users[EMAIL][field] = original

    def test_profile_rechecks_active_verified_account(self):
        token = self.tokens()['access_token']
        for field, value in (('AccountStatus', 'disabled'), ('AccountStatus', 'locked'), ('AccountStatus', 'pending'), ('EmailVerified', 0)):
            original = self.accounts.users[EMAIL][field]
            self.accounts.users[EMAIL][field] = value
            self.assertEqual(self.profile(token).status_code, 401)
            self.accounts.users[EMAIL][field] = original

    def test_profile_rejects_wrong_audience_client_scope_signature_and_lifetime(self):
        token = self.tokens()['access_token']
        claims = self.claims(token)
        invalid = [{'aud': [RESOURCE]}, {'aud': 'https://other.example'}, {'client_id': 'other'}, {'scope': 'openid'},
                   {'exp': claims['iat'] + 301}, {'iat': str(claims['iat'])}, {'sub': ''}, {'sub': 123},
                   {'exp': int(time.time()) - 1}, {'jti': ''}]
        for override in invalid:
            raw = jwt.encode({**claims, **override}, self.key, algorithm='RS256', headers={'kid': 'mail-test-key', 'typ': 'at+jwt'})
            self.assertEqual(self.profile(raw).status_code, 401, str(override))
        for header in ({'kid': 'other', 'typ': 'at+jwt'}, {'kid': 'mail-test-key', 'typ': 'JWT'},
                       {'kid': 'mail-test-key', 'typ': 'at+jwt', 'jku': 'https://untrusted.example'}):
            raw = jwt.encode(claims, self.key, algorithm='RS256', headers=header)
            self.assertEqual(self.profile(raw).status_code, 401)
        wrong_key = jwt.encode(claims, self.connector_key, algorithm='RS256', headers={'kid': 'mail-test-key', 'typ': 'at+jwt'})
        self.assertEqual(self.profile(wrong_key).status_code, 401)

    def test_native_endpoints_reject_ambient_cookies_and_auth_headers(self):
        token = self.tokens()
        for suffix, fields in [('token', {'grant_type': 'refresh_token', 'client_id': CLIENT_ID, 'resource': RESOURCE,
                                         'refresh_token': token['refresh_token']}),
                               ('revoke', {'client_id': CLIENT_ID, 'token': token['refresh_token']})]:
            self.assertEqual(self.browser.post(PREFIX + '/' + suffix, base_url=ISSUER, data=fields).status_code, 400)
            self.assertEqual(self.desktop.post(PREFIX + '/' + suffix, base_url=ISSUER, data=fields,
                                              headers={'Authorization': 'Basic invalid'}).status_code, 400)
        self.assertEqual(self.browser.get(PREFIX + '/profile', base_url=ISSUER,
                                         headers={'Authorization': 'Bearer ' + token['access_token']}).status_code, 401)

    def test_duplicate_token_parameters_and_extra_fields_fail(self):
        token = self.tokens()
        fields = {'grant_type': 'refresh_token', 'client_id': CLIENT_ID, 'resource': RESOURCE, 'refresh_token': token['refresh_token']}
        for body in (urlencode(fields) + '&resource=' + RESOURCE, urlencode({**fields, 'client_secret': 'no'}),
                     urlencode({**fields, 'code': 'mixed-grant'})):
            response = self.desktop.post(PREFIX + '/token', base_url=ISSUER, data=body,
                                         content_type='application/x-www-form-urlencoded')
            self.assertEqual(response.status_code, 400)

    def test_signing_is_disabled_by_default_and_bad_configuration_fails(self):
        app = create_app(SETTINGS, self.accounts, CaptureMailer())
        self.assertEqual(app.test_client().get(PREFIX + '/jwks', base_url=ISSUER).status_code, 404)
        for overrides in ({'NEKTRON_SITE_ORIGIN': 'https://other.example'}, {'NEKTRON_ACCOUNT_ENABLED': 'false'},
                          {'NEKTRON_MAIL_SIGNING_KID': '../bad'}, {'NEKTRON_CONNECTOR_SIGNING_PEM': pem(self.key)},
                          {'NEKTRON_CONNECTOR_SIGNING_KID': 'mail-test-key'}):
            with self.assertRaises(ValueError):
                create_app({**self.settings, **overrides}, self.accounts, CaptureMailer())

    def test_both_oauth_products_keep_independent_servers_keys_and_permissions(self):
        from connector_oauth import CHATGPT_CLIENT, PREFIX as CPREFIX, READ as CREAD, RESOURCE as CRESOURCE
        callback = 'https://chatgpt.com/connector/oauth/synthetic_test'
        settings = {**self.settings, 'NEKTRON_CONNECTOR_OAUTH_ENABLED': 'true',
                    'NEKTRON_CONNECTOR_CHATGPT_CALLBACK': callback,
                    'NEKTRON_CONNECTOR_SIGNING_PEM': pem(self.connector_key), 'NEKTRON_CONNECTOR_SIGNING_KID': 'connector-test-key'}
        with patch('connector_oauth.OAuthStore', return_value=self.oauth), patch('connector_oauth.has_connector_database', return_value=True):
            self.app = create_app(settings, self.accounts, CaptureMailer())
            self.app.testing = True
            self.browser, self.desktop = self.app.test_client(), self.app.test_client(use_cookies=False)
            mail_token = self.tokens()
            params = {**self.params, 'client_id': CHATGPT_CLIENT, 'redirect_uri': callback, 'resource': CRESOURCE, 'scope': CREAD}
            url = CPREFIX + '/authorize?' + urlencode(params)
            response = self.browser.get(url, base_url=ISSUER)
            self.assertEqual(response.status_code, 200, response.text)
            nonce = re.search(r'data-nonce="([^"]+)"', response.text)[1]
            csrf = re.search(r'data-csrf="([^"]+)"', response.text)[1]
            response = self.browser.post(url, base_url=ISSUER, json={'approve': True, 'nonce': nonce},
                                         headers={'Origin': ISSUER, 'X-CSRF-Token': csrf})
            code = parse_qs(urlsplit(response.json['redirect']).query)['code'][0]
            response = self.desktop.post(CPREFIX + '/token', base_url=ISSUER, data={
                'grant_type': 'authorization_code', 'client_id': CHATGPT_CLIENT, 'resource': CRESOURCE,
                'code': code, 'redirect_uri': callback, 'code_verifier': VERIFIER})
            self.assertEqual(response.status_code, 200, response.text)
            claims = jwt.decode(response.json['access_token'], self.connector_key.public_key(),
                                algorithms=['RS256'], issuer=ISSUER, audience=CRESOURCE)
            self.assertEqual(claims['client_id'], CHATGPT_CLIENT)
            self.assertEqual(claims['scope'], CREAD)
            self.assertEqual(self.profile(response.json['access_token']).status_code, 401)
            self.assertEqual(self.profile(mail_token['access_token']).status_code, 200)
            for prefix, kid in ((PREFIX, 'mail-test-key'), (CPREFIX, 'connector-test-key')):
                self.assertEqual(self.desktop.get(prefix + '/jwks', base_url=ISSUER).json['keys'][0]['kid'], kid)
            self.assertEqual(self.refresh(mail_token['refresh_token']).status_code, 200)


if __name__ == '__main__':
    unittest.main()
