#!/usr/bin/env bash
set -euo pipefail

secret_arn="$(/opt/elasticbeanstalk/bin/get-config environment -k NEKTRON_ACCOUNT_SECRET_ARN 2>/dev/null || true)"
if [[ -z "$secret_arn" ]]; then
  echo "[accounts] No account secret configured; backend is not enabled."
  exit 0
fi
if [[ "$secret_arn" != arn:aws:secretsmanager:* ]]; then
  echo "[accounts] Invalid secret ARN."
  exit 1
fi

dnf install -y python3.12 python3.12-pip >/dev/null
id nektronaccounts >/dev/null 2>&1 || useradd --system --no-create-home --shell /sbin/nologin nektronaccounts
mkdir -p /opt/nektron-accounts
python3.12 -m venv /opt/nektron-accounts/venv
/opt/nektron-accounts/venv/bin/pip install --disable-pip-version-check -r /var/app/current/server/accounts/requirements.txt >/dev/null
printf 'NEKTRON_ACCOUNT_SECRET_ARN=%s\nAWS_REGION=us-east-2\n' "$secret_arn" > /etc/nektron-accounts.env
chmod 600 /etc/nektron-accounts.env

cat > /etc/systemd/system/nektron-accounts.service <<'UNIT'
[Unit]
Description=Nektron website accounts
After=network-online.target
Wants=network-online.target
[Service]
User=nektronaccounts
Group=nektronaccounts
WorkingDirectory=/var/app/current/server/accounts
EnvironmentFile=/etc/nektron-accounts.env
Environment=PYTHONDONTWRITEBYTECODE=1
ExecStart=/opt/nektron-accounts/venv/bin/gunicorn --bind 127.0.0.1:8768 --workers 2 --threads 2 --timeout 30 --log-level warning wsgi:application
Restart=on-failure
RestartSec=3
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable nektron-accounts >/dev/null
systemctl restart nektron-accounts
for attempt in {1..15}; do
  if curl --fail --silent http://127.0.0.1:8768/api/account/health >/dev/null; then break; fi
  sleep 1
done
curl --fail --silent http://127.0.0.1:8768/api/account/health >/dev/null

python3 - <<'PY'
from pathlib import Path
path = Path("/etc/nginx/conf.d/zz_nektron_https.conf")
text = path.read_text()
anchor = "    root /var/app/current;\n"
if text.count(anchor) != 1:
    raise SystemExit("Expected one site root")
location = """
    location ^~ /api/account/ {
        access_log /var/log/nginx/access.log nektron_accounts_safe;
        proxy_pass http://127.0.0.1:8768;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_hide_header X-Powered-By;
        client_max_body_size 4k;
        proxy_read_timeout 30s;
    }
"""
# OAuth codes and session tokens never enter routine request logs.
log_format = "log_format nektron_accounts_safe '$remote_addr [$time_local] " \
             "\"$request_method $uri $server_protocol\" $status $request_time';\n"
path.write_text(log_format + text.replace(anchor, anchor + location))
PY
nginx -t
systemctl reload nginx
echo "[accounts] Backend ready."
