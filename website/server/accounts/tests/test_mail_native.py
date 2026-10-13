"""Synthetic first-party Mail sign-in: no live accounts, SQL, AWS or email."""
import copy
import hashlib
import json
import secrets
import sys
import time
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import jwt
from authlib.oauth2.rfc6749.errors import InvalidGrantError
from cryptography.hazmat.primitives.asymmetric import rsa

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import COOKIE, create_app
from connector_oauth_store import OAuthStore, digest
from credentials import credential_tag, password_hash
from mail_native import NATIVE_FLOW, NATIVE_SESSION_PATH
from mail_oauth import CLIENT_ID, ISSUER, PREFIX, READ, RESOURCE
from test_accounts import CaptureMailer, EMAIL, PASSWORD, SETTINGS
from test_mail_oauth import MemoryOAuthStore, ProfileStore, pem


class NativeMemoryOAuthStore(MemoryOAuthStore):
    def __init__(self, accounts):
        super().__init__()
        self.accounts = accounts

    def create_refresh_family(self, raw, data):
        if not self.accounts.get_user(data['user_id'], data['auth_tag']):
            raise InvalidGrantError()
        family = secrets.token_hex(24)
        self.families[family] = {'client': data['client_id'], 'revoked': False, 'expires': time.time() + 30*86400}
        self.save_refresh(raw, dict(data, family=family))


class MailNativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.hashed = password_hash(PASSWORD)
        cls.settings = {**SETTINGS, 'NEKTRON_MAIL_OAUTH_ENABLED': 'true',
                        'NEKTRON_MAIL_SIGNING_PEM': pem(cls.key), 'NEKTRON_MAIL_SIGNING_KID': 'native-mail-test'}

    def setUp(self):
        self.accounts = ProfileStore()
        self.accounts.users[EMAIL] = {'UserId': 'native:synthetic-mail-user', 'Email': EMAIL,
            'PasswordHash': self.hashed, 'FirstName': 'Test', 'LastName': 'Member',
            'AccountStatus': 'active', 'EmailVerified': 1}
        self.oauth, self.mailer = NativeMemoryOAuthStore(self.accounts), CaptureMailer()
        patcher = patch('mail_oauth.OAuthStore', return_value=self.oauth)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.app = create_app(self.settings, self.accounts, self.mailer)
        self.app.testing = True
        self.desktop = self.app.test_client(use_cookies=False)
        self.body = {'email': EMAIL, 'password': PASSWORD, 'client_id': CLIENT_ID,
                     'resource': RESOURCE, 'scope': READ, 'approve': True}

    def sign_in(self, **changes):
        return self.desktop.post(NATIVE_SESSION_PATH, base_url=ISSUER, json={**self.body, **changes})

    def refresh(self, raw, **changes):
        return self.desktop.post(PREFIX + '/token', base_url=ISSUER, data={
            'grant_type': 'refresh_token', 'client_id': CLIENT_ID, 'resource': RESOURCE,
            'refresh_token': raw, **changes})

    def row(self, raw):
        return self.oauth.credentials[hashlib.sha256(raw.encode()).hexdigest()]

    def test_native_session_has_minimal_signed_mail_claims_and_profile(self):
        response = self.sign_in()
        self.assertEqual(response.status_code, 200, response.text)
        token = response.json
        self.assertEqual(set(token), {'access_token', 'refresh_token', 'expires_in', 'token_type', 'scope'})
        self.assertEqual((token['expires_in'], token['token_type'], token['scope']), (300, 'Bearer', READ))
        self.assertRegex(token['refresh_token'], r'^[A-Za-z0-9_-]{64}$')
        self.assertEqual(jwt.get_unverified_header(token['access_token']),
                         {'alg': 'RS256', 'kid': 'native-mail-test', 'typ': 'at+jwt'})
        claims = jwt.decode(token['access_token'], self.key.public_key(), algorithms=['RS256'],
                            audience=RESOURCE, issuer=ISSUER)
        self.assertEqual(set(claims), {'iss', 'sub', 'aud', 'iat', 'exp', 'jti', 'client_id', 'scope'})
        self.assertEqual(claims['sub'], self.accounts.users[EMAIL]['UserId'])
        self.assertEqual(claims['exp'] - claims['iat'], 300)
        profile = self.desktop.get(PREFIX + '/profile', base_url=ISSUER,
                                  headers={'Authorization': 'Bearer ' + token['access_token']})
        self.assertEqual(profile.status_code, 200)
        self.assertEqual(profile.json['email'], EMAIL)
        self.assertEqual(response.headers['Cache-Control'], 'no-store')
        self.assertEqual(response.headers['X-Content-Type-Options'], 'nosniff')
        self.assertEqual(response.headers['Referrer-Policy'], 'no-referrer')
        self.assertNotIn('Set-Cookie', response.headers)
        self.assertFalse(self.accounts.sessions)
        self.assertFalse(self.mailer.sent)
        data = self.row(token['refresh_token'])['data']
        self.assertEqual(data['authentication_flow'], NATIVE_FLOW)
        self.assertNotIn('redirect_uri', data)
        self.assertNotIn('code_challenge', data)
        self.assertNotIn(token['refresh_token'], str(self.oauth.credentials))
        self.assertNotIn(PASSWORD, str(self.oauth.credentials))
        self.assertNotIn(self.hashed, str(self.oauth.credentials))

    def test_refresh_rotates_preserves_native_marker_and_replay_revokes_family(self):
        first = self.sign_in().json
        second = self.refresh(first['refresh_token'])
        self.assertEqual(second.status_code, 200, second.text)
        self.assertNotEqual(first['refresh_token'], second.json['refresh_token'])
        self.assertEqual(self.row(second.json['refresh_token'])['data']['authentication_flow'], NATIVE_FLOW)
        self.assertEqual(self.refresh(first['refresh_token']).status_code, 400)
        self.assertEqual(self.refresh(second.json['refresh_token']).status_code, 400)

    def test_native_family_revocation_is_idempotent_and_client_qualified(self):
        token = self.sign_in().json['refresh_token']
        self.oauth.revoke(token, 'nektron-database-connector-chatgpt')
        rotated = self.refresh(token).json['refresh_token']
        for raw in (rotated, rotated, 'unknown'):
            response = self.desktop.post(PREFIX + '/revoke', base_url=ISSUER,
                                         data={'client_id': CLIENT_ID, 'token': raw})
            self.assertEqual(response.status_code, 200)
        self.assertEqual(self.refresh(rotated).status_code, 400)

    def test_native_refresh_family_expiry_is_not_extended_by_rotation(self):
        token = self.sign_in().json['refresh_token']
        data = self.row(token)['data']
        family = self.oauth.families[data['family']]
        expiry = family['expires']
        self.assertAlmostEqual(expiry, time.time() + 30*86400, delta=5)
        second = self.refresh(token).json['refresh_token']
        self.assertEqual(self.row(second)['expires'], expiry)
        family['expires'] = time.time() - 1
        self.assertEqual(self.refresh(second).status_code, 400)

    def test_unknown_wrong_disabled_unverified_all_have_identical_error(self):
        expected = {'error': 'INVALID_CREDENTIALS'}
        cases = [({'email': 'missing@example.com'}, {}), ({'password': PASSWORD + '!'}, {}),
                 ({}, {'AccountStatus': 'disabled'}), ({}, {'AccountStatus': 'pending'}),
                 ({}, {'EmailVerified': 0}), ({}, {'AccountStatus': 'locked'}),
                 ({}, {'PasswordHash': 'not-an-argon2-hash'})]
        original = copy.deepcopy(self.accounts.users[EMAIL])
        for body, account in cases:
            with self.subTest(case=(body.keys(), account)):
                self.accounts.users[EMAIL] = {**original, **account}
                response = self.sign_in(**body)
                self.assertEqual((response.status_code, response.json), (401, expected))
                self.assertNotIn('Set-Cookie', response.headers)
        self.assertFalse(self.oauth.credentials)
        self.assertFalse(self.oauth.families)

    def test_credential_input_validation_remains_bounded(self):
        for change in ({'email': None}, {'email': []}, {'email': 'bad'}, {'password': None},
                       {'password': ''}, {'password': '  '}, {'password': ['secret']},
                       {'password': 'x'*1025}, {'password': '\ud800'}):
            with self.subTest(field=next(iter(change))):
                response = self.sign_in(**change)
                self.assertEqual((response.status_code, response.json), (401, {'error': 'INVALID_CREDENTIALS'}))
        self.assertFalse(self.oauth.families)

    def test_exact_client_resource_scope_and_explicit_boolean_approval(self):
        for change in ({'client_id': 'nektron-database-connector-chatgpt'}, {'resource': RESOURCE + '/'},
                       {'scope': READ + ' mail/send'}, {'approve': False}, {'approve': 1},
                       {'approve': 'true'}, {'client_id': []}, {'resource': {}}, {'scope': None},
                       {'extra': True}, {'grant_type': 'password'}):
            with self.subTest(field=next(iter(change))):
                response = self.sign_in(**change)
                self.assertEqual((response.status_code, response.json), (400, {'error': 'INVALID_REQUEST'}))
        for field in self.body:
            body = {key: value for key, value in self.body.items() if key != field}
            self.assertEqual(self.desktop.post(NATIVE_SESSION_PATH, base_url=ISSUER, json=body).status_code, 400)
        self.assertFalse(self.oauth.families)

    def test_json_duplicates_malformed_values_and_depth_rejected(self):
        good = json.dumps(self.body)
        bodies = [good[:-1] + ',"approve":true}', good[:-1] + ',"password":"other"}',
                  'null', '[]', '{', '{"approve":NaN}', '['*1500 + ']'*1500,
                  good.replace('true', 'Infinity'), b'\xff']
        for body in bodies:
            with self.subTest(kind=type(body).__name__):
                result = self.desktop.post(NATIVE_SESSION_PATH, base_url=ISSUER,
                    data=body, content_type='application/json')
                self.assertEqual(result.status_code, 400)
        self.assertFalse(self.oauth.families)

    def test_body_oversize_rejected_before_authentication(self):
        with patch.object(self.accounts, 'find_account') as find:
            response = self.sign_in(password='x' * 4096)
            self.assertEqual(response.status_code, 413)
            find.assert_not_called()
        self.assertNotIn('Set-Cookie', response.headers)

    def test_http_wrong_host_content_type_query_and_encoding_fail_closed(self):
        for options in ({'base_url': 'http://nektron.ai'}, {'base_url': 'https://evil.example'},
                        {'base_url': ISSUER, 'query_string': {'extra': 'x'}},
                        {'base_url': ISSUER, 'content_type': 'text/plain'},
                        {'base_url': ISSUER, 'content_type': 'application/problem+json'},
                        {'base_url': ISSUER, 'content_type': 'application/json; charset=iso-8859-1'},
                        {'base_url': ISSUER, 'headers': {'Content-Encoding': 'gzip'}}):
            options = {'content_type': 'application/json', **options}
            response = self.desktop.post(NATIVE_SESSION_PATH, data=json.dumps(self.body), **options)
            self.assertEqual((response.status_code, response.json), (400, {'error': 'INVALID_REQUEST'}))
            self.assertNotIn('Location', response.headers)
        response = self.desktop.post(NATIVE_SESSION_PATH, base_url=ISSUER, data=json.dumps(self.body),
                                     content_type='application/json; charset=UTF-8')
        self.assertEqual(response.status_code, 200)

    def test_every_ambient_browser_header_is_rejected_even_when_empty(self):
        for header in ('Cookie', 'Origin', 'Authorization', 'Referer', 'Sec-Fetch-Site',
                       'Sec-Fetch-Mode', 'Sec-Fetch-Dest', 'Sec-Fetch-User', 'Sec-Fetch-Future'):
            for value in ('', ISSUER if header == 'Origin' else 'synthetic'):
                with self.subTest(header=header, empty=not value):
                    response = self.desktop.post(NATIVE_SESSION_PATH, base_url=ISSUER,
                                                 json=self.body, headers={header: value})
                    self.assertEqual((response.status_code, response.json), (400, {'error': 'INVALID_REQUEST'}))
                    self.assertNotIn('Access-Control-Allow-Origin', response.headers)
        self.assertFalse(self.oauth.families)

    def test_cookie_is_never_read_persisted_or_deleted_even_on_error(self):
        headers = {'Cookie': COOKIE + '=' + 'a'*43}
        with patch.object(self.accounts, 'read_session', side_effect=AssertionError('session read')), \
             patch.object(self.accounts, 'save_session', side_effect=AssertionError('session save')), \
             patch.object(self.accounts, 'delete_session', side_effect=AssertionError('session delete')):
            denied = self.desktop.post(NATIVE_SESSION_PATH, base_url=ISSUER, json=self.body, headers=headers)
            self.assertEqual(denied.status_code, 400)
            success = self.sign_in()
            self.assertEqual(success.status_code, 200)
            for response in (denied, success,
                             self.desktop.get(NATIVE_SESSION_PATH, base_url=ISSUER, headers=headers)):
                self.assertNotIn('Set-Cookie', response.headers)

    def test_only_post_supported_and_no_cors_preflight(self):
        for method in ('GET', 'HEAD', 'PUT', 'DELETE', 'OPTIONS'):
            response = self.desktop.open(NATIVE_SESSION_PATH, base_url=ISSUER, method=method)
            self.assertIn(response.status_code, (403, 405))
            self.assertNotIn('Access-Control-Allow-Origin', response.headers)
            self.assertNotIn('Set-Cookie', response.headers)
        self.assertFalse(self.oauth.families)

    def test_exact_native_csrf_exemption_does_not_extend_to_web_routes(self):
        for path in ('/api/account/login', '/api/account/signup', PREFIX + '/authorize',
                     NATIVE_SESSION_PATH + '/extra'):
            response = self.desktop.post(path, base_url=ISSUER, json={'email': EMAIL, 'password': PASSWORD})
            self.assertEqual(response.status_code, 403)
        self.assertEqual(self.sign_in().status_code, 200)

    def test_native_uses_exact_shared_website_login_budgets(self):
        with patch.object(self.accounts, 'allow_request', return_value=True) as budget:
            self.assertEqual(self.sign_in(email=' ' + EMAIL.upper() + ' ').status_code, 200)
            self.assertEqual(budget.call_args_list[0].args, ('login:ip:127.0.0.1',))
            self.assertEqual(budget.call_args_list[0].kwargs, {'limit': 30, 'seconds': 600})
            self.assertEqual(budget.call_args_list[1].args, ('login:email:' + EMAIL,))
            self.assertEqual(budget.call_args_list[1].kwargs, {'limit': 10, 'seconds': 600})
        self.assertEqual(len(budget.call_args_list), 2)

    def test_alternating_browser_native_does_not_double_email_budget(self):
        attempts = {}
        def budget(key, limit, seconds):
            attempts[key] = attempts.get(key, 0) + 1
            return attempts[key] <= limit
        browser = self.app.test_client()
        with patch.object(self.accounts, 'allow_request', side_effect=budget):
            csrf = browser.get('/api/account/csrf', base_url=ISSUER).json['csrfToken']
            for count in range(10):
                if count % 2:
                    response = self.sign_in(password='wrong-password')
                else:
                    response = browser.post('/api/account/login', base_url=ISSUER,
                        json={'email': EMAIL, 'password': 'wrong-password'},
                        headers={'Origin': ISSUER, 'X-CSRF-Token': csrf})
                self.assertEqual(response.status_code, 401)
            self.assertEqual(self.sign_in().status_code, 429)
        self.assertFalse(self.oauth.families)

    def test_rate_denial_happens_before_password_work(self):
        for values in ([False], [True, False]):
            with patch.object(self.accounts, 'allow_request', side_effect=values), \
                 patch.object(self.accounts, 'find_account') as find, \
                 patch('mail_native.password_matches') as verify:
                response = self.sign_in()
                self.assertEqual((response.status_code, response.json), (429, {'error': 'TRY_LATER'}))
                find.assert_not_called()
                verify.assert_not_called()

    def test_concurrent_password_change_before_finish_login_is_rejected(self):
        finish = self.accounts.finish_login
        def change_password(user_id, expected):
            self.accounts.users[EMAIL]['PasswordHash'] = self.hashed + '-changed'
            return finish(user_id, expected)
        with patch.object(self.accounts, 'finish_login', side_effect=change_password):
            response = self.sign_in()
            self.assertEqual((response.status_code, response.json), (401, {'error': 'INVALID_CREDENTIALS'}))
        self.assertFalse(self.oauth.families)

    def test_concurrent_change_after_login_before_signing_is_rejected(self):
        finish = self.accounts.finish_login
        def change_password(user_id, expected):
            identity = finish(user_id, expected)
            self.accounts.users[EMAIL]['PasswordHash'] = self.hashed + '-changed'
            return identity
        with patch.object(self.accounts, 'finish_login', side_effect=change_password):
            response = self.sign_in()
            self.assertEqual(response.status_code, 401)
        self.assertFalse(self.oauth.families)

    def test_concurrent_change_at_atomic_family_creation_is_rejected(self):
        create = self.oauth.create_refresh_family
        def change_account(raw, data):
            self.accounts.users[EMAIL]['AccountStatus'] = 'disabled'
            return create(raw, data)
        with patch.object(self.oauth, 'create_refresh_family', side_effect=change_account):
            response = self.sign_in()
            self.assertEqual(response.status_code, 401)
            self.assertNotIn('access_token', response.text)
        self.assertFalse(self.oauth.families)

    def test_storage_failure_never_returns_tokens_or_sensitive_error_details(self):
        with patch.object(self.oauth, 'create_refresh_family', side_effect=RuntimeError('password=' + PASSWORD)), \
             self.assertLogs(self.app.logger, 'ERROR') as logs:
            response = self.sign_in()
        self.assertEqual((response.status_code, response.json), (503, {'error': 'ACCOUNT_UNAVAILABLE'}))
        self.assertNotIn(PASSWORD, response.text + str(logs.output))
        self.assertNotIn('access_token', response.text)
        self.assertFalse(self.oauth.credentials)

    def test_account_lookup_and_budget_failure_are_sanitized_and_fail_closed(self):
        for target in ('allow_request', 'find_account', 'finish_login'):
            with patch.object(self.accounts, target, side_effect=RuntimeError('secret=' + PASSWORD)), \
                 self.assertLogs(self.app.logger, 'ERROR') as logs:
                response = self.sign_in()
            self.assertEqual((response.status_code, response.json), (503, {'error': 'ACCOUNT_UNAVAILABLE'}))
            self.assertNotIn(PASSWORD, str(logs.output) + response.text)
        self.assertFalse(self.oauth.families)

    def test_account_state_and_password_change_invalidate_native_refresh(self):
        for field, value in (('AccountStatus', 'disabled'), ('EmailVerified', 0),
                             ('PasswordHash', self.hashed + 'changed')):
            original = self.accounts.users[EMAIL][field]
            token = self.sign_in().json['refresh_token']
            self.accounts.users[EMAIL][field] = value
            self.assertEqual(self.refresh(token).status_code, 400)
            self.accounts.users[EMAIL][field] = original

    def test_native_refresh_marker_must_be_explicit_and_without_callback_fields(self):
        for changes in ({'authentication_flow': 'unknown'}, {'redirect_uri': 'http://127.0.0.1:54321/nektron-mail/callback'},
                        {'code_challenge': 'fake'}, {'resource': 'https://other.example'}, {'client_id': 'other'},
                        {'scope': 'other'}):
            token = self.sign_in().json['refresh_token']
            self.row(token)['data'].update(changes)
            self.assertEqual(self.refresh(token).status_code, 400)
        token = self.sign_in().json['refresh_token']
        self.row(token)['data'].pop('authentication_flow')
        self.assertEqual(self.refresh(token).status_code, 400)

    def test_native_marker_cannot_substitute_for_authorization_code_pkce(self):
        token = self.sign_in().json['refresh_token']
        self.row(token)['kind'] = 'code'
        response = self.desktop.post(PREFIX + '/token', base_url=ISSUER, data={
            'grant_type': 'authorization_code', 'client_id': CLIENT_ID, 'resource': RESOURCE,
            'redirect_uri': 'http://127.0.0.1:54321/nektron-mail/callback', 'code': token, 'code_verifier': 'v'*64})
        self.assertEqual(response.status_code, 400)

    def test_password_is_not_an_oauth_token_grant(self):
        response = self.desktop.post(PREFIX + '/token', base_url=ISSUER, data={
            'grant_type': 'password', 'client_id': CLIENT_ID, 'resource': RESOURCE, 'scope': READ,
            'username': EMAIL, 'password': PASSWORD})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(self.oauth.families)

    def test_native_registration_follows_existing_mail_activation(self):
        app = create_app(SETTINGS, self.accounts, self.mailer)
        self.assertNotIn('mail_native.create_session', app.view_functions)
        self.assertNotIn('mail_oauth.token', app.view_functions)

    def test_native_refresh_cannot_enter_connector_token_endpoint(self):
        from connector_oauth import CHATGPT_CLIENT, PREFIX as CPREFIX, RESOURCE as CRESOURCE
        connector_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        settings = {**self.settings, 'NEKTRON_CONNECTOR_OAUTH_ENABLED': 'true',
            'NEKTRON_CONNECTOR_CHATGPT_CALLBACK': 'https://chatgpt.com/connector/oauth/synthetic_test',
            'NEKTRON_CONNECTOR_SIGNING_PEM': pem(connector_key), 'NEKTRON_CONNECTOR_SIGNING_KID': 'connector-test'}
        with patch('connector_oauth.OAuthStore', return_value=self.oauth):
            app = create_app(settings, self.accounts, self.mailer)
            app.testing = True
            desktop = app.test_client(use_cookies=False)
            token = desktop.post(NATIVE_SESSION_PATH, base_url=ISSUER, json=self.body).json['refresh_token']
            response = desktop.post(CPREFIX + '/token', base_url=ISSUER, data={
                'grant_type': 'refresh_token', 'client_id': CHATGPT_CLIENT, 'resource': CRESOURCE,
                'refresh_token': token})
            self.assertEqual(response.status_code, 400)
            self.assertEqual(self.refresh(token).status_code, 200)


class TransactionAccounts:
    """Records SQL boundaries; deliberately not a substitute for live SQL tests."""
    def __init__(self, account, fail_insert=False):
        self.account = account
        self.fail_insert = fail_insert
        self.statements, self.committed = [], []
        self.rollbacks = 0

    @contextmanager
    def connection(self):
        try:
            yield self
            self.committed = list(self.statements)
        except Exception:
            self.rollbacks += 1
            raise

    @contextmanager
    def cursor(self):
        yield self

    def execute(self, sql, args):
        self.statements.append((sql, args))
        if self.fail_insert and 'INSERT INTO WebsiteOAuthCredential' in sql:
            raise RuntimeError('Synthetic credential insert failure')

    def fetchone(self):
        return self.account


class NativeFamilyStoreTests(unittest.TestCase):
    def setUp(self):
        self.hashed = '$argon2id$synthetic-test-only'
        self.account = {'PasswordHash': self.hashed, 'AccountStatus': 'active', 'EmailVerified': 1}
        self.data = {'user_id': 'synthetic:subject', 'auth_tag': credential_tag(self.hashed),
                     'client_id': CLIENT_ID, 'resource': RESOURCE, 'scope': READ, 'authentication_flow': NATIVE_FLOW}
        self.raw = 'r'*64

    def store(self, accounts):
        store = OAuthStore(accounts)
        store._next_cleanup = float('inf')
        return store

    def test_native_family_and_hashed_refresh_insert_share_account_locked_transaction(self):
        accounts = TransactionAccounts(self.account)
        with patch('connector_oauth_store.time.time', return_value=123456):
            self.store(accounts).create_refresh_family(self.raw, self.data)
        self.assertEqual(len(accounts.committed), 3)
        lock, family, token = accounts.committed
        self.assertIn('FROM `User` WHERE UserId=%s FOR UPDATE', lock[0])
        self.assertEqual(lock[1], ('synthetic:subject',))
        self.assertEqual(family[1][1:], (CLIENT_ID, 123456 + 30*86400))
        self.assertEqual(token[1][0], digest(self.raw))
        self.assertEqual(token[1][1], family[1][0])
        self.assertEqual(token[1][3], family[1][2])
        stored = json.loads(token[1][2])
        self.assertEqual(stored, {**self.data, 'family': family[1][0]})
        self.assertNotIn(self.raw, str(accounts.committed))
        self.assertNotIn(self.hashed, str(accounts.committed))

    def test_second_insert_failure_rolls_back_family_and_never_commits(self):
        accounts = TransactionAccounts(self.account, fail_insert=True)
        with self.assertRaises(RuntimeError):
            self.store(accounts).create_refresh_family(self.raw, self.data)
        self.assertEqual(accounts.rollbacks, 1)
        self.assertFalse(accounts.committed)

    def test_atomic_account_recheck_rejects_changed_credentials_or_ineligible_account(self):
        for account in (None, {**self.account, 'AccountStatus': 'disabled'},
                        {**self.account, 'EmailVerified': 0}, {**self.account, 'PasswordHash': self.hashed + 'changed'},
                        {**self.account, 'PasswordHash': 'legacy'}, {**self.account, 'PasswordHash': None}):
            accounts = TransactionAccounts(account)
            with self.assertRaises(InvalidGrantError):
                self.store(accounts).create_refresh_family(self.raw, self.data)
            self.assertEqual(accounts.rollbacks, 1)
            self.assertEqual(len(accounts.statements), 1)
            self.assertFalse(accounts.committed)


if __name__ == '__main__':
    unittest.main()
