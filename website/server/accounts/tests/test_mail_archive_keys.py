"""Synthetic archive custody and auth regression checks; no AWS/SQL/account I/O."""
import base64
import copy
import hashlib
import json
import secrets
import sys
import threading
import time
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock, patch

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from pymysql.err import IntegrityError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import COOKIE, create_app
from connector_oauth_store import OAuthStore
from credentials import password_hash
from mail_archive_keys import KEY_SCOPE, KEYS_PREFIX, KmsArchiveKeys, canonical_uuid
from mail_archive_keys_store import ArchiveKeyRecord, ArchiveKeyStore
from mail_native import NATIVE_SESSION_PATH
from mail_oauth import CLIENT_ID, ISSUER, PREFIX, READ, RESOURCE
from test_accounts import CaptureMailer, EMAIL, PASSWORD, SETTINGS
from test_mail_native import NativeMemoryOAuthStore
from test_mail_oauth import ProfileStore, pem

KEY_ARN = 'arn:aws:kms:us-east-2:000000000000:key/11111111-1111-4111-8111-111111111111'


class KeyOAuthStore(NativeMemoryOAuthStore):
    def create_refresh_family(self, raw, data):
        super().create_refresh_family(raw, data)
        return self.credentials[hashlib.sha256(raw.encode()).hexdigest()]['data']['family']

    def active_mail_archive_grant(self, family_id, owner, scope):
        family = self.families.get(family_id)
        if (not family or family['revoked'] or family['expires'] <= time.time()
                or family['client'] != CLIENT_ID):
            return False
        active = [row for row in self.credentials.values() if row['kind'] == 'refresh'
                  and row['data']['family'] == family_id and not row['used'] and row['expires'] > time.time()]
        if len(active) != 1:
            return False
        data = active[0]['data']
        return (data['user_id'] == owner and data['scope'] == scope and data['resource'] == RESOURCE
                and data['authentication_flow'] == 'mail-native-session-v1'
                and bool(self.accounts.get_user(owner, data['auth_tag'])))


class MemoryRegistry:
    def __init__(self):
        self.records = {}
        self.lock = threading.Lock()

    def by_request(self, owner, request_id):
        with self.lock:
            return self.records.get((owner, request_id))

    def by_archive(self, owner, archive_id):
        with self.lock:
            return next((row for row in self.records.values()
                         if row.owner_subject == owner and row.archive_id == archive_id), None)

    def insert_or_existing(self, candidate):
        with self.lock:
            return self.records.setdefault((candidate.owner_subject, candidate.request_id), candidate)


class MemoryKeys:
    def __init__(self):
        self.keys = {}
        self.lock = threading.Lock()
        self.wrap_calls = self.unwrap_calls = 0

    def wrap(self, owner, archive_id, key):
        with self.lock:
            wrapped = secrets.token_bytes(64)
            self.keys[wrapped] = (KmsArchiveKeys.context(owner, archive_id), key)
            self.wrap_calls += 1
            return wrapped

    def unwrap(self, row):
        with self.lock:
            self.unwrap_calls += 1
            context, key = self.keys[row.wrapped_key]
            if row.key_version != 1 or context != KmsArchiveKeys.context(row.owner_subject, row.archive_id):
                raise ValueError('Synthetic context mismatch')
            return key


class ArchiveKeysTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.hashed = password_hash(PASSWORD)
        cls.settings = {**SETTINGS, 'NEKTRON_MAIL_OAUTH_ENABLED': 'true',
                        'NEKTRON_MAIL_SIGNING_PEM': pem(cls.key), 'NEKTRON_MAIL_SIGNING_KID': 'archive-test-key',
                        'NEKTRON_MAIL_ARCHIVE_KEYS_ENABLED': 'true',
                        'NEKTRON_MAIL_ARCHIVE_KMS_KEY_ARN': KEY_ARN,
                        'NEKTRON_MAIL_ARCHIVE_KMS_REGION': 'us-east-2'}

    def setUp(self):
        self.accounts, self.registry, self.keys = ProfileStore(), MemoryRegistry(), MemoryKeys()
        self.accounts.users[EMAIL] = {'UserId': 'native:archive-owner', 'Email': EMAIL,
            'PasswordHash': self.hashed, 'FirstName': 'Test', 'LastName': 'Member',
            'AccountStatus': 'active', 'EmailVerified': 1}
        self.oauth = KeyOAuthStore(self.accounts)
        for target, value in (('mail_oauth.OAuthStore', self.oauth),
                              ('mail_archive_keys.ArchiveKeyStore', self.registry),
                              ('mail_archive_keys.KmsArchiveKeys', self.keys)):
            patcher = patch(target, return_value=value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.app = create_app(self.settings, self.accounts, CaptureMailer())
        self.app.testing = True
        self.client = self.app.test_client(use_cookies=False)

    def login(self, scope=KEY_SCOPE, email=EMAIL):
        response = self.client.post(NATIVE_SESSION_PATH, base_url=ISSUER, json={
            'email': email, 'password': PASSWORD, 'client_id': CLIENT_ID,
            'resource': RESOURCE, 'scope': scope, 'approve': True})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json

    def create(self, token, request_id=None, **options):
        return self.client.post(KEYS_PREFIX, base_url=ISSUER,
            headers={'Authorization': 'Bearer ' + token},
            json={'request_id': request_id or str(uuid.uuid4())}, **options)

    def recover(self, token, archive_id):
        return self.client.get(KEYS_PREFIX + '/' + archive_id, base_url=ISSUER,
                               headers={'Authorization': 'Bearer ' + token})

    def refresh(self, token, **fields):
        return self.client.post(PREFIX + '/token', base_url=ISSUER, data={
            'grant_type': 'refresh_token', 'client_id': CLIENT_ID, 'resource': RESOURCE,
            'refresh_token': token, **fields})

    def test_create_retry_recover_same_complete_key_and_owner(self):
        token = self.login()
        request_id = str(uuid.uuid4())
        first = self.create(token['access_token'], request_id)
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(set(first.json), {'archive_id', 'owner_subject', 'key_version', 'data_key'})
        self.assertTrue(canonical_uuid(first.json['archive_id']))
        self.assertEqual((first.json['owner_subject'], first.json['key_version']), ('native:archive-owner', 1))
        self.assertEqual(len(base64.b64decode(first.json['data_key'], validate=True)), 32)
        self.assertEqual(self.create(token['access_token'], request_id).json, first.json)
        self.assertEqual(self.recover(token['access_token'], first.json['archive_id']).json, first.json)
        self.assertEqual(len(self.registry.records), 1)
        self.assertEqual(self.keys.wrap_calls, 1)
        self.assertNotIn(first.json['data_key'], str(self.registry.records))
        for response in (first, self.recover(token['access_token'], first.json['archive_id'])):
            self.assertEqual(response.headers['Cache-Control'], 'no-store')
            self.assertNotIn('Set-Cookie', response.headers)

    def test_concurrent_request_ids_cannot_replace_published_key(self):
        token = self.login()['access_token']
        request_id = str(uuid.uuid4())
        def create_one(_):
            with self.app.test_client(use_cookies=False) as client:
                return client.post(KEYS_PREFIX, base_url=ISSUER,
                    headers={'Authorization': 'Bearer ' + token}, json={'request_id': request_id})
        with ThreadPoolExecutor(max_workers=6) as workers:
            responses = list(workers.map(create_one, range(12)))
        self.assertTrue(all(response.status_code == 200 for response in responses))
        self.assertTrue(all(response.json == responses[0].json for response in responses))
        self.assertEqual(len(self.registry.records), 1)

    def test_other_owner_and_unknown_archive_are_indistinguishable(self):
        owner_token = self.login()['access_token']
        created = self.create(owner_token).json
        self.accounts.users['other@example.com'] = {**self.accounts.users[EMAIL],
            'UserId': 'native:other-owner', 'Email': 'other@example.com'}
        other_token = self.login(email='other@example.com')['access_token']
        denied = self.recover(other_token, created['archive_id'])
        missing = self.recover(other_token, str(uuid.uuid4()))
        self.assertEqual((denied.status_code, denied.json), (404, {'error': 'ARCHIVE_NOT_FOUND'}))
        self.assertEqual((missing.status_code, missing.json), (denied.status_code, denied.json))

    def test_read_scope_never_creates_or_recovers_keys(self):
        read = self.login(READ)
        self.assertEqual(self.create(read['access_token']).status_code, 401)
        self.assertEqual(self.recover(read['access_token'], str(uuid.uuid4())).status_code, 401)
        self.assertEqual(self.refresh(read['refresh_token'], scope=KEY_SCOPE).status_code, 400)
        self.assertFalse(self.registry.records)
        self.assertEqual(self.keys.wrap_calls, 0)

    def test_combined_refresh_preserves_scope_family_and_profile_contract(self):
        first = self.login()
        second = self.refresh(first['refresh_token'])
        self.assertEqual(second.status_code, 200, second.text)
        self.assertEqual(second.json['scope'], KEY_SCOPE)
        claims = jwt.decode(second.json['access_token'], self.key.public_key(), algorithms=['RS256'], audience=RESOURCE)
        self.assertRegex(claims['grant_id'], r'^[a-f0-9]{48}$')
        self.assertNotIn('auth_tag', claims)
        self.assertNotIn(self.hashed, str(claims))
        profile = self.client.get(PREFIX + '/profile', base_url=ISSUER,
            headers={'Authorization': 'Bearer ' + second.json['access_token']})
        self.assertEqual(set(profile.json), {'sub', 'email', 'display_name'})
        self.assertEqual(self.create(second.json['access_token']).status_code, 200)

    def test_revoke_replay_password_account_and_expiry_block_key_release_immediately(self):
        token = self.login()
        archive_id = self.create(token['access_token']).json['archive_id']
        original = copy.deepcopy(self.accounts.users[EMAIL])
        for field, value in (('AccountStatus', 'disabled'), ('EmailVerified', 0), ('PasswordHash', self.hashed + '-changed')):
            self.accounts.users[EMAIL][field] = value
            self.assertEqual(self.recover(token['access_token'], archive_id).status_code, 401)
            self.accounts.users[EMAIL] = copy.deepcopy(original)
        self.oauth.revoke(token['refresh_token'], CLIENT_ID)
        self.assertEqual(self.recover(token['access_token'], archive_id).status_code, 401)
        fresh = self.login()
        self.refresh(fresh['refresh_token'])
        self.assertEqual(self.refresh(fresh['refresh_token']).status_code, 400)
        self.assertEqual(self.recover(fresh['access_token'], archive_id).status_code, 401)
        fresh = self.login()
        family = jwt.decode(fresh['access_token'], options={'verify_signature': False})['grant_id']
        self.oauth.families[family]['expires'] = time.time() - 1
        self.assertEqual(self.recover(fresh['access_token'], archive_id).status_code, 401)

    def test_current_account_is_rechecked_after_unwrap(self):
        token = self.login()['access_token']
        archive_id = self.create(token).json['archive_id']
        unwrap = self.keys.unwrap
        def disable(row):
            key = unwrap(row)
            self.accounts.users[EMAIL]['AccountStatus'] = 'disabled'
            return key
        with patch.object(self.keys, 'unwrap', side_effect=disable):
            self.assertEqual(self.recover(token, archive_id).status_code, 401)

    def test_scope_order_or_grant_claim_tampering_and_bad_tokens_fail(self):
        token = self.login()['access_token']
        claims = jwt.decode(token, options={'verify_signature': False})
        for changes in ({'scope': 'mail/archive.keys mail/archive.read'}, {'scope': READ},
                        {'aud': [RESOURCE]}, {'client_id': 'other'}, {'grant_id': 'x' * 48},
                        {'grant_id': None}, {'exp': claims['iat'] + 301}, {'sub': 'native:other'}):
            raw = jwt.encode({**claims, **changes}, self.key, algorithm='RS256',
                             headers={'kid': 'archive-test-key', 'typ': 'at+jwt'})
            self.assertEqual(self.create(raw).status_code, 401)
        for raw in ('', 'malformed', token + ',another', 'a' * 9000):
            self.assertEqual(self.create(raw).status_code, 401)

    def test_request_shape_ids_encoding_bounds_and_methods_fail_without_key_creation(self):
        token = self.login()['access_token']
        headers = {'Authorization': 'Bearer ' + token}
        for body in ({}, {'request_id': None}, {'request_id': []}, {'request_id': str(uuid.uuid4()).upper()},
                     {'request_id': '00000000-0000-0000-0000-000000000000'},
                     {'request_id': str(uuid.uuid4()), 'owner_subject': 'native:other'},
                     {'request_id': 'x' * 5000}):
            self.assertEqual(self.client.post(KEYS_PREFIX, base_url=ISSUER, headers=headers, json=body).status_code, 400)
        for raw in ('null', '[]', '{', '{"request_id":NaN}', '{"request_id":"x","request_id":"y"}'):
            self.assertEqual(self.client.post(KEYS_PREFIX, base_url=ISSUER, headers=headers,
                                             data=raw, content_type='application/json').status_code, 400)
        for header in ('Cookie', 'Origin', 'Referer', 'Content-Encoding', 'Sec-Fetch-Site', 'Sec-Fetch-Future'):
            self.assertEqual(self.client.post(KEYS_PREFIX, base_url=ISSUER,
                headers={**headers, header: ''}, json={'request_id': str(uuid.uuid4())}).status_code, 401)
        for target in ('http://nektron.ai', 'https://evil.example'):
            self.assertEqual(self.client.post(KEYS_PREFIX, base_url=target, headers=headers,
                json={'request_id': str(uuid.uuid4())}).status_code, 401)
        self.assertEqual(self.client.post(KEYS_PREFIX + '?x=1', base_url=ISSUER, headers=headers,
            json={'request_id': str(uuid.uuid4())}).status_code, 401)
        for method in ('PUT', 'DELETE', 'OPTIONS'):
            response = self.client.open(KEYS_PREFIX, base_url=ISSUER, method=method, headers=headers)
            self.assertIn(response.status_code, (403, 405))
            self.assertNotIn('Access-Control-Allow-Origin', response.headers)
        self.assertFalse(self.registry.records)

    def test_browser_cookie_never_accesses_session_storage_on_keys_routes(self):
        token = self.login()['access_token']
        with patch.object(self.accounts, 'read_session', side_effect=AssertionError('session read')), \
             patch.object(self.accounts, 'save_session', side_effect=AssertionError('session save')), \
             patch.object(self.accounts, 'delete_session', side_effect=AssertionError('session delete')):
            response = self.client.post(KEYS_PREFIX, base_url=ISSUER,
                headers={'Authorization': 'Bearer ' + token, 'Cookie': COOKIE + '=' + 'a' * 43},
                json={'request_id': str(uuid.uuid4())})
            self.assertEqual(response.status_code, 401)
            self.assertNotIn('Set-Cookie', response.headers)

    def test_budget_and_kms_registry_failures_never_leak_or_claim_success(self):
        token = self.login()['access_token']
        with patch.object(self.accounts, 'allow_request', return_value=False):
            self.assertIn(self.create(token).status_code, (401, 429))
        self.assertEqual(self.keys.wrap_calls, 0)
        for target, name in ((self.keys, 'wrap'), (self.registry, 'insert_or_existing')):
            with patch.object(target, name, side_effect=RuntimeError('PRIVATE-KEY-SENTINEL')):
                response = self.create(token)
                self.assertEqual((response.status_code, response.json), (503, {'error': 'ARCHIVE_KEYS_UNAVAILABLE'}))
                self.assertNotIn('PRIVATE-KEY-SENTINEL', response.text)

    def test_subject_budget_precedes_registry_kms_and_checks_ip_budget_too(self):
        token = self.login()['access_token']
        def limit(key, **kwargs):
            return not key.startswith('mail-archive-keys:subject:')
        with patch.object(self.accounts, 'allow_request', side_effect=limit) as budget:
            self.assertEqual(self.create(token).status_code, 429)
        self.assertTrue(any(call.args[0].startswith('mail-archive-keys:ip:') for call in budget.call_args_list))
        self.assertFalse(self.registry.records)
        self.assertEqual(self.keys.wrap_calls, 0)

    def test_unavailable_or_tampered_existing_key_never_replaced_on_retry(self):
        token = self.login()['access_token']
        request_id = str(uuid.uuid4())
        created = self.create(token, request_id).json
        identity = ('native:archive-owner', request_id)
        row = self.registry.records[identity]
        self.registry.records[identity] = replace(row, wrapped_key=b'invalid')
        response = self.create(token, request_id)
        self.assertEqual((response.status_code, response.json), (503, {'error': 'ARCHIVE_KEYS_UNAVAILABLE'}))
        self.assertEqual(self.keys.wrap_calls, 1)
        self.assertEqual(self.registry.records[identity].archive_id, created['archive_id'])
        self.registry.records[identity] = replace(row, key_version=2)
        self.assertEqual(self.recover(token, created['archive_id']).status_code, 503)

    def test_no_key_returned_for_read_token_after_flag_is_enabled_and_no_silent_downgrade(self):
        legacy = self.login(READ)
        rotated = self.refresh(legacy['refresh_token'])
        self.assertEqual(rotated.status_code, 200)
        self.assertEqual(rotated.json['scope'], READ)
        self.assertEqual(self.create(rotated.json['access_token']).status_code, 401)
        combined = self.login()
        self.assertEqual(self.refresh(combined['refresh_token'], scope=READ).status_code, 400)

    def test_recovery_requires_no_body_get_and_exposes_no_cors(self):
        token = self.login()['access_token']
        created = self.create(token).json
        url = KEYS_PREFIX + '/' + created['archive_id']
        headers = {'Authorization': 'Bearer ' + token}
        for method in ('HEAD', 'OPTIONS', 'POST', 'DELETE'):
            result = self.client.open(url, base_url=ISSUER, headers=headers, method=method)
            self.assertIn(result.status_code, (403, 405))
            self.assertNotIn('Access-Control-Allow-Origin', result.headers)
        result = self.client.get(url, base_url=ISSUER, headers=headers, data='unexpected')
        self.assertEqual(result.status_code, 400)

    def test_recovery_flag_cannot_start_without_authentication(self):
        with self.assertRaises(ValueError):
            create_app({**self.settings, 'NEKTRON_MAIL_OAUTH_ENABLED': 'false'}, self.accounts, CaptureMailer())

    def test_default_off_has_no_key_routes_or_combined_native_scope(self):
        app = create_app({**self.settings, 'NEKTRON_MAIL_ARCHIVE_KEYS_ENABLED': 'false'}, self.accounts, CaptureMailer())
        client = app.test_client(use_cookies=False)
        self.assertEqual(client.get(KEYS_PREFIX + '/' + str(uuid.uuid4()), base_url=ISSUER).status_code, 404)
        response = client.post(NATIVE_SESSION_PATH, base_url=ISSUER, json={'email': EMAIL, 'password': PASSWORD,
            'client_id': CLIENT_ID, 'resource': RESOURCE, 'scope': KEY_SCOPE, 'approve': True})
        self.assertEqual(response.status_code, 400)


class ArchiveKmsTests(unittest.TestCase):
    def test_exact_key_context_and_response_size_checks(self):
        client = Mock()
        wrapper = KmsArchiveKeys({'NEKTRON_MAIL_ARCHIVE_KMS_KEY_ARN': KEY_ARN,
                                 'NEKTRON_MAIL_ARCHIVE_KMS_REGION': 'us-east-2'}, client)
        owner, archive_id, key = 'native:synthetic', str(uuid.uuid4()), b'x' * 32
        client.encrypt.return_value = {'KeyId': KEY_ARN, 'CiphertextBlob': b'wrapped'}
        self.assertEqual(wrapper.wrap(owner, archive_id, key), b'wrapped')
        context = client.encrypt.call_args.kwargs['EncryptionContext']
        self.assertEqual(context, {'app': 'nektron-mail', 'purpose': 'local-archive-v1',
            'archive_id': archive_id, 'owner_hash': hashlib.sha256(owner.encode()).hexdigest()})
        self.assertNotIn(owner, str(context))
        row = ArchiveKeyRecord(archive_id, owner, str(uuid.uuid4()), 1, b'wrapped', 1)
        client.decrypt.return_value = {'KeyId': KEY_ARN, 'Plaintext': key}
        self.assertEqual(wrapper.unwrap(row), key)
        self.assertEqual(client.decrypt.call_args.kwargs['EncryptionContext'], context)
        for invalid in ({'KeyId': 'other', 'Plaintext': key}, {'KeyId': KEY_ARN, 'Plaintext': b'short'}):
            client.decrypt.return_value = invalid
            with self.assertRaises(ValueError):
                wrapper.unwrap(row)
        with self.assertRaises(ValueError):
            wrapper.unwrap(replace(row, key_version=2))
        for region, arn in (('us-east-1', KEY_ARN), ('us-east-2', 'alias/mail'), ('', KEY_ARN)):
            with self.assertRaises(ValueError):
                KmsArchiveKeys({'NEKTRON_MAIL_ARCHIVE_KMS_KEY_ARN': arn,
                                'NEKTRON_MAIL_ARCHIVE_KMS_REGION': region}, client)


class RegistrySqlTests(unittest.TestCase):
    def test_exact_owner_binary_binding_and_conflict_never_overwrite(self):
        candidate = ArchiveKeyRecord(str(uuid.uuid4()), 'native:Case-Sensitive', str(uuid.uuid4()), 1, b'wrapped', 1)
        row = {'ArchiveId': candidate.archive_id, 'OwnerSubject': candidate.owner_subject.encode(),
               'RequestId': candidate.request_id, 'KeyVersion': 1, 'WrappedKey': b'wrapped', 'CreatedAt': 1}
        cursor = Mock()
        cursor.__enter__ = Mock(return_value=cursor)
        cursor.__exit__ = Mock(return_value=False)
        cursor.fetchone.return_value = row
        connection = Mock()
        connection.cursor.return_value = cursor
        @contextmanager
        def open_connection():
            yield connection
        accounts = Mock(connection=open_connection)
        registry = ArchiveKeyStore(accounts)
        self.assertEqual(registry.by_archive(candidate.owner_subject, candidate.archive_id), candidate)
        self.assertEqual(cursor.execute.call_args.args[1], (candidate.owner_subject.encode(), candidate.archive_id))
        cursor.execute.side_effect = [IntegrityError(1062, 'duplicate'), None]
        self.assertEqual(registry.insert_or_existing(candidate), candidate)
        self.assertTrue(all('UPDATE' not in call.args[0] and 'DELETE' not in call.args[0]
                            for call in cursor.execute.call_args_list))

    def test_live_grant_sql_checks_family_and_current_account(self):
        cursor = Mock()
        cursor.__enter__ = Mock(return_value=cursor)
        cursor.__exit__ = Mock(return_value=False)
        cursor.fetchone.return_value = {'ClientId': CLIENT_ID, 'Revoked': 0, 'ExpiresAt': int(time.time()) + 1000}
        data = {'user_id': 'native:owner', 'scope': KEY_SCOPE, 'client_id': CLIENT_ID,
                'resource': RESOURCE, 'authentication_flow': 'mail-native-session-v1', 'auth_tag': 'server-only'}
        cursor.fetchall.return_value = [{'Data': json.dumps(data)}]
        connection = Mock()
        connection.cursor.return_value = cursor
        @contextmanager
        def open_connection():
            yield connection
        accounts = Mock(connection=open_connection)
        accounts.get_user.return_value = {'email': EMAIL}
        store = OAuthStore(accounts)
        self.assertTrue(store.active_mail_archive_grant('f' * 48, 'native:owner', KEY_SCOPE))
        accounts.get_user.assert_called_once_with('native:owner', 'server-only')
        self.assertFalse(store.active_mail_archive_grant('f' * 48, 'native:other', KEY_SCOPE))
        cursor.fetchone.return_value['Revoked'] = 1
        self.assertFalse(store.active_mail_archive_grant('f' * 48, 'native:owner', KEY_SCOPE))


if __name__ == '__main__':
    unittest.main()
