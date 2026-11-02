# Nektron Mail product screenshots

These images are rendered from the actual Nektron Mail **0.1.125** WPF application controls, using a separate in-memory demo and an isolated synthetic profile. They are not generated UI mockups and contain no private mail, passwords, account tokens, or real customer addresses. Names, messages, counts, mailboxes and AI availability are illustrative sample data. The `.example` addresses are deliberately fictional.

The screenshots show the current Windows preview. Features that remain limited or unavailable are not hidden: search states it searched local records; the composer is shown in Email mode; the reader retains its current attachment-export notice; rule assistance shows an eligible demo account rather than implying universal/free availability.

| Asset | Dimensions | Caption |
| --- | --- | --- |
| `overview-light.webp` | 1440 × 1000 | Multiple mailboxes, local message list and reading pane in Light theme. |
| `overview-dark.webp` | 1440 × 1000 | The same native mailbox workspace in Dark theme. |
| `compose.webp` | 1180 × 820 | A separate composition window with recipients, a labeled subject and a standard attachment; Email output is selected. |
| `search.webp` | 1180 × 760 | Local mail search with visible From/Subject filters and a selected result. |
| `rules.webp` | 1180 × 1060 | A client rule draft and the paid AI rule-authoring prompt, shown with eligible sample access. No live AI request was made. |
| `downloads.webp` | 1180 × 1000 | Background Get Mail progress, per-folder workers and local download coverage. Counts are illustrative, not a performance claim. |

PNG captures are retained beside lossless WebP exports. Exporting does not resize or change screenshot content; decoded pixels are checked against the PNG source. No desktop input, live provider connection or user profile was used.

`icon-64.png` and `icon-128.png` are copied unchanged from the app's native `Assets/Brand/Application` icon ladder. The tile background is the approved **#9EC9E6**. Display at an appropriate authored size rather than stretching a smaller raster.

Local capture helper: `C:/Development/Projects/Nektron Mail/private/mail-site-shots/` (ignored diagnostic project, referencing the current app). It invokes the production controls with synthetic services and captures them through WPF `RenderTargetBitmap`; no Mail product source was modified.

Suggested page disclosure: **Screenshots show the Windows preview with sample data. Feature availability depends on the supported mailbox and account access.**
