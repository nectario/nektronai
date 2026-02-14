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

## Deploy
Upload the folder contents to your static host (S3/Cloudflare Pages/GitHub Pages/etc.).

## Quick customization
- Replace logo assets in `assets/brand/` and `assets/favicon.png` once your logo is finalized.
- Update product descriptions in `index.html` if you want different positioning.
- Update the GrowNet page copy as research milestones become public.
