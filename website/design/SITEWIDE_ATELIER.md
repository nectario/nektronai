# Research Atelier — secondary pages and subtle background

Extends the approved homepage aesthetic to About, Docs, Downloads, Changelog,
GrowNet journal, GrowNet Formal Specification, Privacy, Terms, and Support.
The homepage receives the explicitly requested Nektron Write / Nektron Mail cards
and the same subtle background. No new product availability, operating-system,
pricing or download claims are introduced. The two new cards point to the existing
Contact section; no unverified product URL or placeholder download is fabricated.

## Content freeze

All secondary-page HTML files remain byte-for-byte unchanged. The new stylesheet
is loaded by a bounded presentation initializer prepended to `assets/site.js`.
The original theme, mobile-navigation and managed-download implementation remains
an exact suffix of that script. The initializer does not modify text or replace
HTML. It enables presentation only on the explicit canonical route allow-list.
It also works when the static site is served below a local preview subdirectory.

The existing homepage copy, links, metadata, images, product cards and research
qualifications remain in their original order. Two additive product cards are the
only content exception. In particular, About's existing portfolio text is not
silently rewritten during this content-frozen pass.

The stand-alone exported article, noindex holding page, public-safe snapshot and
historical design variants are not reinterpreted or restyled. Research source
Markdown/DOCX, release manifests, binaries, logo files and all infrastructure are
untouched. No API calls, collection forms, tracking or dependencies are added.

## Presentation

Same opaque pearl/cyan, champagne and slate materials as the approved homepage.
Primary and secondary buttons retain visible gradients. Research reading surfaces
are opaque and calm; original document typography/structure is retained. Research
tables receive restrained alternating rows and keyboard-scrollable wrappers.
The table of contents remains usable instead of growing beyond the viewport.
The same layout and focus treatment carries through both themes and small screens.

The background files are 800 x 450 WebP derivatives of only the text-free
background portion of an image-generated concept. No generated page, wording,
logo or UI screenshot is used as source content. Filament proportions are retained,
the image is feathered into the site canvas, and Dark is a luminance-remapped
companion rather than an inverted screenshot. The files are approximately 1.2–1.4 KB
each. They draw once behind the upper page, never tile or animate, have no pointer
or accessibility semantics, and are removed in forced-colors and print contexts.

## Progressive enhancement tradeoff

The homepage links the additive CSS directly. On secondary pages the initializer
loads it, then opts in after the stylesheet loads; if CSS fails or JavaScript is
disabled, the readable original presentation stays intact. This intentionally
preserves secondary document sources without a generated/build-time rewrite. The
first uncached visit can show the original presentation briefly while the small
shared stylesheet loads; subsequent visits reuse the same browser-cached asset.
No loading overlay, hidden content or forced layout lock is used.

## Validation

`BASELINE_SITE=/path/to/pr-base/website python3 tests/sitewide_static.py` verifies
all secondary HTML bytes, original homepage words/links/images/meta/IDs outside
the explicit added block, the unchanged original JavaScript suffix, bounded product
additions, image budget, scoped states, and sampled Light/Dark gradient contrast.
The baseline is supplied only for this design review; it is not a permanent ban
on future owner-approved copy changes.

The existing homepage checks remain. `tests/sitewide_browser.cjs` adds real served
page checks at 320/390/768/1440 widths, Light and Dark, keyboard navigation,
scrollable research tables, theme persistence, asset loads, selected axe rules,
forced colors, and the original no-JavaScript desktop fallback. Outbound links
are not followed. No live services, credentials, download writes or deployment.
The existing read-only review workflow exports the current and base source,
WebP assets and screenshots for owner review.

Local inline renders are layout previews using system-font fallback, not a claim
that local network-serving, external fonts or scripts were tested. Final CI
captures use the actual served HTML/CSS/JavaScript and are the primary review set.
