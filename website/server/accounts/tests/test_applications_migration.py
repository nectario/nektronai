"""Migration intent and drift checks, with no network or production access."""
import copy
import importlib.util
import io
import re
import sys
import unittest
from contextlib import contextmanager, redirect_stdout
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location('migrate_applications', ROOT / 'scripts/migrate_applications.py')
migration = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(migration)


class SchemaCursor:
    def __init__(self, existing=()):
        self.tables = set(existing)
        self.expected = copy.deepcopy(migration.EXPECTED)
        self.keys = copy.deepcopy(migration.PRIMARY_KEYS)
        self.calls = []
        self.rows = []
        self.apps = {}
        self.clients = {}
        self.engine = 'InnoDB'
        self.delete_rule = 'RESTRICT'
        self.references_current_schema = 1

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return list(self.rows)

    def execute(self, sql, args=()):
        self.calls.append((sql, args))
        self.rows = []
        if "TABLE_NAME='User'" in sql:
            self.rows = [{'COLUMN_NAME': name, 'COLUMN_TYPE': kind} for name, kind in (
                ('UserId', 'varchar(255)'), ('AccountStatus', 'varchar(20)'), ('EmailVerified', 'tinyint(1)'))]
        elif 'information_schema.TABLES' in sql:
            self.rows = [{'ENGINE': self.engine}] if args[0] in self.tables else []
        elif 'information_schema.COLUMNS' in sql:
            self.rows = [dict(COLUMN_NAME=name, COLUMN_TYPE=spec[0], IS_NULLABLE=spec[1], COLLATION_NAME=spec[2],
                              COLUMN_DEFAULT=spec[3]) for name, spec in self.expected[args[0]].items()]
        elif 'information_schema.STATISTICS' in sql:
            self.rows = [{'COLUMN_NAME': name} for name in self.keys[args[0]]]
        elif 'information_schema.KEY_COLUMN_USAGE' in sql:
            if args[0] != 'Application':
                self.rows = [dict(COLUMN_NAME='ApplicationId', REFERENCED_TABLE_NAME='Application',
                                  REFERENCED_COLUMN_NAME='ApplicationId', DELETE_RULE=self.delete_rule, UPDATE_RULE='RESTRICT',
                                  ReferencesCurrentSchema=self.references_current_schema)]
        elif sql.startswith('CREATE TABLE'):
            self.tables.add(re.search(r'EXISTS (\w+)', sql)[1])
        elif sql.startswith('SELECT ApplicationId FROM ApplicationOAuthClient'):
            self.rows = [{'ApplicationId': self.clients[args[0]]}] if args[0] in self.clients else []
        elif sql.startswith('SELECT ApplicationId FROM Application'):
            self.rows = [{'ApplicationId': args[0]}] if args[0] in self.apps else []
        elif sql.startswith('INSERT INTO ApplicationOAuthClient'):
            self.clients[args[0]] = args[1]
        elif sql.startswith('INSERT INTO Application'):
            self.apps[args[0]] = {'DisplayName': args[1], 'Enabled': 1}
        else:
            raise AssertionError('Unexpected SQL: ' + sql)


class SchemaAccounts:
    def __init__(self, cursor):
        self.value = cursor

    @contextmanager
    def connection(self):
        yield self

    def cursor(self):
        return self.value


class ApplicationMigrationTests(unittest.TestCase):
    def test_default_is_offline_plan_without_store_import_or_connection(self):
        # Store is loaded elsewhere by full-suite tests, but main must not construct it.
        with patch('store.Store', side_effect=AssertionError('No database connection')), redirect_stdout(io.StringIO()) as output:
            migration.main([])
        self.assertIn('OFFLINE PLAN ONLY', output.getvalue())
        self.assertIn('Catalog client associations: 4', output.getvalue())

    def test_check_only_does_not_write(self):
        cursor = SchemaCursor()
        self.assertEqual(set(), migration.migrate(SchemaAccounts(cursor)))
        self.assertTrue(all(sql.startswith('SELECT') for sql, _ in cursor.calls))

    def test_apply_and_repeat_seed_only_catalog_preserving_disabled_state(self):
        cursor = SchemaCursor()
        accounts = SchemaAccounts(cursor)
        self.assertEqual(set(migration.EXPECTED), migration.migrate(accounts, apply=True))
        self.assertEqual(2, len(cursor.apps))
        self.assertEqual(4, len(cursor.clients))
        cursor.apps['status-endpoint'] = {'DisplayName': 'Customized title', 'Enabled': 0}
        cursor.calls.clear()
        migration.migrate(accounts, apply=True)
        self.assertEqual({'DisplayName': 'Customized title', 'Enabled': 0}, cursor.apps['status-endpoint'])
        self.assertFalse(any(sql.startswith(('INSERT', 'UPDATE', 'DELETE')) for sql, _ in cursor.calls))

    def test_schema_is_additive_and_does_not_modify_identity_or_oauth_tables(self):
        statements = migration.schema_statements()
        self.assertEqual(3, len(statements))
        self.assertTrue(all(s.startswith('CREATE TABLE IF NOT EXISTS ') for s in statements))
        self.assertNotRegex('\n'.join(statements), r'(?i)\b(ALTER|DROP|GRANT|DELETE|UPDATE|INSERT)\s+(?:TABLE\s+)?(?:`?User`?|WebsiteOAuth\w*)\b')
        self.assertIn('PRIMARY KEY (UserId, ApplicationId)', statements[1])
        self.assertIn("DEFAULT 'pending'", statements[1])
        self.assertIn('ascii_bin', statements[2])

    def test_schema_drift_fails_before_any_write(self):
        for change in ('collation', 'default', 'primary_key', 'engine', 'cascade', 'foreign_database'):
            with self.subTest(change=change):
                cursor = SchemaCursor(migration.EXPECTED)
                if change == 'collation':
                    cursor.expected['ApplicationOAuthClient']['ClientId'] = ('varchar(128)', 'NO', 'ascii_general_ci', None)
                elif change == 'default':
                    cursor.expected['UserApplication']['AccessStatus'] = ("enum('pending','active','suspended','revoked')", 'NO', 'utf8mb4_bin', 'active')
                elif change == 'primary_key':
                    cursor.keys['UserApplication'] = ['UserId']
                elif change == 'engine':
                    cursor.engine = 'MyISAM'
                elif change == 'foreign_database':
                    cursor.references_current_schema = 0
                else:
                    cursor.delete_rule = 'CASCADE'
                with self.assertRaises(RuntimeError):
                    migration.migrate(SchemaAccounts(cursor), apply=True)
                self.assertTrue(all(sql.startswith('SELECT') for sql, _ in cursor.calls))

    def test_conflicting_client_mapping_is_never_overwritten(self):
        cursor = SchemaCursor(migration.EXPECTED)
        cursor.clients['nektron-status-endpoint-chatgpt'] = 'database-connector'
        with self.assertRaises(RuntimeError):
            migration.migrate(SchemaAccounts(cursor), apply=True)
        self.assertTrue(all(sql.startswith('SELECT') for sql, _ in cursor.calls))
        self.assertEqual('database-connector', cursor.clients['nektron-status-endpoint-chatgpt'])

    def test_seed_detects_conflict_after_preflight_too(self):
        cursor = SchemaCursor()
        cursor.clients['nektron-status-endpoint-worker'] = 'database-connector'
        with self.assertRaises(RuntimeError):
            migration.seed_catalog(cursor)
        self.assertEqual('database-connector', cursor.clients['nektron-status-endpoint-worker'])

    def test_no_automatic_user_enrollment_or_oauth_registration(self):
        cursor = SchemaCursor()
        migration.migrate(SchemaAccounts(cursor), apply=True)
        writes = [(sql, args) for sql, args in cursor.calls if sql.startswith(('INSERT', 'UPDATE', 'DELETE'))]
        self.assertEqual(6, len(writes))
        self.assertTrue(all(sql.startswith(('INSERT INTO Application (', 'INSERT INTO ApplicationOAuthClient (')) for sql, _ in writes))
        self.assertEqual({app for _, app in migration.CLIENT_APPLICATIONS}, {app for app, _ in migration.APPLICATIONS})


if __name__ == '__main__':
    unittest.main()
