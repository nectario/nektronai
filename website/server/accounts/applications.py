"""Additive product catalog and explicit per-user entitlements.

Internal storage API, not authentication or a public grant-management endpoint.
Callers must validate issuer/subject and authorize changes before using this API.
Existing OAuth clients and product-specific authorization remain authoritative.
"""
import json
import re
import time

APPLICATIONS = (
    ('database-connector', 'Database Connector'),
    ('status-endpoint', 'Status Endpoint'),
)
CLIENT_APPLICATIONS = (
    ('nektron-database-connector-chatgpt', 'database-connector'),
    ('nektron-database-connector-account', 'database-connector'),
    ('nektron-status-endpoint-chatgpt', 'status-endpoint'),
    ('nektron-status-endpoint-worker', 'status-endpoint'),
)
ACCESS_STATUSES = frozenset(('pending', 'active', 'suspended', 'revoked'))


def _identifier(value, label, maximum=64):
    if not isinstance(value, str) or not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,' + str(maximum - 1) + '}', value):
        raise ValueError('Invalid ' + label)
    return value


def _user_id(value):
    if not isinstance(value, str) or not value or len(value) > 255 or value != value.strip() or any(ord(c) < 32 for c in value):
        raise ValueError('Exact stable UserId required')
    return value


def _status(value):
    if not isinstance(value, str) or value not in ACCESS_STATUSES:
        raise ValueError('Invalid access status')
    return value


def access_allowed(row, now):
    """Fail closed. A global account role never supplies a product role."""
    return bool(row and row.get('AccountStatus') == 'active' and row.get('EmailVerified') == 1
                and row.get('Enabled') == 1 and row.get('AccessStatus') == 'active'
                and (row.get('ExpiresAt') is None or row['ExpiresAt'] > now))


class ApplicationStore:
    def __init__(self, account_store, *, clock=time.time):
        self.accounts = account_store
        self.clock = clock

    def list_applications(self):
        with self.accounts.connection() as c, c.cursor() as cur:
            cur.execute('SELECT ApplicationId,DisplayName,Enabled FROM Application ORDER BY ApplicationId')
            return cur.fetchall()

    def application_for_client(self, client_id):
        """Catalog lookup only. This does NOT register or enable an OAuth client."""
        _identifier(client_id, 'client ID', 128)
        with self.accounts.connection() as c, c.cursor() as cur:
            cur.execute('SELECT a.ApplicationId,a.DisplayName,a.Enabled FROM ApplicationOAuthClient m '
                        'JOIN Application a ON a.ApplicationId=m.ApplicationId WHERE m.ClientId=%s', (client_id,))
            return cur.fetchone()

    def list_user_applications(self, user_id):
        _user_id(user_id)
        with self.accounts.connection() as c, c.cursor() as cur:
            # Binary comparison prevents a case-insensitive legacy User collation
            # from identifying a different subject. No lookup by email is used.
            cur.execute('SELECT ua.*,a.DisplayName,a.Enabled,u.AccountStatus,u.EmailVerified '
                        'FROM UserApplication ua JOIN Application a ON a.ApplicationId=ua.ApplicationId '
                        'JOIN `User` u ON u.UserId=ua.UserId AND BINARY u.UserId=BINARY ua.UserId '
                        'WHERE ua.UserId=%s AND BINARY ua.UserId=BINARY %s ORDER BY ua.ApplicationId',
                        (user_id, user_id))
            rows = cur.fetchall()
        now = self.clock()
        return [self._record(row, now) for row in rows]

    def get_user_application(self, user_id, application_id):
        _user_id(user_id)
        _identifier(application_id, 'application ID')
        with self.accounts.connection() as c, c.cursor() as cur:
            cur.execute('SELECT ua.*,a.DisplayName,a.Enabled,u.AccountStatus,u.EmailVerified '
                        'FROM UserApplication ua JOIN Application a ON a.ApplicationId=ua.ApplicationId '
                        'JOIN `User` u ON u.UserId=ua.UserId AND BINARY u.UserId=BINARY ua.UserId '
                        'WHERE ua.UserId=%s AND BINARY ua.UserId=BINARY %s AND ua.ApplicationId=%s',
                        (user_id, user_id, application_id))
            row = cur.fetchone()
        return self._record(row, self.clock()) if row else None

    @staticmethod
    def _record(row, now):
        result = dict(row)
        result['AccessAllowed'] = access_allowed(row, now)
        result.pop('AccountStatus', None)
        result.pop('EmailVerified', None)
        if isinstance(result['Settings'], str):
            result['Settings'] = json.loads(result['Settings'])
        return result

    def has_access(self, user_id, application_id):
        record = self.get_user_application(user_id, application_id)
        return bool(record and record['AccessAllowed'])

    @staticmethod
    def _lock_user(cur, user_id):
        # Shared locks protect identity state without granting identity writes.
        cur.execute('SELECT UserId,AccountStatus,EmailVerified FROM `User` '
                    'WHERE UserId=%s AND BINARY UserId=BINARY %s FOR SHARE', (user_id, user_id))
        user = cur.fetchone()
        if not user:
            raise ValueError('Unknown exact UserId')
        return user

    @staticmethod
    def _lock_application(cur, application_id):
        cur.execute('SELECT ApplicationId,Enabled FROM Application WHERE ApplicationId=%s FOR SHARE', (application_id,))
        application = cur.fetchone()
        if not application:
            raise ValueError('Unknown application')
        return application

    @staticmethod
    def _require_active(user, application, access_status):
        if access_status == 'active' and (user['AccountStatus'] != 'active'
                or user['EmailVerified'] != 1 or application['Enabled'] != 1):
            raise ValueError('Cannot activate access for an inactive account or application')

    def create_user_application(self, user_id, application_id, *, access_status='pending',
                                app_role='member', plan_code=None, settings=None, expires_at=None):
        """Explicit trusted enrollment only. Repeated enrollment never changes a row.

        In particular, an existing revoked/suspended entry cannot be reactivated
        by backfill or onboarding. Use a reviewed, version-checked state change.
        """
        _user_id(user_id)
        _identifier(application_id, 'application ID')
        _identifier(app_role, 'application role')
        _status(access_status)
        if plan_code is not None:
            _identifier(plan_code, 'plan code')
        if expires_at is not None and (type(expires_at) is not int or not 0 <= expires_at < 2**64):
            raise ValueError('Expiry must be an unsigned Unix timestamp or None')
        if settings is not None and not isinstance(settings, dict):
            raise ValueError('Settings must be a JSON object')
        encoded_settings = json.dumps({} if settings is None else settings, allow_nan=False, sort_keys=True)
        if len(encoded_settings.encode('utf-8')) > 16384:
            raise ValueError('Settings exceed 16 KiB')
        now = int(self.clock())
        with self.accounts.connection() as c, c.cursor() as cur:
            user = self._lock_user(cur, user_id)
            application = self._lock_application(cur, application_id)
            # An unlocked existence check preserves repeat-enrollment semantics.
            # Do not gap-lock a missing row: concurrent inserts would deadlock.
            # The unique key and no-op upsert below arbitrate concurrent creates.
            cur.execute('SELECT Version FROM UserApplication WHERE UserId=%s AND BINARY UserId=BINARY %s '
                        'AND ApplicationId=%s', (user_id, user_id, application_id))
            if cur.fetchone():
                return False
            self._require_active(user, application, access_status)
            cur.execute('INSERT INTO UserApplication '
                        '(UserId,ApplicationId,AccessStatus,AppRole,PlanCode,Settings,ExpiresAt,CreatedAt,UpdatedAt) '
                        'VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) '
                        'ON DUPLICATE KEY UPDATE Version=Version',
                        (user_id, application_id, access_status, app_role, plan_code, encoded_settings, expires_at, now, now))
            # Store does not enable CLIENT_FOUND_ROWS: 1 means inserted, 0 unchanged.
            created = cur.rowcount == 1
        return created

    def set_access_status(self, user_id, application_id, access_status, *, expected_version):
        """Change only this product's state; reject stale administrative writes.

        This does not revoke an OAuth family or replace live product permissions.
        All access consumers must recheck the current entitlement for revocation
        to take effect. No existing runtime calls this optional foundation yet.
        """
        _user_id(user_id)
        _identifier(application_id, 'application ID')
        _status(access_status)
        if type(expected_version) is not int or not 1 <= expected_version < 2**64 - 1:
            raise ValueError('A positive expected version is required')
        with self.accounts.connection() as c, c.cursor() as cur:
            user = self._lock_user(cur, user_id)
            application = self._lock_application(cur, application_id)
            self._require_active(user, application, access_status)
            cur.execute('UPDATE UserApplication SET AccessStatus=%s,Version=Version+1,UpdatedAt=%s '
                        'WHERE UserId=%s AND BINARY UserId=BINARY %s AND ApplicationId=%s AND Version=%s',
                        (access_status, int(self.clock()), user_id, user_id, application_id, expected_version))
            return cur.rowcount == 1
