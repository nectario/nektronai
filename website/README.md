# NektronAI website refresh (static)

This is a lightweight, no-build-step site refresh intended to feel:
- Minimal and sophisticated
- Technical / scientist-friendly
- Fast (pure HTML/CSS + a tiny JS file)

## Files
- `index.html` – landing page
- `grownet.html` – dedicated GrowNet research page (includes explicit "in development" note)
- `privacy.html`, `terms.html`, `support.html` – styled legal/support pages
- `assets/styles.css` – theme + layout
- `assets/site.js` – theme toggle + mobile nav
- `assets/favicon.png` – simple favicon
- `ai_lab_sophisticated/` – full site variant in its own subfolder
- `mysterious_sophisticated/` – full site variant in its own subfolder
- `precision_sophisticated/` – full site variant in its own subfolder
- `assets/variants/*.css` – variant-specific style overrides
- `variants/index.html` – variant landing page with links

## Local preview
1. Install dependencies:
   ```bash
   npm install
   ```
2. Start the dev server:
   ```bash
   npm run dev
   ```
3. Open the local URL shown in the terminal (typically `http://localhost:5173`).

### Variant URLs (local)
- `http://localhost:5173/` (main site)
- `http://localhost:5173/variants/` (variant index)
- `http://localhost:5173/ai_lab_sophisticated/`
- `http://localhost:5173/mysterious_sophisticated/`
- `http://localhost:5173/precision_sophisticated/`

## Deploy
Upload the folder contents to your static host (S3/Cloudflare Pages/GitHub Pages/etc.).

## Quick customization
- Replace logo assets in `assets/brand/` and `assets/favicon.png` once your logo is finalized.
- Update product descriptions in `index.html` if you want different positioning.
- Update the GrowNet page copy as research milestones become public.

## Social previews
- `assets/og.png` – Open Graph / Twitter preview image (1200×630)
