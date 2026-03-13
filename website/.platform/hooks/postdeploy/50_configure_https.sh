#!/usr/bin/env bash
set -euo pipefail

log() { echo "[https-hook] $*"; }

PRIMARY_DOMAIN="${PRIMARY_DOMAIN:-nektron.ai}"
LETSENCRYPT_EMAIL="${LETSENCRYPT_EMAIL:-info@nektron.ai}"
DOWNLOADS_ORIGIN="${DOWNLOADS_ORIGIN:-https://d2j3ldvioomkd6.cloudfront.net}"
DOMAINS=(
  "nektron.ai"
  "www.nektron.ai"
  "nektron.com"
  "www.nektron.com"
)

install_certbot() {
  if command -v certbot >/dev/null 2>&1; then
    return 0
  fi

  log "Installing certbot..."
  if command -v dnf >/dev/null 2>&1; then
    dnf install -y certbot >/dev/null
  elif command -v yum >/dev/null 2>&1; then
    yum install -y certbot >/dev/null
  else
    log "No supported package manager found for certbot install."
    exit 1
  fi
}

update_certbot_account_email() {
  # If an account already exists, set the contact email deterministically.
  certbot update_account \
    --non-interactive \
    --agree-tos \
    --email "${LETSENCRYPT_EMAIL}" >/dev/null 2>&1 || true
}

configure_renewal_hooks() {
  mkdir -p /etc/letsencrypt/renewal-hooks/pre
  mkdir -p /etc/letsencrypt/renewal-hooks/post

  cat >/etc/letsencrypt/renewal-hooks/pre/00_stop_nginx.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
systemctl stop nginx || true
EOF

  cat >/etc/letsencrypt/renewal-hooks/post/00_start_nginx.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
systemctl start nginx || true
EOF

  chmod +x /etc/letsencrypt/renewal-hooks/pre/00_stop_nginx.sh
  chmod +x /etc/letsencrypt/renewal-hooks/post/00_start_nginx.sh
}

run_certbot_certonly() {
  systemctl stop nginx || true

  if ! certbot certonly "$@" >/dev/null; then
    systemctl start nginx || true
    return 1
  fi

  systemctl start nginx
}

request_or_renew_cert() {
  local domain_args=()
  local d
  local cert_info=""
  local existing_domains=""
  local missing_domains=()
  for d in "${DOMAINS[@]}"; do
    domain_args+=("-d" "$d")
  done

  if cert_info="$(certbot certificates --cert-name "${PRIMARY_DOMAIN}" 2>/dev/null)"; then
    existing_domains="$(printf '%s\n' "${cert_info}" | awk -F': ' '/Domains:/ {print $2; exit}')"

    for d in "${DOMAINS[@]}"; do
      case " ${existing_domains} " in
        *" ${d} "*) ;;
        *) missing_domains+=("${d}") ;;
      esac
    done

    if [[ "${#missing_domains[@]}" -eq 0 ]]; then
      log "Certificate ${PRIMARY_DOMAIN} already covers ${DOMAINS[*]}; skipping issue step."
      return 0
    fi

    log "Expanding certificate ${PRIMARY_DOMAIN}; missing domains: ${missing_domains[*]}"
    run_certbot_certonly \
      --standalone \
      --non-interactive \
      --agree-tos \
      --email "${LETSENCRYPT_EMAIL}" \
      --cert-name "${PRIMARY_DOMAIN}" \
      --keep-until-expiring \
      --expand \
      --preferred-challenges http \
      "${domain_args[@]}"
    return 0
  fi

  log "Requesting initial Let's Encrypt certificate for ${DOMAINS[*]}"
  run_certbot_certonly \
    --standalone \
    --non-interactive \
    --agree-tos \
    --email "${LETSENCRYPT_EMAIL}" \
    --cert-name "${PRIMARY_DOMAIN}" \
    --keep-until-expiring \
    --preferred-challenges http \
    "${domain_args[@]}"
}

write_nginx_tls_config() {
  log "Writing nginx HTTPS config."
  cat >/etc/nginx/conf.d/zz_nektron_https.conf <<'EOF'
server {
    listen 80;
    listen [::]:80;
    server_name nektron.ai www.nektron.ai nektron.com www.nektron.com;

    location /.well-known/acme-challenge/ {
        root /var/www/letsencrypt;
    }

    location / {
        return 301 https://$host$request_uri;
    }
}

server {
    listen 443 ssl;
    listen [::]:443 ssl;
    http2 on;
    server_name nektron.ai www.nektron.ai nektron.com www.nektron.com;

    root /var/app/current;
    index index.html;

    ssl_certificate /etc/letsencrypt/live/nektron.ai/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/nektron.ai/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;

    # Keep the site live, but discourage indexing until public launch.
    add_header X-Robots-Tag "noindex, nofollow, noarchive, nosnippet" always;

    location ^~ /assets/downloads/ {
        return 302 __DOWNLOADS_ORIGIN__$request_uri;
    }

    location = / {
        try_files /index.html =404;
    }

    location / {
        try_files $uri $uri/ =404;
    }
}
EOF

  DOWNLOADS_ORIGIN="${DOWNLOADS_ORIGIN}" python3 - <<'PY'
import os
from pathlib import Path

config_path = Path("/etc/nginx/conf.d/zz_nektron_https.conf")
config_text = config_path.read_text(encoding="utf-8")
config_text = config_text.replace("__DOWNLOADS_ORIGIN__", os.environ["DOWNLOADS_ORIGIN"])
config_path.write_text(config_text, encoding="utf-8")
PY

  mkdir -p /var/www/letsencrypt/.well-known/acme-challenge
}

enable_renewal_timer() {
  if systemctl list-unit-files | grep -q '^certbot-renew.timer'; then
    systemctl enable --now certbot-renew.timer >/dev/null || true
  elif systemctl list-unit-files | grep -q '^certbot.timer'; then
    systemctl enable --now certbot.timer >/dev/null || true
  fi
}

main() {
  install_certbot
  update_certbot_account_email
  configure_renewal_hooks
  request_or_renew_cert
  write_nginx_tls_config
  nginx -t
  systemctl reload nginx
  enable_renewal_timer
  log "HTTPS configuration complete."
}

main "$@"
