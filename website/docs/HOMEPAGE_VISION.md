# Homepage: product mission and GrowNet research ambition

## Owner-approved framing

NektronAI has two complementary ambitions, not a current GrowNet-to-products
technology pipeline. Products reimagine the apps people rely on in everyday life
and professional work. AI belongs in their core functionality, beyond simply
adding a chatbot. They deliver value in their own right; revenue can also help
sustain long-horizon research.

GrowNet is **our boldest undertaking**: aiming to challenge the assumptions behind
today's AI, pioneer a radically different approach, and build a new foundation for
what intelligent systems can become. This is an ambition, not a claim of completed
capabilities. Existing research-in-progress and not-yet-integrated caveats remain.

The stated product path is to continually introduce new applications, initially
powered by existing AI models, and begin integrating GrowNet as it proves its
capabilities. No deadline, blanket migration, existing integration, or product
feature is invented.

## Changes

Only `website/index.html` changes in production. The hero, research-ambition panel,
three commitments, supporting positioning copy, operating-model explanation,
product introduction/note, short Write/Mail descriptions, footer summary and text
metadata express this framing consistently. The former pressure-test/proving-ground
narrative is removed from the homepage. Internal CSS class names stay unchanged.

The three established standalone brands are labeled **Independent brands** in
Quick facts; the Nektron Write/Mail cards remain explicitly part of the Nektron
product family. All five product cards and their link destinations are retained.

The approved layout, DOM element structure, gradients, typography, background,
logo, icons, stylesheets, client scripts, primary/secondary actions, resource shelf,
contact information, copyright and legal links are not redesigned. Copy naturally
changes line wraps and some section heights.

The entire technical `#research` section, including the Golden Rule and status
caveats, is byte-for-byte preserved. No GrowNet journal, formal specification,
download, other canonical page, archived variant or infrastructure is changed.
Existing secondary-page company copy and the original social-image artwork are
intentionally not rewritten as part of this homepage task. The social image's alt
text still describes that unchanged artwork; title/description metadata use the new
mission. A sitewide editorial/social-artwork pass is a separate scope decision.

## Validation

`python3 tests/homepage_vision.py` checks the two ambitions, corporate voice,
independent product value, core AI functionality, model/GrowNet capability boundary,
five products and metadata consistency. In this PR, `VISION_BASE_REF` enables an
exact structural/link/resource guard and restricts all production changes to
`index.html`. Research and navigation source are compared byte-for-byte.

The existing build, homepage and sitewide browser reviews stay enabled. Only for
this approved copy branch, `HOMEPAGE_COPY_REVIEW=1` aligns **text nodes alone in the
test baseline browser** with the approved new copy before existing style/geometry
and hover/focus comparisons. This accounts for legitimate text reflow without
turning off the design-preservation checks. The real after page, its attributes,
elements, styles and resources are never changed by that normalization. Separate
static tests require unchanged production structure and assets.

The earlier sitewide test that froze the deferred pressure-test wording is updated
because that discussion has now concluded. Its capability caveat remains guarded.

No merge or deployment is part of this change. Browser artifacts are review
captures, not generated mockups or a complete accessibility certification.
