# Nektron Mail sales messaging — local review

**Prepared:** November 2, 2026  
**Status:** Published and verified on November 2, 2026, from website commit **b05900d**; deployment **Ready / Green**.
**Preview:** http://127.0.0.1:4180/nektron-mail.html  
**Website baseline:** `23125ba57385f65a417fadc1208de079fe95bc25`  
**Brief:** `C:/Development/Projects/Nektron Mail/docs/Nektron-Mail-Sales-Page-Handoff.md`

## What changed

- Kept the prominent **Nektron Mail** H1 and the brand line **Your mail. Finally yours.** The benefit statement now leads with **Personal mail. Work mail. One calmer workspace.**
- Put WorkMail, Gmail test-user eligibility and the Gmail access request beside the first download CTA, rather than leaving eligibility to the FAQ.
- Led the actual-app tour with personal/business mailbox convenience and separate identities. Updated its JavaScript copy as well as the initial HTML.
- Consolidated the everyday feature grid into three benefits: continuity between accounts, precise search and focused reading/writing. Useful list, layout and bulk-action details remain in the tour and a concise FAQ.
- Moved AI rules ahead of archiving and made the workflow concrete: **Describe → Review → Apply**. Preserved eligibility, execution and transmitted-data disclosures.
- Separated the durable local archive from the small-business database service. Explained customer/supplier correspondence and business decisions as use cases, with a purpose-specific business contact link.
- Clarified selected-mailbox search, separate inboxes, the 100-profile preview limit, storage/backup/recovery, database eligibility and public checkout status.
- Made the archive-help link open and navigate to its specific FAQ answer. Existing tour keyboard controls and screenshot enlargement remain intact.

## What stayed the same

Colors, font families and sizes, gradients, spacing tokens, main layouts, icon artwork, screenshot treatment and the Light/Dark themes are unchanged. CSS adds only the compact compatibility note and FAQ anchor clearance. No shared stylesheet or script changed.

The six real WPF application screenshots cover Light/Dark workspaces, search, compose, rules and download progress. Five captures remain from **0.1.125**; the search image is now a visually reviewed **0.1.131** production-control capture with synthetic accounts/messages. None are fabricated interfaces or private customer mail. Provenance remains in `assets/mail/README.md`.

## Product truth gate and release decision

After the initial local review, the owner approved publication together with the signed **0.1.131** search-fix release. That installer is now published and independently verified. Page and download-card facts are synchronized. Provider copy includes custom IMAP, POP3 and Exchange Server through HTTPS EWS, introduced in **0.1.128**. The earlier 0.1.126 download remains available unchanged.

The release gate is a verified signed 0.1.131 artifact, synchronized version/link/byte count/SHA-256, passing static checks, root visual review, and the root’s confirmation that the Mail search work is ready. Then publish an immutable installer and a five-path static overlay on the current live source; no backend or environment changes are included.

| Claim | Verified evidence and copy boundary |
| --- | --- |
| Providers | Current `windows/NektronMail/src/NektronMail/Shell/MailboxSetupProviders.cs:8` enables WorkMail, Gmail, IMAP, POP3 and Exchange Server. `windows/NektronMail/docs/CUSTOM_MAIL_CONNECTIONS.md:3` records custom connections introduced in **0.1.128**, explicit HTTPS EWS and SMTP setup, and POP3’s local folder/read state. Microsoft 365 / Outlook.com remains unavailable. `windows/NektronMail/docs/GMAIL_CONNECTIONS.md` retains approved Google test-user access. These claims are staged for the planned **0.1.131** download. |
| Multiple mailboxes | `windows/NektronMail/src/NektronMail/Providers/ProviderMailboxManager.cs:141`: 100-profile cap, no one-account-per-provider restriction; duplicate addresses/connections are rejected. Confirmed at `f565686` as well as current source. |
| Sidebar versus combined inbox | `windows/NektronMail/src/NektronMail/Workspace/RealMailboxWorkspace.MailboxGroups.cs:68`: All mailboxes groups folder trees; selecting a folder selects one mailbox. No combined-inbox claim. |
| Search scope | `windows/NektronMail/src/NektronMail/Shell/MailSearchPanel.xaml.cs` selects one mailbox and passes its ID to local search. The 0.1.131 release adds Cc/Bcc fields, automatic traversal of available local result batches, date/folder result ordering and opening a result in the normal message window. Copy retains the selected-mailbox and local-only scope. Filename search is distinct from attachment-content search; EmailDB and AI email search remain disconnected. |
| AI rules | `windows/NektronMail/docs/CLIENT_RULES.md:11–17,28–36`: supported read-state rules, exact folders, optional From/Subject conditions, timing, shared editable draft and explicit Apply. Service receives prompt/draft/folder names, without automatically attaching message bodies, attachments or provider credentials. Separate eligibility and authorization; no public subscription purchasing. These contracts are unchanged since `f565686`. |
| Database archive | `docs/MAIL_DATABASE_PILOT_ACTIVATION.md:3–15`, `docs/EMAILDB_CLIENT_INGESTION_STORAGE.md`, and `windows/NektronMail/src/NektronMail/ArchiveUpload/MailboxDatabaseArchiveService.cs:86`: separately authorized WorkMail IMAP pilot. Structured records/metadata are in EmailDB; original/attachment bytes are in S3. Gmail database archiving remains unavailable (`windows/NektronMail/docs/GMAIL_CONNECTIONS.md:27`); the custom IMAP, POP3 and EWS connections also remain outside the pilot. No customer-configured database, included external-AI query tool, compliance or permanence claim. |
| Runtime | `windows/NektronMail/src/NektronMail/NektronMail.csproj:4–5` and product README: Windows x64; WebView2 is required for formatted mail and not bundled. |

Paths in this table are relative to the canonical **`C:/Development/Projects/Nektron Mail`** checkout unless noted. No historical checkout, real mail, provider credentials, subscription changes or new paid services were used.

## Previously published download verification (0.1.126)

The page's actual download button was clicked in the background browser. The completed public download was checked locally; it was **not run or installed**.

- URL: https://d2j3ldvioomkd6.cloudfront.net/assets/downloads/NektronMail.Setup.0.1.126.exe
- Version: **0.1.126** / file version **0.1.126.0**.
- Size: **60,979,688 bytes** (displayed as **60.98 MB**).
- SHA-256: **359ED42CACDBD714979D18669998DDE4BE9E32D5C6F42FDDFB51188CFFE3F8F2**.
- Authenticode: **Valid**, **Nektron, Inc.**, timestamp certificate present.
- Public HTTP HEAD: **200**, matching byte length and SHA-256 metadata. Downloaded bytes also match the original signed release artifact.

## Initial sales-refinement validation (before 0.1.131 preparation)

- **10 Mail static checks passed**, including anchors, gallery assets, explicit eligibility, archive separation, scoped search, AI boundaries, contact destinations and exact download facts.
- Broader static checks: **27 passed, 3 optional historical-baseline guards skipped**, across the Mail, homepage, sitewide and homepage-vision checks. The 10 Mail checks are included in this total.
- JavaScript syntax and `git diff --check` passed.
- Existing `npm run build --prefix website` passed. It builds the existing homepage entry; its existing non-module script warnings remain. The Mail page was separately served and inspected in the browser.
- Browser inspection: Light/Dark, nominal **320, 390, 820 and 1440** widths and the default desktop viewport. No horizontal overflow or offscreen headings/controls. All referenced page images loaded; the unused lightbox image has no source until opened.
- All six tour tabs update title, description, image and enlargement URL. Keyboard Home/End and ArrowLeft/ArrowRight were exercised. Screenshot enlargement and Escape dismissal worked.
- FAQ answers expand/collapse, including the new entries. The archive deep link opens its target answer. Navigation and the download CTA reach their intended sections. Browser warning/error log was empty.
- Gmail/AI/business access requests reuse the existing **mailto** workflow, with `info@nektron.ai` and distinct decoded subjects. Their browser destinations and encoding were checked. An operating-system email composer and actual message submission were **not** tested; no email was sent. Access approval itself still occurs through the existing human support flow.
- No app executable, installer, backend, authentication, pricing, account data or production environment was modified.

## Visual review

The preview server remains running locally for review. Browser captures are stored beside this report:

| View | Before | After |
| --- | --- | --- |
| Desktop, Light | [Before](review/mail-sales-20261102/before-desktop.png) | [After](review/mail-sales-20261102/after-desktop.png) |
| Mobile, Light | [Before](review/mail-sales-20261102/before-mobile.png) | [After](review/mail-sales-20261102/after-mobile.png) |
| Complete page | — | [Desktop](review/mail-sales-20261102/after-desktop-full.png) · [Mobile](review/mail-sales-20261102/after-mobile-full.png) |
| Dark | — | [Desktop](review/mail-sales-20261102/after-dark.png) · [Mobile](review/mail-sales-20261102/after-mobile-dark.png) |
| Business archive | — | [Desktop section](review/mail-sales-20261102/business-archive-desktop.png) |

The numeric responsive checks are retained in [responsive-checks.json](review/mail-sales-20261102/responsive-checks.json). Small browser scaling/rounding differences are recorded in those observed viewport dimensions.

## Changed files and publication boundary

- `nektron-mail.html`: messaging, section order, business archive, eligibility and FAQ.
- `assets/nektron-mail.css`: narrowly scoped compatibility note and FAQ anchor spacing.
- `assets/nektron-mail.js`: matching tour copy and linked-FAQ disclosure.
- `tests/mail_product_static.py`: five additional checks and strengthened existing checks.
- `docs/NEKTRON_MAIL_SALES_REVIEW.md`, `docs/NEKTRON_MAIL_PRODUCT_PAGE.md`, and `docs/review/mail-sales-20261102/*`: review evidence.

**Published.** The signed 0.1.131 installer and the five-path static website rollout are live and independently verified. Website implementation commit **b05900d** is on `main`. The original before/after captures above document the initial sales refinement; the new native search capture and exact final download facts are documented below and in the rollout record.

## 0.1.131 publication preparation

The prior live source was captured read-only at **Ready / Green**, version `nektron-mail-icon-20261102T061225Z-65e5c8f59721`. The published overlay changed exactly five static paths: `nektron-mail.html`, `assets/nektron-mail.css`, `assets/nektron-mail.js`, the reviewed `assets/mail/search.webp`, and only the Mail section within the active `downloads.html`. It preserves the remaining 186 bundle entries, including 47 protected backend/configuration entries, and all existing ZIP permissions. No account, permission, environment-setting or infrastructure changes are planned.

The staged provider update passes **11 Mail static checks**, JavaScript syntax validation and `git diff --check`. The search screenshot has been replaced with the approved native 0.1.131 synthetic capture at **1180×760**, and its lossless WebP export was verified against every decoded RGBA pixel. Other screenshots, icons and shared site styles/scripts are unchanged. The gallery URL uses a new cache token for this replacement. The signed installer and public download checks passed. The final website suites passed **28 tests with 3 optional historical-baseline skips**; JavaScript syntax, diff checks and Vite build passed. The only build warnings were the existing non-module homepage scripts. The static rollout passed all live hash, route and health checks; no backend or account changes were included.

## Verified 0.1.131 installer

- Public URL: https://d2j3ldvioomkd6.cloudfront.net/assets/downloads/NektronMail.Setup.0.1.131.exe
- Version **0.1.131** / file version **0.1.131.0**; **61,035,888 bytes** (61.04 MB).
- SHA-256: **83B81A57E539A2F003F9D472878322028CD81C17DB80B66F3D15C83167D85318**.
- Authenticode **Valid**, publisher **Nektron, Inc.**, trusted timestamp present.
- Public HTTP **200**, exact byte count and SHA metadata, full-object storage checksum and public range bytes verified. The new version is immutable; previous releases remain available.

## Publication result

- Live URL: https://nektron.ai/nektron-mail.html
- Website implementation commit: **b05900d**, pushed to `main`.
- Deployment: **nektron-mail-sales131-20261102T202207Z-3e1ebc693360**, **Ready / Green**.
- Exactly five static paths changed, **186 existing entries** and all **47 protected entries** unchanged; existing permissions preserved. No account forms were submitted or environment settings changed.
- All changed live files matched their prepared SHA-256 values. Existing page/account routes, the branded download redirect and both prior signed installer versions were verified.
- Full release evidence is in [the product-page rollout record](NEKTRON_MAIL_PRODUCT_PAGE.md).

Final browser review passed: local 390-pixel Light/Dark layouts had no horizontal overflow; the live page showed the verified 0.1.131 download, new native search screenshot, working gallery selection, enlargement and Escape dismissal. Local live proof: `C:/Users/nektarios/AppData/Local/Temp/nektron-mail-sales131-live.png`. Mail application commit **73c24e0** is also pushed to its `main` branch.
