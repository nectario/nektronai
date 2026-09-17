#!/usr/bin/env bash
set -euo pipefail
# Runs after the existing HTTPS hook. Adds only the exact setup-page location.
python3 - <<'PY'
from pathlib import Path
path = Path('/etc/nginx/conf.d/zz_nektron_https.conf')
text = path.read_text()
if 'auth_basic ' in text:
    raise SystemExit('Existing private-site authentication needs separate route review')
marker = '# Database Connector setup route'
if marker in text:
    raise SystemExit('Setup route already exists; inspect before modifying it')
anchor = '    root /var/app/current;\n'
if text.count(anchor) != 1:
    raise SystemExit('Expected exactly one existing website root; no change made')
location = '''
    # Database Connector setup route
    location = /database-connector-setup.html {
        # Authorization codes must not appear in routine access logs.
        access_log /var/log/nginx/access.log database_connector_safe;
        add_header Cache-Control "no-store" always;
        add_header Referrer-Policy "no-referrer" always;
        add_header X-Content-Type-Options "nosniff" always;
        add_header X-Frame-Options "DENY" always;
        add_header X-Robots-Tag "noindex, nofollow" always;
        try_files $uri =404;
    }
'''
# Preserve status/latency diagnostics without query strings or referrers.
log_format = "log_format database_connector_safe '$remote_addr [$time_local] ' " \
             "'\"$request_method $uri $server_protocol\" $status $body_bytes_sent $request_time';\n"
path.write_text(log_format + text.replace(anchor, anchor + location))
PY
nginx -t
systemctl reload nginx
