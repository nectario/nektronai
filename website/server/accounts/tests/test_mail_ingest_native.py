"""Explicit native upload scope, isolated from existing read/key grants."""
import sys
import unittest
from pathlib import Path

import jwt

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app
from mail_native import NATIVE_SESSION_PATH
from mail_oauth import CLIENT_ID, INGEST, ISSUER, PREFIX, READ, RESOURCE
import test_mail_native as native_fixtures


class MailIngestNativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        native_fixtures.MailNativeTests.setUpClass.__func__(cls)

    sign_in = native_fixtures.MailNativeTests.sign_in
    refresh = native_fixtures.MailNativeTests.refresh
    row = native_fixtures.MailNativeTests.row

    def setUp(self):
        native_fixtures.MailNativeTests.setUp(self)
        self.app = create_app({**self.settings, 'NEKTRON_MAIL_INGEST_ENABLED': 'true'}, self.accounts, self.mailer)
        self.app.testing = True
        self.desktop = self.app.test_client(use_cookies=False)

    def test_ingest_is_exact_native_scope_with_independent_refresh_family(self):
        read = self.sign_in().json
        upload = self.sign_in(scope=INGEST).json
        self.assertEqual(upload['scope'], INGEST)
        claims = jwt.decode(upload['access_token'], self.key.public_key(), algorithms=['RS256'],
                            audience=RESOURCE, issuer=ISSUER)
        self.assertEqual(claims['scope'], INGEST)
        self.assertNotIn('grant_id', claims)  # Archive-key release permission is separate.
        self.assertEqual(self.row(upload['refresh_token'])['data']['scope'], INGEST)
        self.assertNotEqual(self.row(read['refresh_token'])['data']['family'], self.row(upload['refresh_token'])['data']['family'])
        profile = self.desktop.get(PREFIX + '/profile', base_url=ISSUER,
            headers={'Authorization': 'Bearer ' + upload['access_token']})
        self.assertEqual(profile.status_code, 200)
        self.assertEqual(profile.json['sub'], claims['sub'])

    def test_read_refresh_cannot_upgrade_to_ingest(self):
        token = self.sign_in().json
        self.assertEqual(self.refresh(token['refresh_token'], scope=INGEST).status_code, 400)

    def test_upload_refresh_preserves_exact_scope_and_rotates(self):
        token = self.sign_in(scope=INGEST).json
        refreshed = self.refresh(token['refresh_token'], scope=INGEST)
        self.assertEqual(refreshed.status_code, 200)
        self.assertEqual(refreshed.json['scope'], INGEST)
        self.assertNotEqual(refreshed.json['refresh_token'], token['refresh_token'])

    def test_mixed_upload_scope_and_missing_approval_are_rejected(self):
        for scope in (READ + ' ' + INGEST, INGEST + ' ' + READ):
            self.assertEqual(self.sign_in(scope=scope).status_code, 400)
        self.assertEqual(self.sign_in(scope=INGEST, approve=False).status_code, 400)
        self.assertFalse(self.oauth.families)

    def test_browser_authorization_cannot_request_upload(self):
        response = self.desktop.get(PREFIX + '/authorize', base_url=ISSUER, query_string={
            'client_id': CLIENT_ID, 'resource': RESOURCE, 'scope': INGEST, 'response_type': 'code',
            'redirect_uri': 'http://127.0.0.1:45000/nektron-mail/callback', 'state': 's' * 32,
            'code_challenge': 'c' * 43, 'code_challenge_method': 'S256'})
        self.assertEqual(response.status_code, 400)

    def test_browser_code_exchange_cannot_request_upload_scope(self):
        response = self.desktop.post(PREFIX + '/token', base_url=ISSUER, data={
            'grant_type': 'authorization_code', 'client_id': CLIENT_ID, 'resource': RESOURCE, 'scope': INGEST,
            'code': 'synthetic-code', 'redirect_uri': 'http://127.0.0.1:45000/nektron-mail/callback',
            'code_verifier': 'v' * 64})
        self.assertEqual(response.status_code, 400)

    def test_upload_scope_is_off_without_explicit_flag(self):
        disabled = create_app(self.settings, self.accounts, self.mailer).test_client(use_cookies=False)
        response = disabled.post(NATIVE_SESSION_PATH, base_url=ISSUER, json={**self.body, 'scope': INGEST})
        self.assertEqual(response.status_code, 400)


if __name__ == '__main__':
    unittest.main()
