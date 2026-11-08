# Status Endpoint OAuth extension: deployed, disabled

Built initially on 2026-11-05 and deployed on 2026-11-08, this extends the
existing native issuer with both Status flags disabled. The release did not
register a live client, enable a flag, create a signing key, enroll an agent or
worker, or issue a live credential. Existing Connector and Mail configuration
and public signing keys were verified unchanged after deployment.

## Reuse and compatibility

The existing issuer, authorize/token/revoke routes, JWKS, account login, S256
PKCE, nonce/CSRF consent, credential-tag rechecks and hashed grant store are reused.
The existing signing configuration remains NEKTRON_CONNECTOR_SIGNING_PEM/KID;
the legacy name is retained. No key material was copied from a live secret.
This is a shared issuer signing boundary with resource/client/scope separation,
not a separately provisioned Status signing identity. Mail's distinct signer and
OAuth implementation are unchanged.

Database Connector keeps its client IDs, exact callbacks (including the existing
compatibility callback), audience, read/manage scopes, consent content, database
setup gate, management endpoint and refresh behavior. Old code/refresh data keep
the legacy format; the reader always treats their scope as database-connector/read.
When the new flags are absent, the root metadata still advertises only that
Connector scope. Status requests do not call has_connector_database or issue a
management token. Status client quotas use separate request-budget keys.

## Disabled settings and exact bindings

| Setting | Default | Required only after review |
| --- | --- | --- |
| NEKTRON_STATUS_OAUTH_ENABLED | false | true enables the Status ChatGPT client |
| NEKTRON_STATUS_CHATGPT_CALLBACK | absent | Exact HTTPS callback shown for this ChatGPT registration |
| NEKTRON_STATUS_WORKER_OAUTH_ENABLED | false | true enables the access-only worker client |
| NEKTRON_STATUS_WORKER_CALLBACK | absent | Exact http://127.0.0.1:PORT/status-endpoint/callback, port 1024-65535 |

No callback is guessed or inherited from Database Connector. Both new clients
are public authorization-code clients with mandatory S256 PKCE and exact resource
parameters. No dynamic registration, client secret or password grant is added.

| Client | Resource | Allowed scope |
| --- | --- | --- |
| nektron-status-endpoint-chatgpt | https://status.nektron.ai/mcp | task-status:read required; optional task-status:read-internal, task-status:report, task-status:create, task-status:dispatch |
| nektron-status-endpoint-worker | https://status-worker.nektron.ai/api/task-worker/v1 | task-status:worker only |

Status consent lists only the requested permissions and states that tenant/agent/
task grants remain separate. Scope, client, resource, callback and authentication
flow are frozen into the code data. Token exchange and refresh recheck the exact
binding. Refresh cannot add or drop scopes. Cross-client/resource/code reuse is
rejected. Status JWTs do not carry the Database Connector-specific verification
claim and never contain a password hash or credential tag.

Access tokens expire in 300 seconds. The ChatGPT client retains the existing
rotating 30-day refresh-family mechanism after explicit consent. The worker has
authorization_code only: no refresh token is generated or stored. Its code lives
120 seconds and its code-family row is bounded to 300 seconds. The issued access
token is valid for at most five minutes after exchange. These times describe
different artifacts; expiry of a family row is not JWT revocation.

OAuth refresh revocation prevents future refresh, while already-issued JWTs can
remain valid until their short expiry. Status Endpoint additionally checks its
own current native account, tenant, agent/task/worker grants and credential tags.
Those grants must be provisioned separately; OAuth consent does not create them.

The 0.6.0 local Status extension adds task-status:report as a separately consented
scope for immediate attributed progress reporting. Existing READ refresh families
cannot gain it; reconnect with explicit consent after approved activation.
Reporting does not require a Database Connector connection or dispatch. Native
signup, email verification and login are reused; existing members reuse their
account. Task/workspace/producer authority remains in separately approved Status
application grants, never in a task ID, email address or status prose. The shared
login page's fixed Status resume fallback was corrected locally in the preceding
change. No registration, account, grant, credential or access flag was created or
enabled by either source change. Database Connector and Mail behavior remain.

## Migration and hosting review

No new accounts table or column is needed. WebsiteOAuthGrant and
WebsiteOAuthCredential already hold client-qualified JSON credentials; new
Status data use those existing fields. Existing grants are not rewritten or
upgraded. The worker's shorter code-family expiry uses the existing ExpiresAt.
Do not run configure_accounts.py --apply or any deployment script as part of
this review; no account provisioning or IAM/secret expansion is required merely
to inspect this change.

A future website package must include status_oauth_clients.py beside
connector_oauth.py, connector_oauth_store.py and app.py, with normal Linux service
read permission (regular source files, mode 0644). Retain /server/ source denial
and private account-service routing. Existing OAuth endpoints are reused; no
new public account route is introduced. Status MCP and worker ASGI hosting remain
separate reviewed surfaces; adding clients here does not deploy those services.

Before enabling settings, approve the common signing-boundary reuse, exact
callbacks, native account subject, tenant/registered agent and corresponding
application grants. Preserve existing Connector settings and signing identity.
No temporary pilot grants or deleted launchers are restored.

## Validation

All 213 native account/application/OAuth tests passed for the released source. Synthetic tests cover scope/resource/
client/callback isolation, native-account
revocation, nonce scope changes, worker no-refresh behavior, bounded SQL intent,
and unchanged Connector flows. The full accounts suite includes existing Mail
and account regressions. A separate opt-in cross-repository test exercises the
native PKCE token through Status Endpoint JWT verification, broker, operator
driver and a synthetic Codex event stream. No real model, AWS or live database
is used by those tests.

## In Simple Terms

**Built and deployed:** Disabled Status clients in the shared native issuer.
**Not activated:** Live Status client registration or application access grants.
**Live now:** Existing Connector and Mail behavior; both Status flags remain off.
**Next:** Review exact bindings and application grants before any activation,
credential issuance or real task. Source commit: `ee4af02`.
The verified production release, migration and rollback details are recorded in
[shared application accounts](README-applications.md#verified-production-foundation-release-2026-11-08).
