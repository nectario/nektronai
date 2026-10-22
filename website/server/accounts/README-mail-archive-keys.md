# Mail local archive key recovery

Implemented and deployed with explicit owner approval on **2026-10-21**. Source defaults off; the approved existing account service now has recovery enabled. Controlled real-account/copied-archive validation remains separate.

## Production verification

The active version is **`nektron-mail-archive-keys-20261022T012701Z-207b277f460a`**, observed **Ready/Green** at 9:28 PM Eastern on October 21, 2026 (01:28 UTC October 22). Candidate SHA-256: `207B277F460AE51C65B600737FF1D940A1B075C2C2F9B7F4314A487384C86D36`.

- **137 account-service tests passed** locally, including 20 key-recovery tests and two Linux ZIP-permission contract tests. The extracted runtime candidate passed all 135 runtime/account tests; packaging-only tests run against the source preparation helper.
- Four existing runtime files were patched and two recovery modules added. All 170 other source entries, static assets and deployment hooks were preserved; the live consent stylesheet cache-buster was retained.
- Fourteen public health, Connector discovery/JWKS, Mail JWKS, account page and asset responses stayed HTTP 200 and byte-identical to their pre-deployment responses. Nine rejection/privacy checks passed: legacy and combined native requests with empty credentials returned 401; invalid scope returned 400; missing/forged bearer and browser-context key requests returned 401; no session cookie was set, and no-store/nosniff headers remained.
- An independent synthetic 32-byte KMS wrap/unwrap succeeded under the new dedicated key and exact app/purpose/archive/owner-hash context. It used the configured operator chain, not a signed-in application user, and created no registry row. A read-only postflight confirmed the existing registry schema and verified TLS/account-database target.
- No real account sign-in, user/refresh grant, archive registration, mailbox access, email or provider operation was performed by these deployment checks. Actual signed-app creation and recovery on another Windows profile still require the owner's pilot.

The first candidate exposed a packaging defect: newly added Python ZIP entries had mode 0600 and were unreadable by the dedicated service user. Deployment failed; the known original version was redeployed and verified Ready/Green with account health 200. The corrected immutable candidate changes only those two entry modes to 100644, not runtime bytes or unrelated modes. It passed the tests above before the successful deployment. The failed artifact was not overwritten; preparation now sets readable modes explicitly and two regression tests guard this boundary.

Nektron Mail may keep an encrypted archive on the user's own disk and recover its archive key after copying those files to another computer. This API keeps a protected recovery copy of that small key. It does not upload email, infer mailbox ownership, send mail, or constitute a backup of the archive files. The service has recovery custody; this is not zero-knowledge encryption.

## Permission and identity

The native session endpoint accepts either the existing exact `mail/archive.read` scope or, only when recovery is enabled, the explicit combined scope `mail/archive.read mail/archive.keys`. Ordering and spelling are fixed. Native clients must explain the additional account-assisted key recovery permission before requesting it. Existing read-only grants never acquire it during refresh. Refresh preserves the exact stored scope; a client wanting to change scope must sign in again. The legacy browser/PKCE authorization remains read-only.

Combined native access tokens add an opaque `grant_id`. Key routes verify the Mail signature, issuer, audience, client, exact scope, lifetime and grant ID, then recheck the live grant and current active/verified account with its server-side credential binding. They repeat that check after key recovery. Revoking the family, replaying a refresh token, disabling the account or changing the password blocks subsequent key releases. No password hash or credential tag enters the JWT or response. Already recovered keys on authorized devices cannot be remotely retracted.

## API

- `POST /api/account/mail-archives/v1/keys` with exactly `{"request_id":"<canonical nonzero UUID>"}` allocates an archive ID and random 32-byte data key. Repeating the same request ID under the same subject returns the same registered archive/key. The body is limited to 256 bytes inside the service's existing 4 KiB cap.
- `GET /api/account/mail-archives/v1/keys/<archive_id>` recovers an existing key only for its registered owner. Other-owner and unknown IDs both return `404 ARCHIVE_NOT_FOUND`.

Both require a Mail Bearer token and canonical HTTPS host. Browser cookies, Origin, Referer, Sec-Fetch headers, content encoding and query parameters are rejected. No browser session is read, set or deleted. Routes provide no CORS. Responses inherit `no-store`, `no-cache`, `nosniff` and no-referrer protections.

Success contains exactly `archive_id`, `owner_subject`, integer `key_version: 1`, and `data_key` (standard base64 encoding of 32 bytes). Owner identity always comes from the verified opaque shared `UserId`, never an email address or file-supplied subject. Key material is returned only over authenticated HTTPS and is never persisted as plaintext or logged.

## Storage and KMS

Apply `mail_archive_keys_schema.sql` explicitly to the existing configured account database. The single immutable `MailArchiveKeys` table stores archive ID, UTF-8 owner bytes, idempotent request ID, key version, wrapped key and creation time. Owner/request has a unique constraint. Runtime needs only `SELECT` and `INSERT`; no runtime DDL, updates, deletion, key replacement or owner reassignment is implemented.

Use a dedicated symmetric KMS encryption key, not the Mail/Connector signing keys and not an account password. Requests name the exact key ARN, algorithm `SYMMETRIC_DEFAULT`, and encryption context `{app: nektron-mail, purpose: local-archive-v1, archive_id: ..., owner_hash: SHA256(subject UTF-8)}`. The subject hash avoids placing the literal identity in KMS/CloudTrail context; it is still linkable metadata. Registry ownership uses the original byte-exact subject. KMS timeouts/retries and ciphertext sizes are bounded.

Configuration, preserving all unrelated existing fields:

```text
NEKTRON_MAIL_ARCHIVE_KEYS_ENABLED=true
NEKTRON_MAIL_ARCHIVE_KMS_KEY_ARN=<exact dedicated KMS key ARN>
NEKTRON_MAIL_ARCHIVE_KMS_REGION=us-east-2
```

The existing account service already depends on boto3; no new Python dependency or compute service is needed. Its role needs `kms:Encrypt`/`kms:Decrypt` only on the dedicated key, preferably constrained to the application/purpose context. SQL grants target this one new table. Default-off source registration does not create any AWS key, SQL table, IAM grant or secret setting.

## Validation and deployment

Run `python -m unittest discover -s website/server/accounts/tests -v` with the pinned requirements and Python 3.12. Synthetic coverage includes immutable retries/concurrent creation, cross-subject denial, live grant and password invalidation, exact scope preservation, browser isolation, malformed/bounded requests, KMS context and key validation, registry failure disclosure and no replacement of a failed existing key. No test needs AWS, real mail, SQL or private account data.

Production rollout uses the owner's explicit approval, read-only metadata preflight, reviewed additive DDL, scoped grants, dedicated KMS/IAM/config, and a Mail-only patch of the current live source bundle. Preserve website/Connector source and unrelated secret fields. No snapshots are requested. Verify health, legacy READ compatibility and Connector discovery before widening the pilot. Missing/forged/read-only tokens must not release keys. An authorized owner must separately check sign-in and copied-archive recovery in the signed desktop app; synthetic tests and public rejection checks do not prove that end-to-end path.
