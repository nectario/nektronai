# Status Endpoint public information page

Published November 4, 2026: https://nektron.ai/status-endpoint.html

The page reuses Database Connector's Research Atelier product styles, local Sora
font, theme controls and responsive layout, with scoped Status Endpoint additions.
A homepage card links to it under AI tools & integrations; the sitemap includes
its canonical URL. The existing noindex policy is preserved; public direct-link
access does not imply search-engine indexing.

The page explains task/producer/work-item ownership, result authority, distinct
progress stages, ordered events, snapshot reconciliation, cursors and exact
retries. The developer guide includes approved onboarding requirements, independent
grant scopes, native HTTPS, a synthetic event, the actual Python CLI syntax and
four task API routes. It offers no credential entry, public enrollment or task
creation. The interactive example runs entirely locally without API access.

Claims were checked against StatusEndpoint source commit 91da4a4, its integration
and security contracts, the authenticated HTTPS rollout report and the completed
two-client pilot report from November 4. The latter confirms three synthetic CLI
events and actual compiled Mail reader/reconciler behavior, followed by revoked
grants and removed temporary credentials. This is described as a bounded pilot,
not full GUI/automatic-email validation or general customer availability. No
existing pilot access was used, recreated or activated for the website work.

## Deployment

- Page source commit: **1ddcc56**; final homepage spacing commit: **96183fc**.
- Final Elastic Beanstalk version: **nektron-status-page-20261104T181623Z-4807529705fe**.
- Environment **nektron-web-si-prod**, **NektronWeb**, Ohio/us-east-2: **Ready / Green**.
- Final ZIP SHA-256: **4807529705fe196c3479ca47c1c511d0c6d502f8ec4f6199726fbc88741b1df2**.
- Six static paths differ from the original active bundle: `index.html`,
  `sitemap.xml`, `status-endpoint.html`, `assets/status-endpoint.css`,
  `assets/status-endpoint.js`, `assets/status-endpoint.svg`.
- **189 existing entries** remain byte-identical, including all **49 protected
  runtime/configuration/package entries**; all original ZIP permissions remain.
- The homepage was patched into the exact active source, retaining existing asset
  version URLs. This is an allowlisted static overlay, not the index-only Vite output.
- Only the application version changed. Backend code, environment options,
  account permissions, infrastructure, credentials and Status Endpoint runtime
  were not changed.

## Verification

- Existing static and homepage vision suites: **29 passed, 3 optional historical
  baseline checks skipped**. The homepage suite passed again after spacing refinement.
- JavaScript syntax, HTML IDs/local links, synthetic JSON parsing, absence of
  credential forms, Git diff checks and the existing Vite build passed. Existing
  non-module homepage script warnings remain; the build is not the deployment bundle.
- Browser checks covered Light/Dark at nominal 320, 390, 820 and 1440 pixels
  (Chrome reported 321 at the smallest override), without page overflow; all
  images loaded. Example buttons and the CLI disclosure worked, including
  keyboard activation of the live illustration.
- **18 live static paths returned HTTP 200 with exact candidate bytes**, including
  all six changed files plus existing product, account, legal and shared theme files.
  The anonymous account-session read returned its expected unauthenticated response.
- Live browser review confirmed the homepage's 20-pixel card gap and keyboard
  navigation to the public Status Endpoint page, plus the correct H1 and illustration.

Local release evidence is retained in the November 4 task workspace:
`status-page-package-evidence.json`, `status-page-live-verification.json`,
`status-page-deployment.json`, and `status-page-candidate.zip`.

No deployment blocker, denied action or uncertain mutation remains.

## Shared accounts, current local capabilities and supplied icon — November 5

Published from **81028a4** to the same public URL. The page now states that users
must sign up or sign in to **NektronAI**, using the same account system as Database
Connector. The account panel links to the existing `signup.html` and `login.html`
routes. No unsupported Status return destination, separate account system or
automatic Status enrollment is implied. A shared account identifies the user;
Status scopes, exact task grants and worker authorization remain distinct.

The new development section reflects the inspected local candidate 0.5.0:
ChatGPT/MCP reads, task creation, durable dispatch, native OAuth and the one-shot
worker path. It explicitly states that these additions remain disabled and are
not live. Simulated OAuth-to-worker integration and the synthetic-provider CLI
protocol check are distinguished from real-model/worker qualification. The
analysis-only runner limit, remaining identity/migration/hosting/registration
decisions and worker-completion-versus-overall-verification distinction remain
visible. Sources: StatusEndpoint's current local `docs/CHATGPT_PLUGIN.md`,
`docs/OPERATOR_DRIVER.md`, `docs/RUNNER_READINESS.md` and
`docs/TASK_CREATION_DISPATCH.md`; this candidate includes uncommitted work and is
not represented as a published or deployed backend release.

The blue/cyan hub with a gold checkmark is the owner-supplied icon from
`StatusEndpoint/icon/StatusEndpoint_Icon_Package_v1_0/png/transparent`.
The 32-, 64- and 128-pixel PNGs are byte-identical to those approved exports,
with transparency and geometry preserved. They replace the earlier placeholder
in the page, account panel, favicon and homepage card. The prior SVG is retained
unchanged but is no longer referenced by those pages. Product branding is not
presented as a live verification indicator.

- Deployment: **nektron-status-account-20261105T051438Z-cc785b8f6b96**,
  **Ready / Green**.
- Bundle SHA-256: **cc785b8f6b961c843523b78a8c71617f763726b931b622a5ed38409577e13ae2**.
- Six static paths changed: homepage, product page, sitemap date and three PNGs.
  **192 existing entries**, including all **49 protected runtime/configuration/
  package entries**, remain byte-identical. Existing ZIP permissions are preserved.
- Only the website application version changed. No account backend, OAuth client,
  callback, grant, database migration, worker setting or live Status route changed.
  The native accounts worktree's unrelated in-progress implementation is preserved.
- **29 static/homepage checks passed; 3 optional baseline guards skipped**. Build,
  HTML IDs/local links/srcsets, icon provenance, no-credential-form and Git checks
  passed. The Vite build has its existing non-module script warnings.
- Light/Dark browser checks at nominal 320/390/820/1440 widths showed no page
  overflow, with all icons loaded. The new development disclosure and account links
  worked; the live account panel and keyboard focus were visually reviewed.
- All **18 live static paths** returned **200** and exact candidate bytes. Existing
  account/product/legal/theme files remained intact; the anonymous session read
  returned its expected unauthenticated response. No account form was submitted.

Evidence: `status-account-package-evidence.json`, `status-account-deployment.json`,
`status-account-live-verification.json`, `status-account-candidate.zip` in the task
workspace. No blocker remains for this public page update; live OAuth/worker
activation is separate pending work and was not performed.
