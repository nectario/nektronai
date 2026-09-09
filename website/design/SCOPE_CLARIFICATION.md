# Owner scope clarification — preserve the approved homepage

The merged Research Atelier homepage from PR #1 is the approved design. The
multi-page generated concept boards are **not** approval to redesign it, replace
copy, change product logos, invent routes, or add unavailable product downloads.

## Current implementation scope

- Restyle the existing non-home pages (GrowNet, formal specification, Docs,
  Downloads, Changelog, About, Privacy, Terms and Support) without changing their
  content. Their HTML remains byte-for-byte identical to this PR's base.
- On the homepage, add only the decorative Light/Dark background and two product
  cards: Nektron Write and Nektron Mail. Put these after the existing three product
  cards, at the same column width and using the existing card styling.
- Keep the approved homepage stylesheet and enhancement script unchanged. The
  secondary-page initializer explicitly excludes `/` and `/index.html`; the
  homepage loads only the bounded `homepage-additions.css`, never `atelier.css`.
- New cards keep the already-added brief product descriptions and Contact links;
  do not invent availability, downloads, operating-system support or pricing.

## Messaging discussion — explicitly deferred

The owner clarified that the product vision is to re-imagine existing apps and
make them better. Products have their own utility and purpose. The current
products do **not** use GrowNet, and wording such as "pressure-test" can imply an
integration that does not exist.

Do **not** change "pressure-test", the product/research loop, the research thesis,
or other homepage messaging in this PR. A separate discussion and explicit owner
approval are required before making those content changes. The existing GrowNet
limitations remain verbatim.

## Regression checks

Static guards preserve original homepage CSS/JS and semantic content and all nine
secondary HTML files. Browser comparison with the approved PR base checks existing
homepage element styles, hero and original product positions, hover/focus treatment,
and matching widths for the two added cards. The intended differences are the
background, the two cards, and the resulting downstream vertical displacement.

No merge or deployment is performed as part of this correction.
