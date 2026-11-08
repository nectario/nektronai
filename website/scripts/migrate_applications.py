"""Review/apply the additive application catalog, with no user enrollment.

Default: offline plan. --check: read-only database preflight. --apply: explicit
DDL plus two product/four client catalog seeds. Live execution needs separate
approval. No User, WebsiteOAuth*, runtime grants, or product data are changed.
"""
import argparse
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'server/accounts'))
from applications import APPLICATIONS, CLIENT_APPLICATIONS

SCHEMA = ROOT / 'server/accounts/applications_schema.sql'
# Field: (MySQL type, nullable, collation, default). Validate existing partial
# installations before writing; CREATE IF NOT EXISTS alone does not detect drift.
EXPECTED = {
    'Application': {
        'ApplicationId': ('varchar(64)', 'NO', 'ascii_bin', None),
        'DisplayName': ('varchar(128)', 'NO', 'utf8mb4_bin', None),
        'Enabled': ('tinyint', 'NO', None, '1'),
    },
    'UserApplication': {
        'UserId': ('varchar(255)', 'NO', 'utf8mb4_bin', None),
        'ApplicationId': ('varchar(64)', 'NO', 'ascii_bin', None),
        'AccessStatus': ("enum('pending','active','suspended','revoked')", 'NO', 'utf8mb4_bin', 'pending'),
        'AppRole': ('varchar(64)', 'NO', 'ascii_bin', 'member'),
        'PlanCode': ('varchar(64)', 'YES', 'ascii_bin', None),
        'Settings': ('json', 'NO', None, None),
        'ExpiresAt': ('bigint unsigned', 'YES', None, None),
        'Version': ('bigint unsigned', 'NO', None, '1'),
        'CreatedAt': ('bigint unsigned', 'NO', None, None),
        'UpdatedAt': ('bigint unsigned', 'NO', None, None),
    },
    'ApplicationOAuthClient': {
        'ClientId': ('varchar(128)', 'NO', 'ascii_bin', None),
        'ApplicationId': ('varchar(64)', 'NO', 'ascii_bin', None),
    },
}
PRIMARY_KEYS = {
    'Application': ['ApplicationId'],
    'UserApplication': ['UserId', 'ApplicationId'],
    'ApplicationOAuthClient': ['ClientId'],
}


def schema_statements():
    return [statement.strip() for statement in SCHEMA.read_text(encoding='utf-8-sig').split(';') if statement.strip()]


def _column_signature(row):
    mysql_type = re.sub(r'\b(tinyint|bigint)\(\d+\)', r'\1', row['COLUMN_TYPE'].lower())
    default = row['COLUMN_DEFAULT']
    return mysql_type, row['IS_NULLABLE'], row['COLLATION_NAME'], None if default is None else str(default)


def preflight(cur):
    cur.execute("SELECT COLUMN_NAME,COLUMN_TYPE FROM information_schema.COLUMNS "
                "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='User'")
    user_columns = {row['COLUMN_NAME']: row['COLUMN_TYPE'] for row in cur.fetchall()}
    if not {'UserId', 'AccountStatus', 'EmailVerified'} <= user_columns.keys():
        raise RuntimeError('Expected existing User account columns are missing')
    identity_type = re.fullmatch(r'(?:var)?char\((\d+)\)', user_columns['UserId'], re.IGNORECASE)
    if not identity_type or not 1 <= int(identity_type[1]) <= 255:
        raise RuntimeError('UserId type requires manual review')
    present = set()
    for table, expected in EXPECTED.items():
        cur.execute('SELECT ENGINE FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s', (table,))
        info = cur.fetchone()
        if not info:
            continue
        present.add(table)
        if info['ENGINE'] != 'InnoDB':
            raise RuntimeError(table + ' engine differs; manual review required')
        cur.execute('SELECT COLUMN_NAME,COLUMN_TYPE,IS_NULLABLE,COLLATION_NAME,COLUMN_DEFAULT '
                    'FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s '
                    'ORDER BY ORDINAL_POSITION', (table,))
        actual = {row['COLUMN_NAME']: _column_signature(row) for row in cur.fetchall()}
        if actual != expected:
            raise RuntimeError(table + ' columns differ; manual review required')
        cur.execute("SELECT COLUMN_NAME FROM information_schema.STATISTICS WHERE TABLE_SCHEMA=DATABASE() "
                    "AND TABLE_NAME=%s AND INDEX_NAME='PRIMARY' ORDER BY SEQ_IN_INDEX", (table,))
        if [row['COLUMN_NAME'] for row in cur.fetchall()] != PRIMARY_KEYS[table]:
            raise RuntimeError(table + ' primary key differs; manual review required')
        cur.execute('SELECT k.COLUMN_NAME,k.REFERENCED_TABLE_NAME,k.REFERENCED_COLUMN_NAME,r.DELETE_RULE,r.UPDATE_RULE, '
                    'k.REFERENCED_TABLE_SCHEMA=DATABASE() AS ReferencesCurrentSchema '
                    'FROM information_schema.KEY_COLUMN_USAGE k JOIN information_schema.REFERENTIAL_CONSTRAINTS r '
                    'ON r.CONSTRAINT_SCHEMA=k.CONSTRAINT_SCHEMA AND r.TABLE_NAME=k.TABLE_NAME '
                    'AND r.CONSTRAINT_NAME=k.CONSTRAINT_NAME '
                    'WHERE k.TABLE_SCHEMA=DATABASE() AND k.TABLE_NAME=%s', (table,))
        foreign_keys = cur.fetchall()
        if table == 'Application':
            valid = not foreign_keys
        else:
            valid = (len(foreign_keys) == 1 and foreign_keys[0]['COLUMN_NAME'] == 'ApplicationId'
                     and foreign_keys[0]['REFERENCED_TABLE_NAME'] == 'Application'
                     and foreign_keys[0]['REFERENCED_COLUMN_NAME'] == 'ApplicationId'
                     and foreign_keys[0]['ReferencesCurrentSchema'] == 1
                     and foreign_keys[0]['DELETE_RULE'] in ('RESTRICT', 'NO ACTION')
                     and foreign_keys[0]['UPDATE_RULE'] in ('RESTRICT', 'NO ACTION'))
        if not valid:
            raise RuntimeError(table + ' foreign keys differ; manual review required')
    if 'ApplicationOAuthClient' in present:
        for client_id, application_id in CLIENT_APPLICATIONS:
            cur.execute('SELECT ApplicationId FROM ApplicationOAuthClient WHERE ClientId=%s', (client_id,))
            mapping = cur.fetchone()
            if mapping and mapping['ApplicationId'] != application_id:
                raise RuntimeError('An OAuth client is already mapped to another application')
    return present


def seed_catalog(cur):
    # Lock and preserve prior display names/disabled state; never overwrite a
    # mapping or enroll any user. Concurrent conflicts abort the transaction.
    for application_id, name in APPLICATIONS:
        cur.execute('SELECT ApplicationId FROM Application WHERE ApplicationId=%s FOR UPDATE', (application_id,))
        if not cur.fetchone():
            cur.execute('INSERT INTO Application (ApplicationId,DisplayName) VALUES (%s,%s)', (application_id, name))
    for client_id, application_id in CLIENT_APPLICATIONS:
        cur.execute('SELECT ApplicationId FROM ApplicationOAuthClient WHERE ClientId=%s FOR UPDATE', (client_id,))
        mapping = cur.fetchone()
        if mapping:
            if mapping['ApplicationId'] != application_id:
                raise RuntimeError('An OAuth client is already mapped to another application')
        else:
            cur.execute('INSERT INTO ApplicationOAuthClient (ClientId,ApplicationId) VALUES (%s,%s)', (client_id, application_id))


def migrate(account_store, *, apply=False):
    with account_store.connection() as c, c.cursor() as cur:
        present = preflight(cur)
        if not apply:
            return present
        for statement in schema_statements():
            cur.execute(statement)
        if preflight(cur) != set(EXPECTED):
            raise RuntimeError('Application schema verification failed')
        seed_catalog(cur)
    return set(EXPECTED)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--check', action='store_true', help='Read-only database preflight using authorized NEKTRON_DB_* settings')
    mode.add_argument('--apply', action='store_true', help='Apply schema/catalog only; requires separately approved database migration')
    args = parser.parse_args(argv)
    if not args.check and not args.apply:
        print('OFFLINE PLAN ONLY: no database connection, user enrollment, OAuth activation or permission changes.\n')
        print(SCHEMA.read_text(encoding='utf-8-sig'))
        print('Catalog products:', ', '.join(application_id for application_id, _ in APPLICATIONS))
        print('Catalog client associations:', len(CLIENT_APPLICATIONS))
        return
    from store import Store
    settings = {key: value for key, value in os.environ.items() if key.startswith('NEKTRON_DB_')}
    settings.setdefault('NEKTRON_DB_CA_FILE', str(ROOT / 'server/accounts/rds-ca.pem'))
    present = migrate(Store(settings), apply=args.apply)
    print('Application schema/catalog ready.' if args.apply else 'Read-only preflight passed. Present tables: ' + ', '.join(sorted(present)))
    print('No user entitlements, account/OAuth records, runtime grants or product data were changed.')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print('Application schema migration failed: ' + type(error).__name__, file=sys.stderr)
        raise SystemExit(1)
