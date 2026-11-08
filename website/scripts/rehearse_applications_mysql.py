"""Synthetic, local-only MySQL integration rehearsal for application accounts.

Starts a new disposable container, uses the production Store with verified TLS,
never reads NEKTRON_DB_* environment settings, and removes its container/volume.
Requires Docker, an already-present official mysql image, and account test deps.
"""
import argparse
import ipaddress
import json
import os
import secrets
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pymysql
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'server/accounts'))
from applications import ApplicationStore
from store import Store
import migrate_applications as migration

ALICE = 'native:alice'
BOB = 'external:bob'
CONNECTOR = 'database-connector'
STATUS = 'status-endpoint'


def docker(*args, **kwargs):
    return subprocess.run(['docker', *args], check=True, capture_output=True,
                          text=True, timeout=90, **kwargs).stdout.strip()


def certificates(directory):
    """Generate a short-lived CA/server identity for this container only."""
    now = datetime.now(timezone.utc)
    ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'Disposable rehearsal CA')])
    ca = (x509.CertificateBuilder().subject_name(ca_name).issuer_name(ca_name)
          .public_key(ca_key.public_key()).serial_number(x509.random_serial_number())
          .not_valid_before(now - timedelta(minutes=5)).not_valid_after(now + timedelta(days=1))
          .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
          .sign(ca_key, hashes.SHA256()))
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    cert = (x509.CertificateBuilder()
            .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'localhost')]))
            .issuer_name(ca_name).public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(minutes=5)).not_valid_after(now + timedelta(days=1))
            .add_extension(x509.SubjectAlternativeName([
                x509.DNSName('localhost'), x509.IPAddress(ipaddress.ip_address('127.0.0.1'))]), critical=False)
            .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
            .sign(ca_key, hashes.SHA256()))
    (directory / 'ca.pem').write_bytes(ca.public_bytes(serialization.Encoding.PEM))
    (directory / 'server.pem').write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    (directory / 'server-key.pem').write_bytes(key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption()))
    # The disposable MySQL uid must be able to read its test-only server key.
    (directory / 'server-key.pem').chmod(0o644)


class InjectedFailure(RuntimeError):
    pass


class FailingStore:
    """Interrupt after a real statement to test MySQL commit/rollback behavior."""
    def __init__(self, delegate, prefix, after):
        self.delegate, self.prefix, self.remaining = delegate, prefix, after

    @contextmanager
    def connection(self):
        owner = self
        with self.delegate.connection() as connection:
            class Cursor:
                def __init__(self):
                    self.inner = connection.cursor()
                def __enter__(self):
                    return self
                def __exit__(self, *args):
                    self.inner.close()
                def execute(self, sql, args=()):
                    result = self.inner.execute(sql, args)
                    if sql.startswith(owner.prefix):
                        owner.remaining -= 1
                        if owner.remaining == 0:
                            raise InjectedFailure('Simulated interrupted migration')
                    return result
                def __getattr__(self, name):
                    return getattr(self.inner, name)
            class Connection:
                cursor = Cursor
            yield Connection()


class MySQLApplicationsTests(unittest.TestCase):
    settings = None

    def setUp(self):
        self.database = 'rehearsal_' + uuid.uuid4().hex
        self.admin = Store(dict(self.settings, NEKTRON_DB_NAME='mysql'))
        self.sql(self.admin, 'CREATE DATABASE `' + self.database + '` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci')
        self.accounts = Store(dict(self.settings, NEKTRON_DB_NAME=self.database))
        self.sql(self.accounts, '''CREATE TABLE `User` (
            UserId VARCHAR(255) PRIMARY KEY, Email VARCHAR(255), Role VARCHAR(32),
            AccountStatus VARCHAR(20), EmailVerified TINYINT(1), PasswordHash VARCHAR(255)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci''')
        for user, role in ((ALICE, 'admin'), (BOB, 'user')):
            self.sql(self.accounts, 'INSERT INTO `User` VALUES (%s,%s,%s,%s,%s,%s)',
                     (user, 'synthetic@example.test', role, 'active', 1, 'synthetic-not-a-password'))
        for table in ('WebsiteOAuthGrant', 'WebsiteOAuthCredential'):
            self.sql(self.accounts, 'CREATE TABLE ' + table + ' (Id INT PRIMARY KEY, Sentinel VARCHAR(64)) ENGINE=InnoDB')
            self.sql(self.accounts, 'INSERT INTO ' + table + " VALUES (1,'synthetic-untouched')")
        self.app = ApplicationStore(self.accounts, clock=lambda: 1000)

    @staticmethod
    def sql(store, statement, params=()):
        with store.connection() as connection, connection.cursor() as cursor:
            cursor.execute(statement, params or None)
            return list(cursor.fetchall())

    def prepare(self):
        migration.migrate(self.accounts, apply=True)

    def snapshot(self):
        return {table: self.sql(self.accounts, 'SELECT * FROM `' + table + '`')
                for table in ('User', 'WebsiteOAuthGrant', 'WebsiteOAuthCredential')}

    def parallel(self, fn, count=8):
        barrier = threading.Barrier(count)
        def run(index):
            barrier.wait(timeout=20)
            return fn(index)
        with ThreadPoolExecutor(max_workers=count) as pool:
            return list(pool.map(run, range(count)))

    def test_verified_tls_and_read_only_preflight(self):
        with self.accounts.connection() as connection:
            self.assertTrue(connection._sock.cipher())
            self.assertTrue(self.accounts.tls.check_hostname)
            self.assertEqual('CERT_REQUIRED', self.accounts.tls.verify_mode.name)
        before = self.snapshot()
        self.assertEqual(set(), migration.migrate(self.accounts))
        tables = self.sql(self.accounts, 'SHOW TABLES')
        self.assertEqual(3, len(tables))
        self.assertEqual(before, self.snapshot())

    def test_apply_repeat_preserves_catalog_entitlements_and_legacy(self):
        before = self.snapshot()
        self.prepare()
        self.assertEqual(2, len(self.app.list_applications()))
        self.assertEqual(4, len(self.sql(self.accounts, 'SELECT * FROM ApplicationOAuthClient')))
        self.assertEqual([], self.sql(self.accounts, 'SELECT * FROM UserApplication'))
        self.app.create_user_application(ALICE, STATUS, access_status='suspended', app_role='reader',
                                         plan_code='pilot', settings={'mode': 'test'}, expires_at=900)
        self.sql(self.accounts, "UPDATE Application SET DisplayName='Custom',Enabled=0 WHERE ApplicationId=%s", (STATUS,))
        entitlement = self.app.get_user_application(ALICE, STATUS)
        for _ in range(2):
            self.prepare()
        self.assertEqual(entitlement, self.app.get_user_application(ALICE, STATUS))
        self.assertEqual({'ApplicationId': STATUS, 'DisplayName': 'Custom', 'Enabled': 0},
                         self.app.application_for_client('nektron-status-endpoint-chatgpt'))
        self.assertEqual(before, self.snapshot())

    def test_interrupted_ddl_and_retry(self):
        before = self.snapshot()
        with self.assertRaises(InjectedFailure):
            migration.migrate(FailingStore(self.accounts, 'CREATE TABLE', 2), apply=True)
        self.assertEqual({'Application', 'UserApplication'}, migration.migrate(self.accounts))
        self.prepare()
        self.assertEqual(set(migration.EXPECTED), migration.migrate(self.accounts))
        self.assertEqual(4, len(self.sql(self.accounts, 'SELECT * FROM ApplicationOAuthClient')))
        self.assertEqual(before, self.snapshot())

    def test_catalog_dml_rolls_back_and_retry(self):
        with self.assertRaises(InjectedFailure):
            migration.migrate(FailingStore(self.accounts, 'INSERT INTO', 3), apply=True)
        self.assertFalse(self.app.list_applications())
        self.assertEqual([], self.sql(self.accounts, 'SELECT * FROM ApplicationOAuthClient'))
        self.prepare()
        self.assertEqual(2, len(self.app.list_applications()))

    def test_conflicting_mapping_rejected_without_overwrite(self):
        self.prepare()
        self.sql(self.accounts, 'UPDATE ApplicationOAuthClient SET ApplicationId=%s WHERE ClientId=%s',
                 (CONNECTOR, 'nektron-status-endpoint-worker'))
        before = self.sql(self.accounts, 'SELECT * FROM ApplicationOAuthClient ORDER BY ClientId')
        with self.assertRaisesRegex(RuntimeError, 'another application'):
            self.prepare()
        self.assertEqual(before, self.sql(self.accounts, 'SELECT * FROM ApplicationOAuthClient ORDER BY ClientId'))

    def test_schema_drift_rejected_before_seeding(self):
        self.sql(self.accounts, migration.schema_statements()[0])
        self.sql(self.accounts, 'ALTER TABLE Application ADD Unexpected INT')
        with self.assertRaisesRegex(RuntimeError, 'columns differ'):
            self.prepare()
        self.assertEqual([], self.sql(self.accounts, 'SELECT * FROM Application'))
        self.assertEqual(4, len(self.sql(self.accounts, 'SHOW TABLES')))

    def test_exact_identity_and_cross_product_isolation(self):
        self.prepare()
        self.assertFalse(self.app.has_access(ALICE, CONNECTOR))
        self.app.create_user_application(ALICE, CONNECTOR, access_status='active', app_role='reader')
        self.app.create_user_application(ALICE, STATUS, access_status='active', app_role='reporter')
        self.assertFalse(self.app.has_access(BOB, CONNECTOR))
        self.assertFalse(self.app.has_access('native:ALICE', CONNECTOR))
        self.assertIsNone(self.app.get_user_application('native:ALICE', CONNECTOR))
        with self.assertRaisesRegex(ValueError, 'exact UserId'):
            self.app.create_user_application('native:ALICE', CONNECTOR)
        self.assertTrue(self.app.set_access_status(ALICE, STATUS, 'revoked', expected_version=1))
        self.assertFalse(self.app.has_access(ALICE, STATUS))
        self.assertTrue(self.app.has_access(ALICE, CONNECTOR))
        self.assertEqual('reader', self.app.get_user_application(ALICE, CONNECTOR)['AppRole'])
        self.sql(self.accounts, 'DELETE FROM `User` WHERE UserId=%s', (ALICE,))
        self.assertEqual([], self.app.list_user_applications(ALICE))
        self.assertFalse(self.app.has_access(ALICE, CONNECTOR))

    def test_disable_unverified_expiry_and_default_pending_fail_closed(self):
        self.prepare()
        self.app.create_user_application(ALICE, CONNECTOR)
        self.assertFalse(self.app.has_access(ALICE, CONNECTOR))
        self.assertTrue(self.app.set_access_status(ALICE, CONNECTOR, 'active', expected_version=1))
        self.app.create_user_application(ALICE, STATUS, access_status='active', expires_at=1000)
        self.assertFalse(self.app.has_access(ALICE, STATUS))
        for sql, undo in (("UPDATE `User` SET AccountStatus='disabled'", "UPDATE `User` SET AccountStatus='active'"),
                          ('UPDATE `User` SET EmailVerified=0', 'UPDATE `User` SET EmailVerified=1'),
                          ('UPDATE Application SET Enabled=0', 'UPDATE Application SET Enabled=1')):
            self.sql(self.accounts, sql)
            self.assertFalse(self.app.has_access(ALICE, CONNECTOR))
            with self.assertRaises(ValueError):
                self.app.set_access_status(ALICE, CONNECTOR, 'active', expected_version=2)
            self.sql(self.accounts, undo)
        self.assertTrue(self.app.has_access(ALICE, CONNECTOR))

    def test_concurrent_enrollment_is_idempotent(self):
        self.prepare()
        results = self.parallel(lambda i: self.app.create_user_application(
            ALICE, CONNECTOR, access_status='suspended', settings={'winner': i}))
        self.assertEqual(1, results.count(True))
        self.assertEqual(7, results.count(False))
        before = self.app.get_user_application(ALICE, CONNECTOR)
        results = self.parallel(lambda i: self.app.create_user_application(
            ALICE, CONNECTOR, access_status='active', app_role='admin'))
        self.assertEqual([False] * 8, results)
        self.assertEqual(before, self.app.get_user_application(ALICE, CONNECTOR))

    def test_concurrent_updates_reject_stale_versions(self):
        self.prepare()
        self.app.create_user_application(ALICE, CONNECTOR, access_status='active')
        self.app.create_user_application(ALICE, STATUS, access_status='active')
        for version in range(1, 6):
            results = self.parallel(lambda i: self.app.set_access_status(
                ALICE, CONNECTOR, 'suspended' if i % 2 else 'revoked', expected_version=version))
            self.assertEqual(1, results.count(True))
            self.assertEqual(7, results.count(False))
        self.assertEqual(6, self.app.get_user_application(ALICE, CONNECTOR)['Version'])
        self.assertEqual(1, self.app.get_user_application(ALICE, STATUS)['Version'])
        self.assertTrue(self.app.has_access(ALICE, STATUS))

    def test_concurrent_distinct_products_preserve_both(self):
        self.prepare()
        self.assertEqual([True, True], self.parallel(lambda i: self.app.create_user_application(
            ALICE, (CONNECTOR, STATUS)[i], access_status='active'), count=2))
        self.assertTrue(self.app.has_access(ALICE, CONNECTOR))
        self.assertTrue(self.app.has_access(ALICE, STATUS))

    def restricted_store(self, writer=False):
        username, password = 'r_' + uuid.uuid4().hex[:20], secrets.token_urlsafe(24)
        self.sql(self.admin, 'CREATE USER %s@%s IDENTIFIED BY %s REQUIRE SSL', (username, '%', password))
        principal = "'" + username + "'@'%'"
        database = '`' + self.database + '`.'
        self.sql(self.admin, 'GRANT SELECT (UserId,AccountStatus,EmailVerified) ON ' + database + '`User` TO ' + principal)
        for table in migration.EXPECTED:
            self.sql(self.admin, 'GRANT SELECT ON ' + database + table + ' TO ' + principal)
        if writer:
            self.sql(self.admin, 'GRANT INSERT, UPDATE (AccessStatus,Version,UpdatedAt) ON ' + database + 'UserApplication TO ' + principal)
        return Store(dict(self.accounts.settings, NEKTRON_DB_USER=username, NEKTRON_DB_PASSWORD=password))

    def test_read_runtime_has_no_write_ddl_or_sensitive_identity_access(self):
        self.prepare()
        self.app.create_user_application(ALICE, CONNECTOR, access_status='active')
        reader = self.restricted_store()
        runtime = ApplicationStore(reader)
        self.assertTrue(runtime.has_access(ALICE, CONNECTOR))
        self.assertEqual(2, len(runtime.list_applications()))
        for statement in ('SELECT PasswordHash FROM `User`', 'UPDATE Application SET Enabled=0',
                          "UPDATE UserApplication SET AccessStatus='active'", 'CREATE TABLE forbidden (Id INT)',
                          'SELECT * FROM WebsiteOAuthCredential'):
            with self.subTest(statement=statement), self.assertRaises(pymysql.MySQLError):
                self.sql(reader, statement)
        with self.assertRaises(pymysql.MySQLError):
            runtime.create_user_application(BOB, CONNECTOR)
        self.assertFalse(self.app.has_access(BOB, CONNECTOR))

    def test_revoked_read_permission_raises_instead_of_using_cached_access(self):
        self.prepare()
        self.app.create_user_application(ALICE, CONNECTOR, access_status='active')
        reader = self.restricted_store()
        runtime = ApplicationStore(reader)
        self.assertTrue(runtime.has_access(ALICE, CONNECTOR))
        principal = "'" + reader.settings['NEKTRON_DB_USER'] + "'@'%'"
        self.sql(self.admin, 'REVOKE SELECT ON `' + self.database + '`.UserApplication FROM ' + principal)
        with self.assertRaises(pymysql.MySQLError):
            runtime.has_access(ALICE, CONNECTOR)

    def test_concurrent_account_disable_prevents_new_active_entitlement(self):
        self.prepare()
        started = threading.Event()
        def enroll():
            started.set()
            return self.app.create_user_application(ALICE, CONNECTOR, access_status='active')
        with ThreadPoolExecutor(max_workers=1) as pool:
            with self.accounts.connection() as connection, connection.cursor() as cursor:
                cursor.execute("UPDATE `User` SET AccountStatus='disabled' WHERE UserId=%s", (ALICE,))
                pending = pool.submit(enroll)
                self.assertTrue(started.wait(timeout=10))
                time.sleep(0.1)
                self.assertFalse(pending.done())
            with self.assertRaisesRegex(ValueError, 'inactive account'):
                pending.result(timeout=10)
        self.assertIsNone(self.app.get_user_application(ALICE, CONNECTOR))

    def test_entitlement_writer_needs_no_identity_or_catalog_write_grants(self):
        self.prepare()
        writer = self.restricted_store(writer=True)
        administrative = ApplicationStore(writer, clock=lambda: 1000)
        self.assertTrue(administrative.create_user_application(ALICE, CONNECTOR, access_status='active'))
        self.assertTrue(administrative.set_access_status(ALICE, CONNECTOR, 'revoked', expected_version=1))
        self.assertFalse(administrative.has_access(ALICE, CONNECTOR))
        for statement in ("UPDATE `User` SET Role='admin'", 'UPDATE Application SET Enabled=0',
                          'DELETE FROM UserApplication', "UPDATE UserApplication SET AppRole='admin'", 'CREATE TABLE forbidden (Id INT)',
                          'SELECT PasswordHash FROM `User`', 'SELECT * FROM WebsiteOAuthGrant'):
            with self.subTest(statement=statement), self.assertRaises(pymysql.MySQLError):
                self.sql(writer, statement)

    def test_foreign_keys_restrict_orphans_and_catalog_deletion(self):
        self.prepare()
        self.app.create_user_application(ALICE, CONNECTOR)
        for statement in ("DELETE FROM Application WHERE ApplicationId='database-connector'",
                          "UPDATE ApplicationOAuthClient SET ApplicationId='missing'",
                          "UPDATE UserApplication SET ApplicationId='missing'"):
            with self.subTest(statement=statement), self.assertRaises(pymysql.IntegrityError):
                self.sql(self.accounts, statement)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', choices=('mysql:8.0', 'mysql:8.4', 'mysql:8.4.5'), default='mysql:8.4')
    args = parser.parse_args()
    # Refuse remote daemons, including an environment override of the context.
    endpoint = os.environ.get('DOCKER_HOST') or json.loads(docker('context', 'inspect'))[0]['Endpoints']['docker']['Host']
    if not endpoint.startswith(('npipe://', 'unix://')):
        raise RuntimeError('A local Docker socket is required for this rehearsal')
    # No pull, remote endpoint, imported data, external credentials or host DB option.
    docker('image', 'inspect', args.image)
    name = 'nektron-app-rehearsal-' + uuid.uuid4().hex[:12]
    with tempfile.TemporaryDirectory(prefix='nektron-app-rehearsal-') as temp:
        directory = Path(temp)
        certificates(directory)
        password = secrets.token_urlsafe(32)
        environment = dict(os.environ, MYSQL_ROOT_PASSWORD=password, MYSQL_ROOT_HOST='%')
        created = False
        try:
            docker('run', '--detach', '--pull=never', '--name', name,
                   '--label', 'nektron.purpose=disposable-application-rehearsal',
                   '--publish', '127.0.0.1::3306', '--env', 'MYSQL_ROOT_PASSWORD', '--env', 'MYSQL_ROOT_HOST',
                   '--mount', 'type=bind,source=' + str(directory) + ',target=/rehearsal-tls,readonly',
                   args.image, '--ssl-ca=/rehearsal-tls/ca.pem', '--ssl-cert=/rehearsal-tls/server.pem',
                   '--ssl-key=/rehearsal-tls/server-key.pem', '--require-secure-transport=ON', env=environment)
            created = True
            port = int(docker('port', name, '3306/tcp').rsplit(':', 1)[1])
            settings = {'NEKTRON_DB_HOST': '127.0.0.1', 'NEKTRON_DB_PORT': port,
                        'NEKTRON_DB_USER': 'root', 'NEKTRON_DB_PASSWORD': password,
                        'NEKTRON_DB_NAME': 'mysql', 'NEKTRON_DB_CA_FILE': str(directory / 'ca.pem')}
            admin = Store(settings)
            deadline = time.monotonic() + 90
            while True:
                try:
                    version = MySQLApplicationsTests.sql(admin, 'SELECT VERSION() AS version')[0]['version']
                    break
                except pymysql.MySQLError:
                    if time.monotonic() >= deadline:
                        raise RuntimeError('Disposable MySQL did not become ready') from None
                    time.sleep(1)
            print('Disposable MySQL ' + version + '; localhost only, TLS verified, synthetic data only.', flush=True)
            MySQLApplicationsTests.settings = settings
            result = unittest.TextTestRunner(verbosity=2).run(
                unittest.defaultTestLoader.loadTestsFromTestCase(MySQLApplicationsTests))
            print(json.dumps({'mysql_version': version, 'tests': result.testsRun,
                              'failures': len(result.failures), 'errors': len(result.errors)}), flush=True)
            return 0 if result.wasSuccessful() else 1
        finally:
            # Only the uniquely named container created above and its anonymous volume.
            if created:
                docker('rm', '--force', '--volumes', name)
                print('Disposable container and anonymous data volume removed.', flush=True)


if __name__ == '__main__':
    raise SystemExit(main())
