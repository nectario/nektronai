# Nektron Mail product page rollout

Published **November 1, 2026 (America/New_York)** from website commit **4ad1faf**.

- Product page: https://nektron.ai/nektron-mail.html
- Installer: https://nektron.ai/assets/downloads/NektronMail.Setup.0.1.125.exe
- Direct download: https://d2j3ldvioomkd6.cloudfront.net/assets/downloads/NektronMail.Setup.0.1.125.exe
- Application version: **0.1.125**, Windows x64 preview.
- Installer size: **60,966,912 bytes**.
- Installer SHA-256: **955261D59DA1A4FE170A432E2D09641C5908E96A3CE30B8F733445FD79649F0D**.
- Authenticode: **Valid**, timestamped, **Nektron, Inc.** Verified locally before publication. S3 full-object checksum, public checksum metadata and a public range response were verified after upload.

## Content and screenshots

The page presents mailbox organization, durable local archives, precise local search, composing, formatted reading, rules and download progress. It clearly distinguishes the Windows preview from limited-access AI/database features, approved-user Gmail testing and capabilities still in development.

Six captures show the native application interface with synthetic sample data: light/dark mailbox views, search, compose, rules and download progress. WebP exports serve the page; application icons are supplied at 64/128 pixels. No private customer messages or credentials were used in these public images, and the interfaces were not fabricated with image generation.

## Deployment scope

The release was prepared as an allowlisted overlay on the exact active application source, preserving its deployment asset references:

- **14 changed/new static paths**: the Mail product card in `index.html`, one section in `downloads.html`, one URL in `sitemap.xml`, `nektron-mail.html`, its CSS/JS, six WebP captures and two PNG icons.
- **173 existing entries unchanged**, including all **47 backend, platform-hook and configuration entries**. All existing ZIP permissions were preserved.
- Shared CSS, JavaScript, local Sora font, wordmarks and backgrounds were checked against the active source. CSS differed from local source only by existing asset-version query strings, which were preserved.
- Deployment changed only the application version. No environment options, backend code, account data, permissions or infrastructure configuration were changed. No account forms were submitted.
- Installer publication used a new immutable object key without changing ACLs. Release binaries remain outside Git.

Elastic Beanstalk version label (UTC timestamp): **nektron-mail-page-20261102T043900Z-cdb5e0d682dc**. Final environment state: **Ready / Green**.

Candidate source ZIP SHA-256: **cdb5e0d682dc8bd35f34a2d25709f3d1bf81c1951b58d2d6430af7acb8e4a526**.

## Verification

- Local static checks: **22 passed, 3 skipped**. JavaScript syntax checks and the existing Vite build passed.
- Local browser review covered Light/Dark themes, 320/390-pixel mobile layouts, tab controls, image enlargement and keyboard behavior.
- All **14 deployed static paths** returned HTTP 200 with bytes matching the reviewed candidate.
- Existing login, signup, account, Database Connector, privacy, terms and support pages returned HTTP 200 and matched the preserved source. The anonymous account-session endpoint returned its expected unauthenticated response.
- The branded installer redirect returned HTTP 200 through the download host, with the expected content length and SHA-256 metadata.
- The site's existing `noindex` policy was preserved. Publication does not imply search-engine indexing.

Do not deploy this change using a broad S3 `--delete` or by replacing the active account-service bundle with an unreviewed local checkout. Future static updates should retain the same allowlist/content/permission verification approach.

## Title prominence refinement — November 2, 2026

Published from commit **164569b**. `Nektron Mail` is now the prominent H1, with the tagline visually subordinate. Local review confirmed the larger title in both themes and at 320 pixels without horizontal overflow; five Mail static checks and JavaScript syntax checks passed.

- Changed only **`nektron-mail.html`** and **`assets/nektron-mail.css`**, with cache token **20261102-title1**.
- Preserved **185 other entries**, including all **47 protected runtime/configuration entries**, and every existing ZIP permission. Installer, screenshot assets, JavaScript and environment settings were unchanged.
- Version-only deployment label: **nektron-mail-title-20261102T052357Z-61d9df91b8df**. Final health: **Ready / Green**.
- Live H1 verified as **Nektron Mail**. Both changed files returned HTTP 200 and matched the candidate hashes; existing routes, screenshots/icons and the signed installer passed read-only verification.
- Candidate SHA-256: **61d9df91b8df18120988701159d1184179bd62c02750e65df690bcc2e942ca2a**.