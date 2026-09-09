# NektronAI — Research Atelier homepage refinement

## Owner intent
A crafted, sophisticated continuation of the current research-first site, with
noticeable gradients on cards and controls. Not a splashy rebrand. NektronAI's
umbrella identity remains distinct from the independently branded products.

## Visual changes
- A pearl-cyan research-thesis panel, opaque inset signal surfaces and deep ink.
- Blue / champagne / slate positioning cards; pearl resource links; coordinated
  research, status, product and contact surfaces. Dark has separate opaque navy,
  warm-charcoal and slate materials, not an inverted Light palette.
- The existing Invent / Pressure-test / Refine sequence is a horizontal band on
  desktop and a vertical list on phones. No explanatory content is hidden.
- Quieter dotted texture at the top, rather than a repeated full-page particle
  image. Smaller, colored shadows and fine edges; no bouncing/lifting controls.
- More deliberate headline wrapping, more legible line-height, restrained
  metadata, gradient secondary buttons, visible focus and mobile menu behavior.

## Scope and fidelity
Only the homepage loads `assets/home-refinement.css` and `home-refinement.js`.
The original logo images, words, metadata, research caveats, external product
identities, navigation destinations and downloads are retained. The copy that
says GrowNet is not yet integrated into products stays visible and unchanged.
No new benchmarks, capabilities, integration claims or product availability are
inferred. Nektron Write/Mail can be added in a separate owner-approved content
pass; this PR does not invent their listing status.

`assets/styles.css`, `assets/site.js`, research documents, legal pages, variants,
release artifacts, manifests, server/deployment scripts and package dependencies
are unchanged. The shared site script continues to own theme persistence and
navigation toggling. The small home enhancement restores focus on Escape and
marks progressive navigation readiness; without JS the mobile links stay visible.

## Validation
- `python3 tests/homepage_static.py`: structure, scope, links, research caveats,
  approved image paths, accessible states, and sampled gradient contrast.
- Set `BASELINE_HTML` to the PR-base homepage to check every normalized word,
  anchor destination, image attribute and metadata value against the source.
  This is an optional design-only guard, not a blanket ban on future copy changes.
- `npm ci && npm run build`: the repository's existing Vite build. No runtime or
  application dependency changes are introduced by this design.
- `NODE_PATH=<isolated review tools>/node_modules node tests/homepage_browser.cjs`:
  actual static source on localhost; 320/390/768/900/1440/1920 widths in both themes,
  axe rules, root/container overflow, approved images, theme toggle/persistence,
  mobile menu/Escape/hash links, keyboard skip link, no-JS mobile navigation,
  forced-colors capture, and unchanged secondary-page route smoke checks.
- The review workflow uses read-only permissions, no secrets, no deployment and
  no production writes. It uploads before/after screenshots and a bounded source
  preview, excluding release binaries. Browser tools are isolated from the site.

Preserve Sora, the existing heading font. If the existing external font service
is unavailable, the system-sans fallback remains usable; review results record
font loading status. No fonts are added or redistributed by this change.

## Owner checkpoint
Start with the 1440px Light hero, the three positioning cards, and the full Dark
page. Then inspect the 390px mobile capture. Passing automated checks does not
replace visual approval, physical-device checks, or a full accessibility audit.
No merge or deployment is performed by this PR.
