"""Offline behavioral tests. SQLite is an adapter, not MySQL integration proof."""
import json
import sqlite3
import sys
import unittest
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from applications import ApplicationStore, APPLICATIONS, CLIENT_APPLICATIONS, access_allowed


class Cursor:
    def __init__(self, accounts):
        self.accounts = accounts
        self.cursor = accounts.db.cursor()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.cursor.close()

    def execute(self, sql, args=()):
        self.accounts.calls.append((sql, args))
        # Model MySQL's unchanged duplicate-key write as an ignored insert.
        adapted = sql.replace('%s', '?').replace(' FOR UPDATE', '').replace(' FOR SHARE', '').replace('BINARY ', '')
        adapted = adapted.replace('ON DUPLICATE KEY UPDATE Version=Version', 'ON CONFLICT(UserId, ApplicationId) DO NOTHING')
        self.cursor.execute(adapted, args)

    def fetchone(self):
        row = self.cursor.fetchone()
        return dict(row) if row else None

    def fetchall(self):
        return [dict(row) for row in self.cursor.fetchall()]

    @property
    def rowcount(self):
        return self.cursor.rowcount


class Accounts:
    def __init__(self):
        self.calls = []
        self.db = sqlite3.connect(':memory:')
        self.db.row_factory = sqlite3.Row
        self.db.executescript('''
            PRAGMA foreign_keys=ON;
            CREATE TABLE User (UserId TEXT PRIMARY KEY, Email TEXT, Role TEXT,
                AccountStatus TEXT, EmailVerified INTEGER);
            CREATE TABLE Application (ApplicationId TEXT PRIMARY KEY, DisplayName TEXT, Enabled INTEGER DEFAULT 1);
            CREATE TABLE UserApplication (UserId TEXT, ApplicationId TEXT REFERENCES Application(ApplicationId),
                AccessStatus TEXT DEFAULT 'pending', AppRole TEXT DEFAULT 'member', PlanCode TEXT,
                Settings TEXT, ExpiresAt INTEGER, Version INTEGER DEFAULT 1, CreatedAt INTEGER, UpdatedAt INTEGER,
                PRIMARY KEY(UserId, ApplicationId));
            CREATE TABLE ApplicationOAuthClient (ClientId TEXT PRIMARY KEY,
                ApplicationId TEXT REFERENCES Application(ApplicationId));
        ''')
        self.db.executemany('INSERT INTO User VALUES (?,?,?,?,?)', (
            ('native:alice', 'shared@example.test', 'admin', 'active', 1),
            ('native:bob', 'shared@example.test', 'user', 'active', 1),
            ('native:pending', 'pending@example.test', 'user', 'pending', 0),
            ('native:disabled', 'disabled@example.test', 'admin', 'disabled', 1),
        ))
        self.db.executemany('INSERT INTO Application (ApplicationId,DisplayName) VALUES (?,?)', APPLICATIONS)
        self.db.executemany('INSERT INTO ApplicationOAuthClient VALUES (?,?)', CLIENT_APPLICATIONS)
        self.db.commit()

    @contextmanager
    def connection(self):
        try:
            yield self
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    def cursor(self):
        return Cursor(self)


class ApplicationsTests(unittest.TestCase):
    def setUp(self):
        self.accounts = Accounts()
        self.addCleanup(self.accounts.db.close)
        self.now = 1000
        self.store = ApplicationStore(self.accounts, clock=lambda: self.now)

    def enroll(self, app='database-connector', **kwargs):
        return self.store.create_user_application('native:alice', app, **kwargs)

    def test_signup_catalog_mapping_and_global_admin_do_not_grant_access(self):
        self.assertEqual(2, len(self.store.list_applications()))
        self.assertEqual('status-endpoint', self.store.application_for_client('nektron-status-endpoint-worker')['ApplicationId'])
        self.assertIsNone(self.store.application_for_client('unknown-client'))
        self.assertEqual([], self.store.list_user_applications('native:alice'))
        self.assertFalse(self.store.has_access('native:alice', 'database-connector'))
        self.assertFalse(self.store.has_access('native:alice', 'status-endpoint'))

    def test_enrollment_is_pending_by_default_with_separate_product_settings(self):
        self.assertTrue(self.enroll(settings={'theme': 'dark'}, plan_code='free'))
        record = self.store.get_user_application('native:alice', 'database-connector')
        self.assertEqual('pending', record['AccessStatus'])
        self.assertEqual('member', record['AppRole'])
        self.assertEqual({'theme': 'dark'}, record['Settings'])
        self.assertEqual('free', record['PlanCode'])
        self.assertFalse(record['AccessAllowed'])
        self.assertNotIn('AccountStatus', record)
        self.assertNotIn('EmailVerified', record)
        self.assertNotIn('Email', record)

    def test_one_user_can_have_two_independent_products(self):
        self.enroll(access_status='active', app_role='reader', plan_code='free')
        self.enroll('status-endpoint', access_status='active', app_role='reporter', plan_code='pilot')
        records = self.store.list_user_applications('native:alice')
        self.assertEqual(['database-connector', 'status-endpoint'], [row['ApplicationId'] for row in records])
        self.assertEqual(['reader', 'reporter'], [row['AppRole'] for row in records])
        self.assertTrue(all(row['AccessAllowed'] for row in records))
        self.assertTrue(self.store.set_access_status('native:alice', 'status-endpoint', 'revoked', expected_version=1))
        self.assertFalse(self.store.has_access('native:alice', 'status-endpoint'))
        self.assertTrue(self.store.has_access('native:alice', 'database-connector'))

    def test_same_email_does_not_link_accounts_and_subject_is_exact(self):
        self.enroll(access_status='active')
        self.assertFalse(self.store.has_access('native:bob', 'database-connector'))
        self.assertFalse(self.store.has_access('native:ALICE', 'database-connector'))
        with self.assertRaises(ValueError):
            self.store.create_user_application('native:ALICE', 'database-connector', access_status='active')
        queries = '\n'.join(sql for sql, _ in self.accounts.calls)
        self.assertNotIn('Email=', queries)
        self.assertIn('BINARY UserId=BINARY %s', queries)
        self.assertIn('BINARY u.UserId=BINARY ua.UserId', queries)

    def test_repeat_enrollment_never_reactivates_or_overwrites_existing_data(self):
        self.enroll(access_status='revoked', app_role='reader', plan_code='free', settings={'x': 1}, expires_at=900)
        self.assertFalse(self.enroll(access_status='active', app_role='admin', plan_code='paid', settings={'x': 2}))
        record = self.store.get_user_application('native:alice', 'database-connector')
        self.assertEqual(('revoked', 'reader', 'free', {'x': 1}, 900, 1),
                         tuple(record[k] for k in ('AccessStatus', 'AppRole', 'PlanCode', 'Settings', 'ExpiresAt', 'Version')))

    def test_state_change_is_version_checked_scoped_and_does_not_enroll(self):
        self.enroll(access_status='active')
        self.assertTrue(self.store.set_access_status('native:alice', 'database-connector', 'suspended', expected_version=1))
        self.assertFalse(self.store.set_access_status('native:alice', 'database-connector', 'active', expected_version=1))
        self.assertFalse(self.store.set_access_status('native:bob', 'database-connector', 'active', expected_version=1))
        self.assertFalse(self.store.set_access_status('native:alice', 'status-endpoint', 'active', expected_version=1))
        self.assertFalse(self.store.has_access('native:alice', 'database-connector'))
        self.assertTrue(self.store.set_access_status('native:alice', 'database-connector', 'active', expected_version=2))
        self.assertTrue(self.store.has_access('native:alice', 'database-connector'))
        sql = next(sql for sql, _ in self.accounts.calls if sql.startswith('UPDATE'))
        self.assertIn('ApplicationId=%s AND Version=%s', sql)
        self.assertNotIn('WebsiteOAuth', sql)

    def test_expiry_boundary_and_unknown_records_fail_closed(self):
        self.enroll(access_status='active', expires_at=1001)
        self.assertTrue(self.store.has_access('native:alice', 'database-connector'))
        self.now = 1001
        self.assertFalse(self.store.has_access('native:alice', 'database-connector'))
        self.assertFalse(self.store.has_access('native:missing', 'database-connector'))
        self.assertFalse(self.store.has_access('native:alice', 'missing-product'))

    def test_account_and_application_disabled_state_is_checked_each_read(self):
        self.enroll(access_status='active')
        for statement in ("UPDATE User SET AccountStatus='disabled' WHERE UserId='native:alice'",
                          "UPDATE User SET EmailVerified=0 WHERE UserId='native:alice'",
                          "UPDATE Application SET Enabled=0 WHERE ApplicationId='database-connector'"):
            with self.subTest(statement=statement):
                self.accounts.db.execute(statement)
                self.assertFalse(self.store.has_access('native:alice', 'database-connector'))
                self.accounts.db.execute("UPDATE User SET AccountStatus='active',EmailVerified=1")
                self.accounts.db.execute('UPDATE Application SET Enabled=1')
        self.accounts.db.execute("DELETE FROM User WHERE UserId='native:alice'")
        self.assertFalse(self.store.has_access('native:alice', 'database-connector'))

    def test_activation_rejected_for_inactive_account_or_application_but_revocation_allowed(self):
        for user in ('native:pending', 'native:disabled'):
            with self.subTest(user=user), self.assertRaises(ValueError):
                self.store.create_user_application(user, 'database-connector', access_status='active')
        self.enroll(access_status='active')
        self.accounts.db.execute("UPDATE User SET AccountStatus='disabled' WHERE UserId='native:alice'")
        self.accounts.db.commit()
        self.assertTrue(self.store.set_access_status('native:alice', 'database-connector', 'revoked', expected_version=1))
        with self.assertRaises(ValueError):
            self.store.set_access_status('native:alice', 'database-connector', 'active', expected_version=2)
        self.accounts.db.execute('UPDATE Application SET Enabled=0')
        self.accounts.db.commit()
        with self.assertRaises(ValueError):
            self.store.create_user_application('native:bob', 'status-endpoint', access_status='active')

    def test_unknown_user_or_application_is_rejected_without_insert(self):
        for user, app in (('native:missing', 'database-connector'), ('native:alice', 'missing-product')):
            with self.subTest(user=user, app=app), self.assertRaises(ValueError):
                self.store.create_user_application(user, app)
        self.assertFalse(any(sql.startswith('INSERT') for sql, _ in self.accounts.calls))

    def test_identity_and_catalog_locks_do_not_require_write_privileges(self):
        self.enroll(access_status='active')
        locking = [sql for sql, _ in self.accounts.calls if 'FOR SHARE' in sql]
        self.assertEqual(2, len(locking))
        self.assertTrue(any('FROM `User`' in sql for sql in locking))
        self.assertTrue(any('FROM Application ' in sql for sql in locking))
        self.assertFalse(any('FOR UPDATE' in sql for sql, _ in self.accounts.calls))
        self.assertTrue(any('ON DUPLICATE KEY UPDATE Version=Version' in sql for sql, _ in self.accounts.calls))

    def test_input_validation_does_not_touch_database(self):
        for kwargs in ({'access_status': 'owner'}, {'app_role': 'Admin'}, {'plan_code': '../paid'},
                       {'settings': []}, {'settings': {'nan': float('nan')}}, {'settings': {'huge': 'x' * 16385}},
                       {'expires_at': True}, {'expires_at': -1}, {'expires_at': 2**64}):
            with self.subTest(kwargs=str(kwargs)[:80]), self.assertRaises(ValueError):
                self.enroll(**kwargs)
        for version in (None, True, 0, -1, 2**64):
            with self.subTest(version=version), self.assertRaises(ValueError):
                self.store.set_access_status('native:alice', 'database-connector', 'active', expected_version=version)
        for subject in ('', ' native:alice', 'native:alice ', 'x' * 256, 'native:\nuser'):
            with self.subTest(subject=subject), self.assertRaises(ValueError):
                self.store.has_access(subject, 'database-connector')
        self.assertEqual([], self.accounts.calls)

    def test_client_catalog_matches_existing_ids_without_replacing_configuration(self):
        from connector_oauth import CHATGPT_CLIENT, MANAGEMENT_CLIENT
        from status_oauth_clients import STATUS_CLIENT, WORKER_CLIENT
        self.assertEqual({CHATGPT_CLIENT: 'database-connector', MANAGEMENT_CLIENT: 'database-connector',
                          STATUS_CLIENT: 'status-endpoint', WORKER_CLIENT: 'status-endpoint'}, dict(CLIENT_APPLICATIONS))

    def test_no_permissions_are_derived_from_plan_role_or_settings(self):
        self.enroll(app_role='admin', plan_code='enterprise', settings={'admin': True, 'active': True})
        self.assertFalse(self.store.has_access('native:alice', 'database-connector'))
        self.assertFalse(access_allowed(None, self.now))
        self.assertFalse(access_allowed({'Role': 'admin', 'AccessStatus': 'active'}, self.now))


if __name__ == '__main__':
    unittest.main()
