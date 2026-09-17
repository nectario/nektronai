# Website accounts

Auth0 performs signup, password authentication, email verification and recovery.
The website requests only `openid profile email`. It does not request connector
management access, create connector memberships or enable billing.

## Identity and data

- Uses the existing Auth0 tenant/website client, with Authorization Code + S256 PKCE.
- Register `https://nektron.ai/api/account/callback` in the client's Allowed
  Callback URLs, preserving all existing callbacks. Enable the existing database
  connection for the client and allow signup in Auth0.
- The existing application is **Database Connector Account** (public SPA client
  `9bYdBkEd654k8ktx58UtDqDVL3TnEgJ8`), in tenant `dev-cmgmokiptmjiwjri`.
- A verified issuer/subject maps to an opaque `User.UserId`. Never link by email.
- New rows are `Role=user`, `AccountStatus=active`, `EmailVerified=1`.
  Disabled, locked, or pending existing records are not reactivated.
- `PasswordHash=!external-auth:oidc` explicitly marks an external identity; it is
  not a password hash. Never add local password authentication for these rows.
- The website cookie is Secure, HttpOnly, SameSite=Lax, path=/, host-only.
  Session tokens are hashed in MySQL; sessions expire after eight hours.
  OAuth state and PKCE material are server-side and expire after ten minutes.
- Logout requires the exact website Origin and a per-session CSRF token.
- The shared identity does not imply shared authorization between products.
- Existing User emails are not silently replaced from later identity claims.

## Configuration

The EC2 instance role needs GetSecretValue for only the website account secret.
Set the EB environment's `NEKTRON_ACCOUNT_SECRET_ARN` to that ARN. Its JSON contains:

```text
NEKTRON_ACCOUNT_ENABLED=true
NEKTRON_SITE_ORIGIN=https://nektron.ai
NEKTRON_AUTH_ISSUER=https://dev-cmgmokiptmjiwjri.us.auth0.com/
NEKTRON_AUTH_CLIENT_ID=<existing website client>
NEKTRON_DB_HOST=<from authorized NEKTRON environment>
NEKTRON_DB_PORT=3306
NEKTRON_DB_NAME=<from authorized NEKTRON environment>
NEKTRON_DB_USER=<account-scoped runtime user>
NEKTRON_DB_PASSWORD=<secret>
```

For a confidential Auth0 client also set NEKTRON_AUTH_CLIENT_SECRET; public clients
use no client secret. Never copy either passwords or client secrets into assets.

The CA bundle at `rds-ca.pem` is AWS's public RDS trust bundle. Connections always
verify the server certificate and hostname. The environment SSL mode is not used
to downgrade verification.

Apply schema.sql once using a deployment identity. It creates WebsiteSession and
WebsiteRateLimit only; the existing User table is not recreated. Runtime database
grants should be SELECT/INSERT/UPDATE on User, SELECT/INSERT/UPDATE/DELETE on the
two website tables. Do not grant schema changes to the runtime user.

With the authorized NEKTRON_DB_* environment loaded, run
`python website/scripts/configure_accounts.py --aws-from-wsl` from the repository
root for a read-only database and Auth0 preflight. Add `--apply` to provision the
tables, dedicated database user, secret and role policy. No password is printed.
Pass its returned ARN as NEKTRON_ACCOUNT_SECRET_ARN to deploy-eb-site.sh, which
sets the environment reference and application version together.

The backend runs as a dedicated non-login user, bound to loopback behind nginx.
The HTTPS hook blocks /server/. The account hook logs paths without query strings.
No OAuth access tokens or ID tokens are retained after the callback.

## Validation

Run `python -m unittest discover -s tests -v` from this directory with the pinned
requirements installed. Use a local mock identity provider or the injected test
remote; tests must not create real Auth0 users or email real users.

Before publication: verify the callback allowlist, TLS DB access, schema,
least-privilege grants, health endpoint and the real signup/email verification/
login/logout flow. A successful build is not proof that an identity-provider
callback has been configured.
