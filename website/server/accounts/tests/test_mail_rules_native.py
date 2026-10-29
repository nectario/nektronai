"""AI rule-authoring native grants are independent from read/key/capture grants."""
import sys
import unittest
from pathlib import Path

import jwt

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app
from mail_native import NATIVE_SESSION_PATH
from mail_oauth import CLIENT_ID, INGEST, ISSUER, PREFIX, READ, RESOURCE, RULES_AUTHOR
import test_mail_native as native_fixtures


class MailRulesNativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        native_fixtures.MailNativeTests.setUpClass.__func__(cls)

    sign_in = native_fixtures.MailNativeTests.sign_in
    refresh = native_fixtures.MailNativeTests.refresh
    row = native_fixtures.MailNativeTests.row

    def setUp(self):
        native_fixtures.MailNativeTests.setUp(self)
        self.app = create_app({**self.settings, 'NEKTRON_MAIL_RULES_AUTHOR_ENABLED': 'true',
                               'NEKTRON_MAIL_INGEST_ENABLED': 'true'}, self.accounts, self.mailer)
        self.app.testing = True
        self.desktop = self.app.test_client(use_cookies=False)

    def test_authoring_is_exact_native_scope_with_separate_family_and_same_subject(self):
        read = self.sign_in().json
        upload = self.sign_in(scope=INGEST).json
        authoring = self.sign_in(scope=RULES_AUTHOR).json
        claims = jwt.decode(authoring['access_token'], self.key.public_key(), algorithms=['RS256'], audience=RESOURCE, issuer=ISSUER)
        self.assertEqual(claims['scope'], RULES_AUTHOR)
        self.assertEqual(claims['sub'], self.accounts.users[self.body['email']]['UserId'])
        self.assertEqual(claims['exp'] - claims['iat'], 300)
        self.assertNotIn('grant_id', claims)
        self.assertNotIn('entitlements', claims)
        self.assertNotIn('mailbox', claims)
        families = {self.row(value['refresh_token'])['data']['family'] for value in (read, upload, authoring)}
        self.assertEqual(len(families), 3)
        profile = self.desktop.get(PREFIX + '/profile', base_url=ISSUER, headers={'Authorization': 'Bearer ' + authoring['access_token']})
        self.assertEqual(profile.status_code, 200)
        self.assertEqual(profile.json['sub'], claims['sub'])

    def test_existing_grants_cannot_upgrade_to_authoring(self):
        for scope in (READ, INGEST):
            token = self.sign_in(scope=scope).json
            self.assertEqual(self.refresh(token['refresh_token'], scope=RULES_AUTHOR).status_code, 400)

    def test_authoring_refresh_preserves_exact_scope_and_rotates(self):
        token = self.sign_in(scope=RULES_AUTHOR).json
        renewed = self.refresh(token['refresh_token'], scope=RULES_AUTHOR)
        self.assertEqual(renewed.status_code, 200)
        self.assertEqual(renewed.json['scope'], RULES_AUTHOR)
        self.assertNotEqual(renewed.json['refresh_token'], token['refresh_token'])
        next_claims = jwt.decode(renewed.json['access_token'], self.key.public_key(), algorithms=['RS256'], audience=RESOURCE, issuer=ISSUER)
        self.assertEqual(next_claims['scope'], RULES_AUTHOR)

    def test_authoring_refresh_cannot_request_mail_or_upload(self):
        for requested in (READ, INGEST, READ + ' mail/archive.keys'):
            token = self.sign_in(scope=RULES_AUTHOR).json
            self.assertEqual(self.refresh(token['refresh_token'], scope=requested).status_code, 400)

    def test_mixed_scopes_and_missing_approval_are_rejected(self):
        for scope in (READ + ' ' + RULES_AUTHOR, RULES_AUTHOR + ' ' + READ, INGEST + ' ' + RULES_AUTHOR):
            self.assertEqual(self.sign_in(scope=scope).status_code, 400)
        self.assertEqual(self.sign_in(scope=RULES_AUTHOR, approve=False).status_code, 400)
        self.assertFalse(self.oauth.families)

    def test_browser_authorization_and_code_exchange_remain_read_only(self):
        response = self.desktop.get(PREFIX + '/authorize', base_url=ISSUER, query_string={
            'client_id': CLIENT_ID, 'resource': RESOURCE, 'scope': RULES_AUTHOR, 'response_type': 'code',
            'redirect_uri': 'http://127.0.0.1:45000/nektron-mail/callback', 'state': 's' * 32,
            'code_challenge': 'c' * 43, 'code_challenge_method': 'S256'})
        self.assertEqual(response.status_code, 400)
        response = self.desktop.post(PREFIX + '/token', base_url=ISSUER, data={
            'grant_type': 'authorization_code', 'client_id': CLIENT_ID, 'resource': RESOURCE, 'scope': RULES_AUTHOR,
            'code': 'synthetic-code', 'redirect_uri': 'http://127.0.0.1:45000/nektron-mail/callback', 'code_verifier': 'v' * 64})
        self.assertEqual(response.status_code, 400)

    def test_authoring_is_off_without_explicit_flag_and_other_scopes_still_work(self):
        disabled = create_app({**self.settings, 'NEKTRON_MAIL_INGEST_ENABLED': 'true'}, self.accounts, self.mailer).test_client(use_cookies=False)
        for scope, status in ((RULES_AUTHOR, 400), (READ, 200), (INGEST, 200)):
            response = disabled.post(NATIVE_SESSION_PATH, base_url=ISSUER, json={**self.body, 'scope': scope})
            self.assertEqual(response.status_code, status)

    def test_disabling_authoring_rejects_its_profile_and_refresh(self):
        token = self.sign_in(scope=RULES_AUTHOR).json
        disabled = create_app(self.settings, self.accounts, self.mailer).test_client(use_cookies=False)
        self.assertEqual(disabled.get(PREFIX + '/profile', base_url=ISSUER,
            headers={'Authorization': 'Bearer ' + token['access_token']}).status_code, 401)
        self.assertEqual(disabled.post(PREFIX + '/token', base_url=ISSUER, data={
            'grant_type': 'refresh_token', 'client_id': CLIENT_ID, 'resource': RESOURCE,
            'refresh_token': token['refresh_token'], 'scope': RULES_AUTHOR}).status_code, 400)


if __name__ == '__main__':
    unittest.main()
