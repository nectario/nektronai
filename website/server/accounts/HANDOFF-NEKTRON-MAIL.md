# Nektron Mail signup and shared account handoff

Prepared October 12, 2026 for the Nektron Mail implementation agent.

Reuse the existing NektronAI account identity rather than creating a separate
password database for Nektron Mail. Signup, verification, password recovery and
website login already exist. Signing a desktop app or a separately hosted web app
into that identity still requires a deliberately implemented integration.

## Source and release status

Repository: `C:/Development/Projects/NektronAI`; website: `website/`.
The corresponding WSL path is `/mnt/c/Development/Projects/NektronAI`.

This handoff describes the current local source, not a fresh production audit.
The baseline before this handoff was `25aa575`. The commit containing this file
also includes the previously uncommitted account abuse protection, regression
tests, account frontend, and Database Connector updates. Use that commit or a
reviewed descendant rather than `25aa575` alone. Compare the intended deployment
with the live source bundle before publishing; a Git push is not a deployment.

The account abuse patch was independently observed Ready/Green in production on
October 5, 2026 at approximately 11:44 PM Eastern, version
`nektron-account-abuse-20261006T033029Z`. The CLI reported 57 backend tests plus
concurrency and browser checks passed at that time. That is historical evidence,
not a deployment performed for this handoff. All 57 backend tests were rerun and
passed locally while preparing the October 12 commit; no real users or emails
were used by that suite.

## Existing account service

- Native first-party forms at `https://nektron.ai/signup.html` and `/login.html`.
  Website signup no longer uses Auth0 redirects. Do not revive the old Auth0 flow.
- Python Flask and Gunicorn behind nginx on Elastic Beanstalk, with MySQL/RDS
  storage in the existing NektronDB `User` table. Database access is server-side
  with certificate and hostname validation.
- Shared identity key: `UserId`, currently generated as `native:<uuid>` for new
  signups. Treat it as an opaque identifier; preserve existing IDs and do not
  use email as a permanent product ownership key.
- Signup inserts `Role=user`, `AccountStatus=pending`, `EmailVerified=0`.
  Only active, verified users may log in. Disabled/locked users cannot use
  verification or reset to reactivate themselves.
- `WebsiteSession`, `WebsiteActionToken` and `WebsiteRateLimit` support the
  website account lifecycle. Connector OAuth has separate support tables.
- A NektronAI identity is not itself a Mail subscription or mailbox authorization.
  Store Mail-specific enrollment, preferences and entitlements separately, keyed
  by the shared user ID. Gmail/Microsoft/IMAP account connections need their own
  authorization and credential-storage design.

## Signup fields and validation

| JSON field | Required | Current behavior |
| --- | --- | --- |
| `firstName` | Yes | Trimmed, at most 100 characters, alphabetic content required, control characters rejected. |
| `lastName` | Yes | Same validation as first name. |
| `countryCode` | Yes | Explicit selection from `website/assets/account-countries.json`; not a free-text country. |
| `email` | Yes | Validated, normalized and lowercased on the server. |
| `password` | Yes | Non-empty and not entirely whitespace; no visible minimum-length rule. |
| `middleName` | No | Same name validation when provided; empty is allowed. |
| `phoneNumber` | No | Common international formatting; at most 30 characters and 4-15 digits when provided. |
| `website` | Bot trap | Must remain empty; not a visible profile field. |
| `turnstileToken` | Conditional | Needed for email-generating operations when Turnstile is configured. |

Passwords are Argon2id hashes with 64 MiB memory, three iterations and one lane.
The server has a 1,024-byte UTF-8 resource-safety cap and never truncates passwords.
No minimum beyond nonblank was a deliberate owner choice, not a recommended
strength standard. Do not silently change it or describe it as strong-password
enforcement; discuss any policy change with the owner. Do not reuse a mailbox
provider password as the NektronAI account password.

Country and phone are self-reported profile data, not verified identity factors.
Existing accounts may have no country even though new signup requires it.

## Current website API contract

Base: `https://nektron.ai/api/account`. These are same-origin website endpoints,
not a general desktop bearer-token API. They use a host-only cookie and do not
provide cross-origin SSO just because another product shares the database.

Fetch `GET /csrf` first. Retain the browser session cookie and pass the returned
`csrfToken` as `X-CSRF-Token` on JSON POSTs. The browser must send the exact
`Origin: https://nektron.ai`. `/csrf` also returns the public `turnstileSiteKey`,
or an empty value when the challenge is disabled. Never expose its secret key.

| Method and path | Body or response |
| --- | --- |
| `GET /csrf` | `{csrfToken, turnstileSiteKey}`; creates a short-lived form session. |
| `POST /signup` | Fields above; generic HTTP 202 `{accepted:true}`. |
| `POST /login` | `{email,password}`; success `{authenticated:true,redirect:"/account.html"}`. |
| `GET /session` | `{authenticated:false}` or `{authenticated:true,user,csrfToken}`. |
| `POST /request-verification` | `{email,website,turnstileToken}`; generic HTTP 202. |
| `POST /verify-email` | `{token}`; success `{verified:true}`. |
| `POST /request-reset` | `{email,website,turnstileToken}`; generic HTTP 202. |
| `POST /reset-password` | `{token,password}`; success `{reset:true}`. |
| `POST /logout` | JSON `{}` with CSRF; success `{signedOut:true}`. |
| `GET /health` | Readiness; not proof of email delivery. |

POST bodies accept only the endpoint's defined fields; unknown fields are
rejected. The account service caps request bodies at 4 KiB. Do not add a
`product`, arbitrary `returnUrl`, or other field without an explicit API change.

The public session profile includes email, names, country and phone, but currently
does NOT return `UserId`. A Mail integration must obtain a stable subject through
a proper authenticated interface, not infer it from profile data.

Handle validation errors, `INVALID_CREDENTIALS`, `EMAIL_NOT_VERIFIED`,
`INVALID_LINK`, `INVALID_CSRF`, `HUMAN_VERIFICATION_REQUIRED`, `TRY_LATER` and
`ACCOUNT_UNAVAILABLE`. HTTP 202 means the request was accepted generically; it
does not confirm account creation, account existence, or email delivery.

## Verification and recovery behavior

- New signup sends a 24-hour verification link. Reset links last 30 minutes.
- Both use 43-character random bearer tokens in URL fragments, not query strings.
  The pages remove the fragment from history and keep the token out of server logs.
- Opening a verification link automatically submits a CSRF-protected POST. No
  email re-entry is required. A GET alone does not consume it, and verification
  does not automatically log the user in. JavaScript-capable mail scanners may
  execute the verification flow.
- Tokens are hashed, credential-bound and consumed transactionally once.
  A repeated or failed send does not invalidate an earlier unexpired link.
- Successful verification/reset clears that user's action tokens and website
  sessions. Reset also establishes the new password and verified, active status
  for eligible pending/active accounts; it never unlocks disabled/locked users.
- Duplicate signup does not overwrite an existing password or profile. For a
  pending account it sends a reset link, so the email owner must replace a
  potentially attacker-chosen preregistration password before using the account.
- Login rotates the session. Authenticated sessions last eight hours; anonymous
  form sessions default to ten minutes. Cookie: `__Host-nektron_session`, Secure,
  HttpOnly, SameSite=Lax, Path=/, without a Domain attribute. Refresh the CSRF
  value after login. Do not copy this cookie into a desktop application.

## Abuse protection and email delivery

Signup, verification-resend and reset-request share atomic MySQL-backed budgets,
reserved before lookup or creation, including for unknown addresses:

| Scope | Current shared limits |
| --- | --- |
| Recipient | 1/minute, 3/hour, 6/day |
| Source IP | 3/10 minutes, 10/hour, 30/day |
| Site | 10/minute, 30/hour, 100/day |

These are request budgets, not counts of successfully delivered emails. Existing
endpoint-specific limits also apply. Recipient throttles retain generic accepted
responses; IP/site limits use HTTP 429. Preserve atomic locking and deadlock
retries rather than replacing these with per-process counters. Review capacity
before adding another product: the small site-wide budget will be shared too.

Off-screen honeypots and known email-to-SMS gateway blocks are active in the
reviewed source. Optional Turnstile is implemented with server-side success,
hostname and action checks; partial configuration fails startup, and validation
outages fail closed. It applies to email-generating forms, not login or link
consumption. It was not configured at the last deployment verification; its
current live key presence must be checked without printing secrets.

All account email uses `NektronAI <info@nektron.ai>`, with Nektron, Inc. as the
legal footer. SES sending region is `us-east-2`. Domain and sender DKIM signing
were verified there on September 24, 2026. Do not change the sender to a new
domain or region without verifying authentication and permissions in that region.

October's unsolicited messages were genuine form-triggered verification/reset
emails, not evidence of stolen credentials. Preserve generic responses, safe
logging, suppression/bounce handling and mail budgets. Never log passwords,
action tokens, reset links or user-submitted message content. SES acceptance
does not guarantee inbox delivery; do not disable bounces just to hide abuse.

## Recommended Nektron Mail integration

This section is proposed work, not functionality already implemented for Mail.
First establish whether Mail is desktop, web, or both and what its account unlocks.

For a desktop app, provide Create account and Sign in entry points that use the
system browser and first-party NektronAI account pages, styled consistently with
the existing site. Return to the app through an approved authorization flow;
do not collect website cookies, embed credentials, or simulate the Origin header
to turn the browser login route into an unsupported native login API.

Use a separately registered Mail client with Authorization Code plus PKCE S256,
state verification, a narrowly validated callback, and a Mail-specific resource
audience and scopes. A native client cannot keep a client secret. Keep refresh
tokens in OS-protected credential storage, with short-lived access tokens,
refresh rotation/replay protection and revocation. A browser login or email
verification completion is not evidence of an authenticated desktop session.
Native-app browser/PKCE guidance: [RFC 8252](https://www.rfc-editor.org/rfc/rfc8252).
Token and redirect protections: [RFC 9700](https://www.rfc-editor.org/rfc/rfc9700).

The current `connector_oauth.py` is a reference implementation, NOT a reusable
Mail client registration. It hardcodes a ChatGPT client, ChatGPT callbacks,
Database Connector scopes/resource audience and a configured-database check.
Never reuse its token audience, client ID or connector permissions for Mail.
Add a reviewed, isolated Mail integration without breaking those flows. The
existing OAuth discovery is not proof of a general OIDC service; no Mail ID-token
or userinfo contract is implemented here. Choose an explicit authenticated
subject/profile contract rather than treating arbitrary OAuth tokens as identity.

The existing website return destinations in `account.js` are a fixed connector
allowlist. There is no `returnTo=mail` flow. Add a validated Mail-specific return
flow rather than accepting arbitrary redirects or transmitting tokens in URLs.

If Mail is a separately hosted web app, use a server-side authorization flow and
its own secure session. Do not broaden the website cookie to every subdomain,
disable CSRF, or allow arbitrary origins. A page genuinely hosted on nektron.ai
can reuse the existing same-origin session, but product authorization is separate.

## Configuration and code map

Secrets live in AWS Secrets Manager `nektron/website/accounts`, region
`us-east-2`, loaded through `NEKTRON_ACCOUNT_SECRET_ARN`. Key names include
`NEKTRON_SITE_ORIGIN`, `NEKTRON_ACCOUNT_ENABLED`, `NEKTRON_DB_*`,
`NEKTRON_AUTH_EMAIL_FROM`, `NEKTRON_EMAIL_REGION`, optional
`NEKTRON_TURNSTILE_SITE_KEY` and `NEKTRON_TURNSTILE_SECRET_KEY`, and optional
`NEKTRON_ACCOUNT_BLOCKED_EMAIL_DOMAINS`. Preserve all other fields when updating.
Settings load at process startup. No DB, AWS, signing or Turnstile secrets belong
in a desktop binary, frontend bundle, chat, or Git.

Paths below are relative to `C:/Development/Projects/NektronAI`:

| Source | Purpose |
| --- | --- |
| `website/server/accounts/app.py` | API, CSRF, sessions and lifecycle orchestration. |
| `website/server/accounts/store.py` | User persistence, transactions, token and shared-budget logic. |
| `website/server/accounts/credentials.py` | Password hashing and email normalization. |
| `website/server/accounts/account_profile.py` | Required/optional profile validation. |
| `website/server/accounts/abuse.py` | Turnstile and blocked email domains. |
| `website/server/accounts/mail.py` | SES sender and verification/reset templates. |
| `website/server/accounts/schema.sql` | Account support tables, not a replacement User table. |
| `website/server/accounts/connector_oauth.py` | Connector-specific OAuth and discovery, not Mail-ready. |
| `website/server/accounts/connector_oauth_store.py` | Hashed OAuth codes, refresh families and revocation. |
| `website/assets/account.js`, `account.css`, `account-countries.json` | Website account UI, challenges and country data. |
| `website/signup.html`, `login.html`, `verify-email.html`, `forgot-password.html`, `reset-password.html`, `account.html` | First-party pages to preserve. |
| `website/scripts/configure_accounts.py`, `migrate_account_profile.py` | Existing provisioning/migration tools; do not run blindly on production. |
| `website/.platform/hooks/postdeploy/60_accounts.sh` | Account service deployment and nginx proxy. |
| `website/server/accounts/README.md` | Setup and operations; its older Auth0/connector introduction is stale relative to the native connector code. |

## Acceptance and rollout

1. Establish the exact source baseline and Mail app type before implementation.
2. Existing NektronAI users must not create a second identity; new Mail users
   must follow the same required fields, verification and recovery policies.
3. Keep branding as NektronAI and preserve the approved signup aesthetics.
4. Test pending, active, disabled, duplicate and pre-registered accounts; expired,
   reused and failed-delivery links; CSRF, Origin, rate limits, concurrent sends,
   Turnstile failures and token revocation. Protect all product-specific APIs.
5. For app authorization, test callback tampering, wrong client/audience/scope,
   wrong PKCE/state, replay, cancellation and refresh-family revocation. Do not
   grant access based on an email address supplied by the client.
6. Preserve existing website and Database Connector flows, including account
   ownership and pending authorization across login/signup/verification.
7. Use mocked mail and controlled test accounts. Browser test suites are local
   with mocked endpoints; they do not prove production mail delivery. Do not
   use real users or a shared production User table for destructive tests.
8. Review the live source bundle and infrastructure before deployment. Recent
   releases included newer connector work than the local committed baseline;
   deploying a stale or whole dirty tree can undo it. Deploy only reviewed changes.

Existing regression commands, from the NektronAI repository root:

```sh
python -m unittest discover -s website/server/accounts/tests -v
node website/tests/account_browser.cjs
node website/tests/account_abuse_browser.cjs
```

Install the backend requirements and browser-test dependencies in isolated
environments. Browser tests expect a local preview (default port 8771; REVIEW_URL
override). Add Mail-specific tests; the existing suite does not cover a Mail
client. Do not change production or enable Turnstile until the complete flow,
hostname configuration, rollback and verification plan have been reviewed.
