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
