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

## AWS Traffic Monitoring
CloudWatch log streaming is enabled for the production Elastic Beanstalk environment with 7-day retention.

- Region: `us-east-2`
- Environment: `nektron-web-si-prod`
- Access log group: `/aws/elasticbeanstalk/nektron-web-si-prod/var/log/nginx/access.log`

### Quick tail
```bash
aws logs tail /aws/elasticbeanstalk/nektron-web-si-prod/var/log/nginx/access.log \
  --region us-east-2 \
  --since 1d
```

### 1. Homepage hits in the last 24 hours
Counts successful homepage requests (`GET /` with `200`).

```bash
aws logs filter-log-events \
  --region us-east-2 \
  --log-group-name /aws/elasticbeanstalk/nektron-web-si-prod/var/log/nginx/access.log \
  --start-time $(( ($(date -u +%s) - 86400) * 1000 )) \
  --query 'events[?contains(message, `"GET / HTTP"`) && contains(message, ` 200 `)] | length(@)'
```

### 2. Top IPs in the last 24 hours
Useful for seeing whether traffic is concentrated in a few bot/scanner sources.

```bash
aws logs filter-log-events \
  --region us-east-2 \
  --log-group-name /aws/elasticbeanstalk/nektron-web-si-prod/var/log/nginx/access.log \
  --start-time $(( ($(date -u +%s) - 86400) * 1000 )) \
  --query 'events[].message' \
  --output text | awk '{print $1}' | sort | uniq -c | sort -rn | head -n 20
```

### 3. Top suspicious probe paths in the last 24 hours
Shows common scanner targets such as `.env`, `wp-*`, `xmlrpc.php`, and `.git/config`.

```bash
aws logs filter-log-events \
  --region us-east-2 \
  --log-group-name /aws/elasticbeanstalk/nektron-web-si-prod/var/log/nginx/access.log \
  --start-time $(( ($(date -u +%s) - 86400) * 1000 )) \
  --query 'events[].message' \
  --output text | awk -F'"' '{split($2,r," "); print r[2]}' | \
  rg '(^/\.env|^/\.git/config|xmlrpc\.php|wp-content|wp-includes|wp-admin|cgi-bin|info\.php|admin\.php|ms-edit\.php)' | \
  sort | uniq -c | sort -rn | head -n 30
```
