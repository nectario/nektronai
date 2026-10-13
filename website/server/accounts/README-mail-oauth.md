# Nektron Mail shared-account authorization

Implemented October 12, 2026; the shared Mail sign-in service was deployed and
activated with explicit approval on October 13, 2026. Public endpoint checks
passed; the controlled real-account desktop sign-in pilot remains pending.
This is **not Mail enrollment or access to any mailbox**. Existing signup,
verification, recovery, password policy, email budgets, and Database Connector
stay in place.

## Production deployment status

The approved deployment extends the existing account service at `https://nektron.ai`.
It uses a dedicated Mail signing key in the existing account secret, preserving
all unrelated secret fields and the Connector signing identity. The bundle was
built from the actual live application, overlaid only with the five reviewed
Mail/account runtime files and account CSS/JS cache-version references. The only
additional styling correction underlines verification-success links. Deployment
hooks and unrelated application content were preserved.

Acceptance on October 13, 2026:

- Elastic Beanstalk reports the candidate active, Ready and Green.
- All 84 account-service tests pass against the deployment candidate.
- All three mocked browser suites pass: 36 responsive/theme checks, 24 account
  accessibility scans, six Mail accessibility scans, native form actions, abuse
  controls, Mail return/consent/cancellation and Connector isolation.
- Account health is ready. Connector discovery and JWKS are byte-identical to
  the pre-deployment responses; the Mail JWKS matches the dedicated staged key.
- Missing/forged Mail bearer tokens return 401; an unregistered authorization
  client returns 400 without a redirect. Privacy/security headers are present,
  backend source routes return 404, and deployed account/consent assets match
  the validated candidate.

No schema migration, mailbox grant, archive API deployment, provider change or
mail sending was performed. No live signup emails, real-user password changes
or user token exchanges were exercised by the deployment checks. Complete a
controlled desktop sign-in before calling the end-to-end pilot validated.

## Product boundary

The original Windows flow uses the system browser to sign into the existing
NektronAI account. A separately implemented **first-party native sign-in** route
now supports the owner's requested in-app email/password dialog. The source
changes described below are not evidence of a deployed native endpoint; the
production acceptance above covers the earlier browser/PKCE deployment only.
Neither flow copies browser cookies, embeds a client secret, or receives
database/AWS/Connector credentials. The stable subject is the existing opaque
`UserId`, not an email address.

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

All responses are no-store. Protected website POSTs keep the existing Origin
and CSRF requirements. The two native token/revoke endpoints and exact
`mail_native.create_session` endpoint are exempt; each applies its own explicit
credential and request checks. OAuth requests are rate limited using the existing
shared server-side account budget store, with a separate Mail key namespace.
Native password authentication instead shares the **exact website login budget**
described below. Exceptions retain the sanitized account-service error policy.

## First-party native credential sign-in

Implemented in source on October 13, 2026 following the owner's explicit choice
of an in-app credential dialog and approval to deploy the new API. The route is
registered only when the existing Mail feature and account service are enabled;
it uses the same dedicated Mail signing key. No new secret field, password store,
database table, mailbox grant, or Connector permission is introduced.

This is **not an OAuth password grant**, and does not claim the system-browser,
SSO, phishing-resistance, or PKCE security properties of the browser flow. The
first-party Windows application necessarily handles the entered password in
memory and sends it directly to the fixed HTTPS account service. It must not
persist, log, forward, or put that password in command lines, URLs or diagnostics.
The server cannot attest that an arbitrary HTTP caller is the genuine app merely
from its public client ID or absence of browser headers. Signup, verification and
password recovery remain on the website. Existing browser/PKCE sign-in is retained.

`POST https://nektron.ai/api/account/mail-native/session` accepts JSON with exactly:

```json
{
  "email": "synthetic-user@example.com",
  "password": "synthetic example only",
  "client_id": "nektron-mail-windows",
  "resource": "https://nektron.ai/mail",
  "scope": "mail/archive.read",
  "approve": true
}
```

The client must show the permission being approved in the dialog. `approve` must
be the boolean `true`; it is an explicit first-party UI acknowledgement, not a
server-rendered OAuth consent transaction or proof of a trusted client.

- Require canonical-host HTTPS, `application/json` (optional UTF-8 charset), a
  maximum 4096-byte request body, no query fields, and no duplicate/unknown JSON
  fields. Compressed or non-UTF-8 payloads are rejected.
- Reject `Cookie`, `Origin`, `Authorization`, `Referer` and every `Sec-Fetch-*`
  header, including empty-present headers. Do not expose CORS or accept browser
  form submissions. The client must never manufacture an Origin or CSRF header.
- `DatabaseSessions` isolates this exact path before attempting to read a cookie,
  and never saves/deletes a browser session or emits `Set-Cookie`, including
  rejection and failure cases. Website session and CSRF behavior is unchanged.
- Reuse normalized email, bounded password handling and Argon2 verification,
  including dummy-hash work for nonexistent accounts. Reuse the exact existing
  `login:ip:` (30 per ten minutes) and `login:email:` (10 per ten minutes) budgets;
  alternating website and native login does not double the password-attempt budget.
- Unknown accounts, incorrect passwords, inactive or unverified accounts all
  return the same `401 {"error":"INVALID_CREDENTIALS"}`. Other errors are
  `400 INVALID_REQUEST`, `413 REQUEST_FAILED`, `429 TRY_LATER`, or sanitized
  `503 ACCOUNT_UNAVAILABLE`. No account status is disclosed by this route.
- Existing `finish_login` rechecks the account and password hash. Signing rechecks
  the credential binding, then a transaction locks the account row and checks
  active/verified status and the credential tag again before atomically inserting
  a new grant family and its hashed refresh credential. Failed persistence never
  returns either credential. Password reset uses the same account-row lock.

Success returns exactly `access_token`, `refresh_token`, `expires_in` (300),
`token_type` (`Bearer`) and `scope` (`mail/archive.read`). The access token retains
the existing minimal Mail claims, dedicated key and five-minute lifetime. The
native refresh family has the explicit `authentication_flow=mail-native-session-v1`
metadata marker, without an invented callback or PKCE challenge. That marker is
accepted only for refresh credentials, never authorization-code exchange.

The existing `/api/account/mail-oauth/token`, `/revoke` and `/profile` endpoints
are reused afterward. Thirty-day family expiry, hashed storage, atomic rotation,
replay revocation, credential-change checks and client/resource/scope isolation
remain in force. The new family-creation method uses the existing tables; it does
not execute DDL. Successful native login still grants **no mailbox by itself**.

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

The October 13 approval covered Mail sign-in activation, its dedicated signing
key in the existing secret, and this account-service deployment only. Database
changes, archive API deployment, and granting a real archive to a subject remain
**separate approvals**. Later signing-key or production configuration changes
also require explicit approval.
Do not run provisioning/migration scripts as part of source validation. Preserve
all existing secret fields and review the intended source bundle against the live
deployment before any approved publish. Disabling Mail must leave Connector and
website account routes working. Existing OAuth discovery remains Connector's;
Mail uses this explicit fixed contract, not a general OIDC discovery assumption.

Account pages reference versioned `account.js` and `account.css` URLs. The live
deployment uses a new version on every referencing page and the consent stylesheet;
the public asset bytes were verified against the candidate. Future deployments
must preserve cache versioning; serving an old script can lose the fixed Mail
return destination. Include warm-cache existing-account and signup return checks
in the controlled pilot. This deployment did not purge production caches.

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
