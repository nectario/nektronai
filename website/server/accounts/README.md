# Website accounts

Native email/password forms stay on nektron.ai. This backend uses the existing
NektronDB `User` table, not Auth0 redirects. Database Connector's Auth0 configuration
is separate and is not modified, nor does a website account grant connector access.

## Identity and security

- New signups require first name, last name and an explicitly selected country or
  region, as well as email and password. Middle name and phone number are optional.
  The country allowlist is `assets/account-countries.json`, shared with the static
  form and tested for parity. Codes follow ISO 3166-1 plus the user-assigned XK code;
  the source revision and license are included alongside the data.
- `User.CountryCode` is nullable for existing accounts and other product clients.
  Before deploying this version, run `python website/scripts/migrate_account_profile.py --apply`
  with the authorized NEKTRON_DB_* deployment credentials. The migration is additive
  and idempotent; it does not backfill or overwrite users. Runtime grants remain
  unchanged. Country and phone are self-reported, not verified identity factors.

- Signup creates `native:<uuid>` identities with `Role=user`, `AccountStatus=pending`
  and `EmailVerified=0`. Duplicate signup never changes an existing password.
  Repeated signup for a pending account emails a password-reset link, rather
  than activating a potentially pre-registered password chosen by someone else.
- Passwords are Argon2id hashes (64 MiB, three iterations, one lane). Passwords
  have no minimum length beyond being non-empty and not entirely whitespace.
  A server-side 1,024-byte resource-safety cap applies consistently to signup,
  reset and login; passwords are never truncated. No password is logged or returned.
- Email verification is required before login. Verification links last 24 hours;
  password-reset links last 30 minutes. Tokens are random, hashed in the database,
  credential-bound, and consumed transactionally once. Disabled/locked accounts
  cannot log in or use these links to reactivate themselves.
- Tokens use URL fragments, which are removed from browser history immediately.
  Opening a valid verification link automatically submits a CSRF-protected POST
  from the browser; no email re-entry or second confirmation click is needed.
  A plain GET does not consume the token. JavaScript-capable email scanners can
  complete this flow too, but verification never signs anyone in automatically.
- All mutations require JSON, the exact site Origin, and a per-session CSRF token.
  Login, signup and email requests have database-backed IP/email rate limits.
- Unknown/existing email requests have generic responses and a timing floor.
  Delivery errors log only the error class, never addresses, links or credentials.
- Secure, HttpOnly, SameSite=Lax, host-only cookies contain opaque session tokens.
  The database stores only their hashes. Login rotates the session; authenticated
  sessions expire in eight hours. Logout deletes the session. Password changes
  revoke all sessions and invalidate prior action tokens.
- Previously created external-auth website rows can establish a native password
  using the email-proven reset flow, preserving their UserId. This does not change
  their Auth0 password or silently create a shared login with Database Connector.

## Configuration

Set the EB environment's `NEKTRON_ACCOUNT_SECRET_ARN` to the website runtime secret.
Its JSON contains:

```text
NEKTRON_ACCOUNT_ENABLED=true
NEKTRON_SITE_ORIGIN=https://nektron.ai
NEKTRON_AUTH_EMAIL_FROM=NektronAI <info@nektron.ai>
NEKTRON_EMAIL_REGION=us-east-2
NEKTRON_DB_HOST=<authorized database host>
NEKTRON_DB_PORT=3306
NEKTRON_DB_NAME=<existing database>
NEKTRON_DB_USER=<account-scoped runtime user>
NEKTRON_DB_PASSWORD=<secret>
```

The EC2 role receives GetSecretValue for this secret and ses:SendEmail for the
verified info@nektron.ai identity only. SES must have production sending enabled.
No credentials belong in public assets. Old provider settings are retained only
for application-version rollback; this backend does not read them.

The public AWS CA bundle at `rds-ca.pem` verifies the RDS certificate and hostname.
The provisioner adds WebsiteSession, WebsiteRateLimit and WebsiteActionToken, not
a replacement User table. Runtime grants are SELECT/INSERT/UPDATE on User, and
SELECT/INSERT/UPDATE/DELETE on the three support tables, with no schema privileges.

Load the authorized NEKTRON_DB_* environment, then run from the repository root:

```sh
python website/scripts/configure_accounts.py --aws-from-wsl
python website/scripts/configure_accounts.py --aws-from-wsl --apply
```

The first command is a read-only DB preflight. The second provisions the storage,
scoped runtime identity, secret and email permissions. No passwords are printed.
Pass the secret ARN to deploy-eb-site.sh. The service runs as a dedicated non-login
user on loopback behind nginx. Public access to /server/ is blocked.

## Validation

```sh
python -m unittest discover -s website/server/accounts/tests -v
node website/tests/account_browser.cjs
```

Browser checks use a local static preview (REVIEW_URL, default port 8771) and
mocked account endpoints. They never create users or send mail. Before deployment,
also exercise transactions against controlled disposable DB rows, and verify SES
delivery using its mailbox simulator. Do not email real users during tests.

After deployment check health, secure cookies, forms on mobile and desktop, SES
acceptance, and login/logout. Monitor account_email_delivery_failed and 5xx rates;
a generic accepted response alone is not proof that an email was delivered.
