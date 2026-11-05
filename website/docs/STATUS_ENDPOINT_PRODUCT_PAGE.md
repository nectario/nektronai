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

## Prominent signup, larger labels and flow diagram — November 5

Published the prepared changes after the owner's explicit **"Great. Please
commit/push/deploy"** approval. The earlier public-deployment hold was superseded;
the prior production version was checked before one approved rollout was started.

- Source commit: **51fbf86**.
- Deployment: **nektron-status-layout-20261105T155056Z-8d21728ce89e**,
  **Ready / Green**.
- Public URL: https://nektron.ai/status-endpoint.html
- ZIP SHA-256: **8d21728ce89e5643f17d8f7aa64fa209d74a8573f53f4ba8661ef4e9ad88de20**.

Sign Up now appears in the header and hero and links to the existing NektronAI
signup page. The `#account` navigation and account panel remain. Small section
and workflow labels rise two 2-pixel type-scale steps, from 10 to **14 px**;
the product-lockup label rises from 11 to **15 px**. Mobile header refinements
keep the existing branding, signup and theme control together on the first row.

The new accessible SVG diagram explains account/task authorization, producer
updates and evidence, ordered status storage/snapshots, authorized consumer
reads, and designated overall-result authority. A separate vertical mobile SVG
preserves readable text. The caption distinguishes the tested evidence flow from
the separate ChatGPT dispatch/worker development. The diagrams make no execution
or independent-truth claim.

Exactly **four static paths** changed: `status-endpoint.html`, its scoped CSS,
`assets/status-endpoint/how-it-works.svg` and `how-it-works-mobile.svg`.
The approved bytes match the locally reviewed hashes. **196 existing entries**,
including all **49 protected runtime/configuration/package entries**, remain
byte-identical, with all existing ZIP permissions preserved. Only the website
application version changed; unrelated account-backend working files remain intact.

Validation:

- Prepared change checks: **29 passed, 3 optional baseline guards skipped**;
  existing Vite build, Git diff, HTML IDs/local assets and accessible SVG checks
  passed. Existing non-module homepage script warnings remain.
- Live browser review at nominal **320, 360, 390, 768, 820, 1100 and 1440 pixels**
  in Light and Dark: Sign Up remained in the first screen, no page overflow,
  and the example development section label measured **14 px** in all 14 checks.
  The smallest browser override reports 321 pixels.
- Both live diagram sources loaded with their expected 1100x550 and 360x1020
  intrinsic dimensions. The desktop diagram was visually reviewed, and the
  mobile source switch and retained `#account` navigation were verified.
- **16 public static paths** returned HTTP **200** and exact candidate bytes,
  including all four changed files and preserved product, account, legal and
  shared-style routes. The anonymous account-session read remained unauthenticated.
  No account form was submitted.

Evidence in the task workspace: `status-layout-package-evidence.json`,
`status-layout-deployment.json`, `status-layout-live-verification.json`,
`status-layout-candidate.zip`, and the historical local review record
`status-layout-local-evidence.json`. Its former publication hold is historical;
the approved live deployment is recorded here. No blocker remains for this release.

## Shared-goal graph in light and dark themes - November 5

Published the graph after the owner's explicit "Yes please!" approval to commit,
push and deploy the prepared diagram. The initial rollout revealed that a returning
browser could retain the former dark SVG. Versioned URLs now refresh all four
diagram assets without requiring visitors to clear their cache.

- Graph source commit: **97c0b1d**; asset-cache correction: **e1e0da1**.
- Final deployment: **nektron-status-graph-20261105T170652Z-580358d89730**,
  **Ready / Green**.
- Public URL: https://nektron.ai/status-endpoint.html#how-it-works
- ZIP SHA-256: **580358d89730cc637577466c8e6a995f510ec598b207a589fc0c2b9478654f1c**.

One shared goal contains three agent branches. Each agent has an assigned task and
one or more status updates. Solid arrows carry reports into Status Endpoint;
dashed arrows carry results back to agents polling with separately authorized read
access. The legend and caption explicitly distinguish polling from server push.
The conceptual goal maps to an API task and each assignment to a work item; the
example does not impose a one-work-item-per-producer API restriction. The goal
remains in progress while release and verification work remain incomplete.

Separate desktop and vertical mobile SVGs use matching geometry and wording in
light and dark palettes. The site's existing theme toggle selects exactly one
picture; the vertical layout applies through the 950px breakpoint and is capped
at 440px for tablet legibility. Signup placement and enlarged labels remain.

Validation:

- Static/homepage suites: **29 passed, 3 optional baseline guards skipped**.
  HTML IDs/local asset references, SVG XML/accessibility, arrow counts, theme
  geometry/wording parity and Git diff checks passed. Sampled text contrast was
  at least **4.52:1**.
- Prepared layouts were reviewed locally at nominal **320, 390, 820, 1100 and
  1440px**, both themes. The final live page loaded the versioned mobile source
  at **390px** and desktop source at **1281px**, in both themes, with exactly one
  visible picture, correct intrinsic dimensions and no horizontal page overflow.
- All four final live SVGs were visually reviewed, including the three inward
  converging report arrows and outward polling-result branches. The default
  desktop page was also visually reviewed in both themes. Screenshot capture
  under a browser viewport override was unavailable; live responsive source and
  overflow checks used DOM measurements, supplemented by the local mobile review
  and full live vertical SVG screenshots.
- **22 public URL checks** returned HTTP **200** and exact candidate bytes:
  six changed paths, twelve preserved routes/assets, and four versioned SVG URLs.
  The anonymous account-session read remained unauthenticated. No forms were
  submitted and no pilot access was recreated.

Exactly six static paths differ from the previous layout release. All **196 other
existing bundle entries**, including **49 runtime/configuration/package entries**,
remain byte-identical; existing ZIP permissions are preserved. No runtime feature
was activated or environment setting changed. Unrelated account-backend work was
preserved.

Task-workspace evidence: `status-graph-package-evidence.json`,
`status-graph-deployment.json`, `status-graph-live-verification.json`,
`status-graph-browser-verification.json`, and `status-graph-candidate.zip`.
The initial rollout records are retained with the `status-graph-initial-` prefix.
No publication blocker remains.
