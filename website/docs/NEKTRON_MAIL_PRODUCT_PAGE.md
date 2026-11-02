# Nektron Mail product page rollout

> **Latest publication — November 2, 2026:** The reviewed sales refinement and signed **0.1.131** search release are live. Provider compatibility, local-search capabilities and the current download facts are synchronized. The five-path static rollout is verified **Ready / Green**. See [the sales review and evidence](NEKTRON_MAIL_SALES_REVIEW.md) and the release record below.

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

## Transparent application icon and 0.1.126 download — November 2, 2026

The website now uses the same transparent, larger-envelope artwork as the signed **Nektron Mail 0.1.126** Windows release (Mail commit **f565686**). Authored 16/32-pixel PNGs supply the favicons; 64/128-pixel PNGs supply the page artwork. All four website files match the native exports byte-for-byte and have transparent corners. The 64-pixel page display size is retained; icon-only CSS corner clipping was removed. Fresh filenames and CSS cache token **20261102-icon1** prevent reuse of the former opaque tile.

- Current installer: https://nektron.ai/assets/downloads/NektronMail.Setup.0.1.126.exe
- Direct download: https://d2j3ldvioomkd6.cloudfront.net/assets/downloads/NektronMail.Setup.0.1.126.exe
- Size: **60,979,688 bytes**.
- SHA-256: **359ED42CACDBD714979D18669998DDE4BE9E32D5C6F42FDDFB51188CFFE3F8F2**.
- Signature independently verified as **Valid**, **Nektron, Inc.**, with a trusted timestamp. S3 full-object checksum, public checksum metadata and a public range response were verified after immutable upload. The previous **0.1.125** download remains unchanged and available.
- Deployment changed **seven static paths**: product HTML/CSS, the Mail-only downloads section and four new transparent PNGs. **184 existing entries**, including all **47 protected runtime/configuration entries**, and all existing ZIP permissions were preserved. Gallery images, JavaScript, old icons, backend code and environment options were unchanged.
- Version-only deployment: **nektron-mail-icon-20261102T061225Z-65e5c8f59721**. Final state: **Ready / Green**.
- Candidate SHA-256: **65e5c8f5972172b05338eb188b601978352c78859d112134ebb8a5dc6b32e8ae**.
- Five Mail static checks, JavaScript syntax and diff checks passed. The Windows release pipeline reported **1,804 passed, 10 opt-in checks skipped**.
- All seven deployed paths returned HTTP 200 with candidate-matching bytes. Existing routes, gallery/old icon assets, the anonymous account endpoint and both installer versions passed read-only verification. No account forms were submitted.
- Final live browser review passed in **Light and Dark**: the transparent icon loads, the prominent product title remains intact, and version **0.1.126** with the correct installer link is visible. A diagnostic capture is retained at `C:/Users/nektarios/AppData/Local/Temp/nektron-mail-transparent-icon-live.jpg` outside Git.

## Sales refinement and signed 0.1.131 search release — November 2, 2026

Published the owner-approved sales page from website commit **b05900d** after the Mail search fix in application commit **73c24e0** passed its signed release pipeline.

- Live page: https://nektron.ai/nektron-mail.html
- Deployment: **nektron-mail-sales131-20261102T202207Z-3e1ebc693360**, **Ready / Green**.
- Exactly five changed static paths: `nektron-mail.html`, `assets/nektron-mail.css`, `assets/nektron-mail.js`, `assets/mail/search.webp`, and only the Mail section within the active `downloads.html`.
- **186 existing bundle entries** remain byte-identical, including all **47 protected backend/configuration entries**. All existing ZIP permissions are preserved. Only the application version was updated; no environment settings, account permissions, authentication, database or infrastructure changes were made.
- Candidate bundle SHA-256: **3E1EBC693360B5001F45935C4C7C908654AC6AA66FCF4CB0006F4F5DA34E5870**. Protected-entry hash-manifest SHA-256: **66A37C3E24F59F1564733DF60979F8845A50269637E772DB564F96F385DD1D1F**.
- All five changed paths returned HTTP **200** with exact candidate hashes. The homepage, sitemap, remaining gallery assets, login, signup, account, Database Connector, privacy, terms and support routes retained the prior source. The unauthenticated account-session GET returned its expected response; no forms were submitted.

The copy makes personal/business mailbox convenience and reviewed AI rule drafting clearer, separates durable local storage from the WorkMail IMAP database pilot, and accurately includes custom IMAP, POP3 and Exchange Server through HTTPS EWS. Microsoft 365 / Outlook.com remains unavailable, and Gmail still requires approved Google test access. Search stays local to the selected mailbox; server, AI email and attachment-content search are not advertised as active.

The search illustration is an approved native **0.1.131** production-control capture with synthetic data, at **1180×760**. Its PNG is unchanged from the source, and every decoded RGBA pixel matches the lossless WebP export. No real mail appears in website images. The five other screenshots remain the 0.1.125 synthetic captures. The updated search asset has its own cache token; colors, typography and the established layout remain intact.

Installer:

- https://d2j3ldvioomkd6.cloudfront.net/assets/downloads/NektronMail.Setup.0.1.131.exe
- Version **0.1.131**, file version **0.1.131.0**; **61,035,888 bytes**.
- SHA-256: **83B81A57E539A2F003F9D472878322028CD81C17DB80B66F3D15C83167D85318**.
- Authenticode **Valid**, **Nektron, Inc.**, trusted timestamp present. Independent local size/hash/signature checks, full-object storage checksum, public HTTP 200 metadata and range bytes passed.
- The branded download redirect works. Previous **0.1.125** and **0.1.126** installer URLs remain available with their original sizes and checksums.

Validation: **28 website checks passed, 3 optional historical-baseline guards skipped**; Mail JavaScript syntax, diff checks and Vite build passed. Existing non-module homepage script warnings remain. The application signed-release pipeline reported **1,919 passed, 11 opt-in skipped**. Final browser review passed at 390-pixel width in Light and Dark without horizontal overflow. Live 0.1.131 download details were correct; the new 1180×760 search image, gallery tab, enlargement and Escape dismissal worked. Live proof is retained locally at `C:/Users/nektarios/AppData/Local/Temp/nektron-mail-sales131-live.png`.
