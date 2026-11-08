# Shared NektronAI application accounts

## Scope and current activation state

This is an additive, local-only foundation for one NektronAI identity across
Database Connector and Status Endpoint. It adds a product catalog and explicit
per-user product records. It is **not wired into account signup, login, OAuth,
Status, Connector, or a public API**. It does not enable any product or client,
grant a user access, or require a new database table for the current Status
plugin rollout. No production migration or deployment has been performed.

The existing `User` remains the global identity. Existing website sessions,
`WebsiteOAuthGrant`, and `WebsiteOAuthCredential` remain unchanged. Product
resources stay in their existing stores: Connector accounts/connections in
DynamoDB, Status workspaces/tasks/grants in its service schema. No operational
data, password, credential, token, or email is copied to this catalog.

## Records

- `Application`: stable, case-sensitive `ApplicationId` and display name.
  `Enabled` is catalog availability, **not** an OAuth activation flag.
- `UserApplication`: `(UserId, ApplicationId)` is the primary key. Each person
  can have several independent product records. Access state is `pending`,
  `active`, `suspended`, or `revoked`; newly created records default to pending.
  The record has product role, optional plan, optional expiry, product settings,
  timestamps, and an optimistic-lock version. Settings must be a JSON object
  up to 16 KiB. Do not store secrets or detailed resource permissions there.
- `ApplicationOAuthClient`: an exact client-to-product association. One product
  can have several clients. The migration seeds the existing Connector ChatGPT
  and management client IDs plus Status ChatGPT and worker IDs. These rows are
  only metadata: they do not register a client, permit redirects, change claims,
  issue credentials, or override existing enabled flags, scopes or audiences.

Only the two requested products are seeded. Other products, including existing
Mail clients, are left alone rather than silently brought into this rollout.

`ApplicationId` has restrictive foreign keys in both related tables. `UserId`
is a logical link, following the existing account support-table convention:
there is deliberately no ALTER of the legacy User table or dependency on its
unknown key/collation definition. Creation locks and verifies the exact existing
UserId. Reads join the current user with a binary comparison and fail closed if
the account no longer exists. If a later account-deletion workflow is introduced,
review archival/cleanup and a physical user foreign key together. A recreated
UserId must never identify a different person.

## Internal API and authorization boundaries

`ApplicationStore(account_store)` uses the existing TLS-verified transactional
connection factory. It provides catalog/client lookups, per-user listing and
lookup, `has_access`, explicit `create_user_application`, and version-checked
`set_access_status`.

This is a **privileged internal storage API**, not an authentication interface.
Before calling it, a future HTTP/admin integration must authenticate the caller,
validate the exact issuer and stable subject, authorize the particular action,
apply CSRF protection where relevant, and record an audit event. There is no
public enrollment, administrative route, automatic backfill, or grant-all call.
Do not hand an untrusted request's user ID, role, status or plan to this API.

- No identity is located or merged by email. Preserve the canonical UserId; do
  not synthesize a native user from an external provider's matching address.
- A global `User.Role=admin` does not confer any product role or access.
- Access requires an existing explicit active record, enabled catalog product,
  current active/verified user, and an unexpired entitlement. Account/product
  state is checked on every read. DB failure raises; callers must fail closed.
- Repeated enrollment does not change an existing row, including suspended or
  revoked records, settings, role, plan, expiry, or version. Backfills therefore
  cannot accidentally reactivate users. Reviewed state changes require the
  current version and affect only that user's specified application.
- An app entitlement is only an additional coarse access prerequisite. It does
  not replace OAuth consent, client/audience/scope validation, current product
  membership, workspace/task grants, connection permissions, or worker identity.
- Revocation in this new store has **no effect on today's live products** until
  those consumers are explicitly integrated. A later integration must check live
  entitlements on protected operations as well as token issuance/refresh, and
  define its in-flight request/token revocation semantics. Do not claim immediate
  token invalidation merely because the catalog record changed.

## Organization access

There is no verified central organization directory in the current account
backend. Do not convert a Connector account ID or Status workspace ID into a
universal organization or infer organization membership from an email domain.
Personal access is implemented now. Optional organization access is an extension:
add an explicit Organization identity, membership, and OrganizationApplication
entitlement only after choosing the authoritative organization/membership model.
Then resolve access from current membership plus that organization's app grant
and explicit per-user suspension policy. Product-specific organizations and
workspace permissions stay in their existing stores until deliberately mapped.
No organization inheritance is implemented or silently granted by this change.

## Migration and review

The command is offline by default. It only prints the schema and seed summary:

```powershell
python website/scripts/migrate_applications.py
```

After separate authorization, a deployment operator can use authorized
`NEKTRON_DB_*` settings for a read-only preflight:

```powershell
python website/scripts/migrate_applications.py --check
```

**Do not run the following against production without explicit migration
approval, reviewed backup/recovery, and a tested disposable MySQL rehearsal:**

```powershell
python website/scripts/migrate_applications.py --apply
```

The apply path checks the existing User column names/type and checks any existing
catalog tables for columns, nullability, defaults, collations, primary keys,
InnoDB engine and restrictive foreign keys. Incompatible tables or conflicting
client associations stop the migration for review. Missing tables are created,
then only absent catalog products/client associations are seeded. Existing names,
disabled state and correct mappings are preserved. Existing UserApplication rows
are never seeded, updated or deleted by this command.

MySQL DDL is not transactionally rolled back. If DDL is interrupted, inspect the
partial result and rerun only after resolving any mismatch. Idempotent DDL and
preflight support a partial installation without dropping data. Catalog DML is
transactional. There are no user, credential, password, token or permission writes.

No new permissions are applied by this code. Before future activation, separately
review least-privilege access: catalog reads for account runtime, entitlement
writes only for the trusted administrative/onboarding component that needs them,
and no direct shared identity-table access for product services. The rehearsed
account read role has SELECT on the three new tables and only UserId,
AccountStatus and EmailVerified from User. The trusted entitlement writer adds
INSERT on UserApplication and UPDATE on only AccessStatus, Version and UpdatedAt.
It needs no User/catalog writes, credential-column reads, DELETE or schema grants.
Shared identity/catalog locks protect concurrent state changes; the unique key
and a no-op duplicate-key insert make concurrent enrollment idempotent. These
locking semantics require MySQL 8.0.22 or later and the existing Store connection
settings without CLIENT_FOUND_ROWS. No grants are applied outside the disposable
rehearsal. Do not grant schema/admin permissions to an account runtime. Do not deploy new consumers
before the schema, reviewed access policy and entitlement population are ready.

Rollback of this dormant addition is simply to leave it unreferenced. If a later
consumer has been enabled, remove/revert that consumer before changing schema.
Preserve catalog/entitlement data for review; do not drop tables or revoke live
permissions as an automatic rollback step.

## Validation

```powershell
python -m unittest discover -s website/server/accounts/tests -p 'test_applications*.py' -v
python -m unittest discover -s website/server/accounts/tests -v
```

Tests cover multiple apps, no automatic access, exact subjects despite shared
email, global-role isolation, app-specific revocation, version conflicts,
expiry, account/product disablement, repeat enrollment preservation, schema
drift, conflicting mappings, offline default, and migration seed scope.
Behavior tests use an in-memory SQLite SQL adapter. Migration tests use MySQL
metadata stubs. A separate, reproducible integration rehearsal exercises real
MySQL without accepting any external database host or credentials:

```powershell
python website/scripts/rehearse_applications_mysql.py --image mysql:8.4
python website/scripts/rehearse_applications_mysql.py --image mysql:8.0
```

Use the account test environment/dependencies and a running local Docker daemon.
The selected official MySQL image must already exist locally; the harness never
pulls an image. It refuses remote Docker sockets, creates a uniquely named
container bound only to 127.0.0.1, generates temporary verified TLS certificates,
uses synthetic users/data, and removes its container and anonymous data volume
when the tests finish. It does not read NEKTRON_DB_* environment configuration,
contact production, send mail, or enable any application/OAuth client.

Coverage includes real DDL, repeated apply, interrupted-DDL recovery, catalog-DML
rollback/retry, suspended-entitlement preservation, conflicting mappings and
schema drift, exact identity under a case-insensitive legacy User collation,
product-isolated revocation, expiry/disablement, eight concurrent enrollments,
five rounds of eight stale-version updates, account-disable races, restrictive
foreign keys, TLS verification, read-only runtime grants and a separate least-
privilege entitlement writer. Legacy identity/OAuth sentinel rows stay unchanged.

These tests do not prove the production schema/grants/configuration or deployed
account/OAuth integration. Before activation, confirm the production MySQL
version and schema, review backup/recovery and grants, rerun the matching
rehearsal plus all existing account/OAuth flows, and obtain explicit migration
and activation approval. Do not use real users or send mail in the rehearsal.

### Recorded local rehearsal

On 2026-11-08, the final harness passed all 16 integration tests on MySQL 8.4.13
and all 16 on MySQL 8.0.46. The full account/OAuth Python regression suite passed
213 tests. Python syntax compilation and the default offline migration plan also
passed. Both disposable containers and their anonymous data volumes were removed.

The rehearsal found that FOR UPDATE on identity/catalog rows required broader
permissions than the intended read-only grants. The local fix uses FOR SHARE for
those state checks and a no-op duplicate-key insert for enrollment. The final
runs verified column-limited entitlement updates and no identity/catalog writes,
while preserving concurrent enrollment and optimistic-version behavior. This is
local validation only, not a production migration or activation result.
