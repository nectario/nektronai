# Nektron Mail shared-account authorization

Implemented October 12, 2026. This is source and synthetic test coverage, **not a
production deployment or Mail enrollment**. Existing signup, verification,
recovery, password policy, email budgets, and Database Connector stay in place.

## Product boundary

The Windows app uses the system browser to sign into the existing NektronAI
account. It never collects a website password, copies a browser cookie, embeds a
client secret, or receives database/AWS/Connector credentials. The stable subject
is the existing opaque `UserId`, not an email address.

Mail has its own public native client, signing key, resource, scope, consent,
pending session state, and authorization-server instance:

| Contract | Value |
| --- | --- |
| Issuer | `https://nektron.ai` |
| Endpoint prefix | `/api/account/mail-oauth` |
| Native client | `nektron-mail-windows` |
| Resource / access-token audience | `https://nektron.ai/mail` |
| Scope | `mail/archive.read` |
| Grants | Authorization code with PKCE S256; rotating refresh token |
| Access token | RS256, `typ=at+jwt`, lifetime 300 seconds |
| Callback | `http://127.0.0.1:{1024..65535}/nektron-mail/callback` |

No OIDC ID token is issued. Mail tokens cannot access Database Connector. A Mail
token also **does not by itself authorize any mailbox**: the archive API must
apply separately approved, exact server-side subject/account grants. Do not
infer archive ownership from the token's email, client-supplied mailbox filters,
or successful website login.

## Browser and native endpoints

- `GET /authorize`: requires `client_id`, `redirect_uri`, `response_type=code`,
  `resource`, exact `scope`, nonempty `state`, `code_challenge`, and
  `code_challenge_method=S256`. Optional `response_mode` must be `query`.
  Optional `screen=signup` starts account creation if not signed in; absent means
  sign in. Other parameters, repeated parameters, controls, and invalid callback
  shapes fail without redirecting or storing pending state.
- The callback allows the literal `127.0.0.1` host only. No localhost alias, IPv6,
  user info, query, fragment, escaped path, trailing slash, leading-zero port, or
  privileged port is accepted. The **exact chosen port and callback** are bound
  to the grant and checked again at exchange.
- Authenticated users see explicit account-specific Mail consent. `POST
  /authorize` requires the existing same-origin JSON + CSRF checks, a one-use
  consent nonce, and unchanged parameters/user. Denial returns only
  `error=access_denied`, `state`, and `iss`. Approval returns only `code`, `state`,
  and `iss`. Native code must validate state and issuer before exchanging a code.
- Unauthenticated requests store only validated parameters for ten minutes in
  `mail_oauth_pending` and use the fixed website `returnTo=mail-authorize` flow.
  `GET /resume` consumes this pending request. Expired requests must restart from
  Mail; completing signup does not automatically authenticate the desktop.
- Login rotation preserves fresh Mail and Connector pending requests, not consent
  nonces. Frontend return destinations remain a fixed allowlist. An explicit
  URL destination is preferred and Mail account-form links preserve it. When a
  verification/recovery link opens in a new tab, login can supply the fixed Mail
  resume fallback if only a Mail request is pending; stale Connector journey
  storage cannot override that fallback. No arbitrary return URL is accepted.
- `POST /token`: form-encoded public-client request; exact client and resource
  mandatory. Code exchange needs exact callback plus verifier; refresh needs the
  refresh token. Optional scope must equal `mail/archive.read`. Cookies, Basic or
  bearer authentication, query parameters, extra/mixed grant fields, and repeated
  fields are rejected. Active/verified status and credential binding are rechecked
  for every code/refresh exchange. Tokens are never returned in browser URLs.
- `POST /revoke`: form-encoded `client_id`, `token`, and optional
  `token_type_hint=refresh_token`. Revokes the client-qualified refresh family;
  unknown/already revoked tokens return success without revealing existence.
- `GET /jwks`: public RSA key only; no dynamic key URL is accepted from a token.
- `GET /profile`: Mail bearer access token, without browser cookie/query fields.
  Checks signature, key, issuer, single audience, client, exact scope, claims and
  lifetime; then reads the current active/verified account. Returns exactly
  `{sub,email,display_name}`. It does not return a credential tag, password hash,
  phone, country, mailbox list, or product entitlement.

All responses are no-store. Protected POSTs keep the website's existing Origin
and CSRF requirements. Only the two native token/revoke endpoints are exempt;
they reject ambient browser credentials. Requests are rate limited using the
existing shared server-side account budget store, with a separate Mail key
namespace. Exceptions retain the sanitized account-service error policy.

## Credentials and revocation

The existing `WebsiteOAuthGrant` / `WebsiteOAuthCredential` tables are reused with
the dedicated client ID; no DDL is introduced. Code lifetime remains 120 seconds,
refresh-family lifetime 30 days. Raw codes/refresh tokens are hashed at rest.
Mail credential records additionally bind exact resource and scope. The existing
store locks and consumes credentials atomically, rotates refresh credentials,
and revokes the family on replay. A failed exchange must restart rather than
retry a consumed code; clients must serialize refresh calls and must not blindly
retry an ambiguous refresh response.

The store's existing bounded client-qualified expired-grant housekeeping remains
unchanged. This is authorization-record housekeeping, not email archive deletion.
No mailbox data, website identities, or local mail caches are purged by sign-out.

Already-issued access JWTs can remain usable until their **five-minute expiry**
after refresh revocation, password reset, or website logout. Profile rechecks
active/verified account status, but does not introspect refresh families or carry
a password-derived value in the JWT. Archive APIs validating offline JWTs have
the same maximum access-token window; immediate global revocation would require
a separately designed server-side check. Password changes and ineligible account
status block subsequent code/refresh exchange. Website logout ends the browser
session only; desktop sign-out must revoke its refresh family and remove its own
OS-protected token, while retaining local email according to Mail policy.

## Disabled-by-default configuration and rollout gate

New settings, loaded at process startup:

- `NEKTRON_MAIL_OAUTH_ENABLED=true` enables the routes; omitted/other values leave
  them unregistered. Accounts must be enabled at the canonical HTTPS origin.
- `NEKTRON_MAIL_SIGNING_PEM`: **dedicated** RSA private key, 2048–8192 bits,
  exponent 65537. Never reuse the Connector key or put a key in Git/client code.
- `NEKTRON_MAIL_SIGNING_KID`: distinct, 1–64 ASCII letters/digits/underscore/hyphen.

Enabling this implementation, generating/provisioning a production signing key,
updating Secrets Manager, changing a database, deploying the account service or
archive API, and granting a real archive to a subject are **separate approvals**.
Do not run provisioning/migration scripts as part of source validation. Preserve
all existing secret fields and review the intended source bundle against the live
deployment before any approved publish. Disabling Mail must leave Connector and
website account routes working. Existing OAuth discovery remains Connector's;
Mail uses this explicit fixed contract, not a general OIDC discovery assumption.

The account pages currently reference a versioned `account.js` URL. An approved
deployment must update that asset version or invalidate the corresponding browser
and CDN cache before enabling Mail; serving an old script can lose the fixed
Mail return destination. Include a warm-cache existing-account and signup return
check in deployment acceptance. This source task does not purge production caches.

## Synthetic validation

Use an isolated Python environment with `requirements.txt`, then from repo root:

```sh
python -m unittest discover -s website/server/accounts/tests -v
```

`test_mail_oauth.py` covers real Authlib code/PKCE and refresh exchanges with
synthetic users and an in-memory implementation of the existing credential-store
contract; no live SQL, AWS, real users, or outbound emails. It covers invalid and
expired grants, callback/nonce/state tampering, replay, credentials, scopes,
resource/client separation, cancellation, active/verified account checks, minimal
profile claims, and both Connector and Mail servers enabled together. These
tests are not a live database concurrency or deployment proof.

For local browser tests, serve `website/` on loopback port 8771 (or set
`REVIEW_URL` to a loopback URL) and provide Playwright + `@axe-core/playwright` in
an isolated Node environment:

```sh
node website/tests/account_browser.cjs
node website/tests/account_abuse_browser.cjs
node website/tests/mail_account_browser.cjs
```

These mock all account actions; the Mail test also blocks external requests and
checks fixed return navigation, minimal consent, one-use submission, narrow and
desktop layouts, light/dark themes, and accessibility. They do not prove live
email delivery, real account grants, or production authentication.
