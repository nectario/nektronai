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
- Signup, verification resends and password-reset requests also share atomic
  database-backed budgets across all workers and endpoints. Per recipient: one
  request per minute, three per hour and six per day. Per IP: three per ten
  minutes, ten per hour and thirty per day. Site-wide: ten per minute, thirty per
  hour and one hundred per day. Windows start on first use; each request reserves
  all budgets together, before account lookup or creation. Unknown addresses use
  the same budgets. Recipient throttles retain generic accepted responses;
  IP/site throttles return `TRY_LATER`. No schema migration is required.
- Repeated or failed email delivery does not invalidate earlier unexpired links.
  Using a link still consumes all of that user's action tokens atomically.
- Account-mail forms include an off-screen honeypot. Known email-to-SMS gateways
  are rejected; add other domains with `NEKTRON_ACCOUNT_BLOCKED_EMAIL_DOMAINS`
  (comma-separated). These checks and rate limits reduce abuse, but cannot prove
  a visitor is human or prevent every low-volume automated signup.
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

## Human verification

For stronger bot protection, create a **Managed** Cloudflare Turnstile widget
with allowed hostname `nektron.ai` (account pages redirect the other domains there).
Turnstile does not require moving DNS or hosting to Cloudflare. Store BOTH keys in
the existing `nektron/website/accounts` AWS Secrets Manager JSON, preserving all
other settings:

1. Sign in to the Cloudflare dashboard, open **Turnstile**, and choose **Add widget**.
2. Name it `NektronAI accounts`, add hostname `nektron.ai`, and select **Managed**.
3. Copy the site key and secret key into the two fields below in AWS Secrets
   Manager (region `us-east-2`, secret `nektron/website/accounts`). Edit the
   existing JSON; do not replace its database, email or OAuth settings.
4. Redeploy the account backend to load the keys. Confirm the security check
   appears on signup, forgot-password and verification-resend forms, and test
   those flows with an address you own. Login should remain unchanged.

```text
NEKTRON_TURNSTILE_SITE_KEY=<public widget site key>
NEKTRON_TURNSTILE_SECRET_KEY=<private widget secret key>
```

Restart `nektron-accounts` or redeploy the patched backend to load the settings.
Never commit or paste the secret key into frontend files. The CSRF endpoint
returns only the public site key, and the shared account script renders the widget
on signup, verification resend and reset-request forms. Login and emailed-link
consumption do not require the widget. The server calls Siteverify and checks
success, exact hostname and action before creating accounts or issuing emails.
Missing/invalid/replayed tokens are rejected; service failures fail closed.
Partial key configuration fails startup rather than silently disabling checks.
With neither key configured, the baseline protections remain active but CAPTCHA
is **not enabled**. Use Cloudflare's documented test keys only locally, never in
production. Official setup and validation documentation:

- https://developers.cloudflare.com/turnstile/get-started/
- https://developers.cloudflare.com/turnstile/get-started/server-side-validation/

SES currently forwards delivery failures to the sender. Those notifications
should not be disabled merely to hide abuse. Review hard-bounce recipients and
SES suppression settings separately; mailbox-full/rate-limit failures alone do
not establish that an address is permanently invalid.

## Runtime permissions

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
node website/tests/account_abuse_browser.cjs
```

Browser checks use a local static preview (REVIEW_URL, default port 8771) and
mocked account endpoints. They never create users or send mail. Before deployment,
also exercise transactions against controlled disposable DB rows, and verify SES
delivery using its mailbox simulator. Do not email real users during tests.

After deployment check health, secure cookies, forms on mobile and desktop, SES
acceptance, and login/logout. Monitor account_email_delivery_failed and 5xx rates;
a generic accepted response alone is not proof that an email was delivered.
