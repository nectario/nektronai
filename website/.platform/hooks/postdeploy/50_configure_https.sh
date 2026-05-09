#!/usr/bin/env bash
set -euo pipefail

log() { echo "[https-hook] $*"; }

PRIMARY_DOMAIN="${PRIMARY_DOMAIN:-nektron.ai}"
LETSENCRYPT_EMAIL="${LETSENCRYPT_EMAIL:-info@nektron.ai}"
DOWNLOADS_ORIGIN="${DOWNLOADS_ORIGIN:-https://d2j3ldvioomkd6.cloudfront.net}"
SITE_COMING_SOON_ENABLED="${SITE_COMING_SOON_ENABLED:-false}"
SITE_BASIC_AUTH_ENABLED="${SITE_BASIC_AUTH_ENABLED:-false}"
SITE_BASIC_AUTH_USER="${SITE_BASIC_AUTH_USER:-nektron}"
SITE_BASIC_AUTH_PASSWORD="${SITE_BASIC_AUTH_PASSWORD:-}"
SITE_BASIC_AUTH_REALM="${SITE_BASIC_AUTH_REALM:-NektronAI private preview}"
SITE_RESEARCH_PUBLIC_ENABLED="${SITE_RESEARCH_PUBLIC_ENABLED:-false}"
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

configure_basic_auth_file() {
  if [[ "${SITE_BASIC_AUTH_ENABLED}" != "true" ]]; then
    rm -f /etc/nginx/.nektron_htpasswd
    return 0
  fi

  if [[ -z "${SITE_BASIC_AUTH_PASSWORD}" ]]; then
    log "SITE_BASIC_AUTH_ENABLED=true but SITE_BASIC_AUTH_PASSWORD is empty."
    exit 1
  fi

  if ! command -v openssl >/dev/null 2>&1; then
    log "openssl is required to generate the Basic Auth password file."
    exit 1
  fi

  local password_hash
  password_hash="$(openssl passwd -apr1 "${SITE_BASIC_AUTH_PASSWORD}")"
  printf '%s:%s\n' "${SITE_BASIC_AUTH_USER}" "${password_hash}" >/etc/nginx/.nektron_htpasswd
  chmod 644 /etc/nginx/.nektron_htpasswd
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
    etag on;

    # Keep the site live, but discourage indexing until public launch.
    add_header X-Robots-Tag "noindex, nofollow, noarchive, nosnippet" always;

    location = /coming-soon.html {
        add_header X-Robots-Tag "noindex, nofollow, noarchive, nosnippet" always;
        add_header Cache-Control "no-cache, no-store, must-revalidate" always;
        expires -1;
        try_files /coming-soon.html =404;
    }

    location = /assets/coming-soon.svg {
        try_files /assets/coming-soon.svg =404;
    }

    location = /assets/background_dark.jpg {
        try_files /assets/background_dark.jpg =404;
    }

    location = /assets/favicon.svg {
        try_files /assets/favicon.svg =404;
    }

    location = /assets/favicon.png {
        try_files /assets/favicon.png =404;
    }

    location ^~ /assets/downloads/ {
        __PRIVATE_AUTH__
        __DOWNLOADS_ACTION__
    }

    __ROOT_LOCATION__

    location ^~ /assets/ {
        __PRIVATE_AUTH__
        try_files $uri $uri/ =404;
    }

    location ~* \.html$ {
        __PRIVATE_AUTH__
        add_header X-Robots-Tag "noindex, nofollow, noarchive, nosnippet" always;
        add_header Cache-Control "no-cache, no-store, must-revalidate" always;
        expires -1;
        try_files $uri =404;
    }

    location / {
        __PRIVATE_AUTH__
        try_files $uri $uri/ =404;
    }
}
EOF

  DOWNLOADS_ORIGIN="${DOWNLOADS_ORIGIN}" \
  SITE_COMING_SOON_ENABLED="${SITE_COMING_SOON_ENABLED}" \
  SITE_BASIC_AUTH_ENABLED="${SITE_BASIC_AUTH_ENABLED}" \
  SITE_BASIC_AUTH_REALM="${SITE_BASIC_AUTH_REALM}" \
  SITE_RESEARCH_PUBLIC_ENABLED="${SITE_RESEARCH_PUBLIC_ENABLED}" \
  python3 - <<'PY'
import os
from pathlib import Path

config_path = Path("/etc/nginx/conf.d/zz_nektron_https.conf")
config_text = config_path.read_text(encoding="utf-8")
config_text = config_text.replace("__DOWNLOADS_ORIGIN__", os.environ["DOWNLOADS_ORIGIN"])
auth_enabled = os.environ["SITE_BASIC_AUTH_ENABLED"] == "true"
coming_soon_enabled = os.environ["SITE_COMING_SOON_ENABLED"] == "true"
research_public_enabled = os.environ["SITE_RESEARCH_PUBLIC_ENABLED"] == "true"

if auth_enabled:
    realm = os.environ["SITE_BASIC_AUTH_REALM"].replace('"', '\\"')
    private_auth = (
        f'auth_basic "{realm}";\n'
        "        auth_basic_user_file /etc/nginx/.nektron_htpasswd;"
    )
else:
    private_auth = ""

if coming_soon_enabled:
    root_location = """location = / {
        add_header X-Robots-Tag "noindex, nofollow, noarchive, nosnippet" always;
        add_header Cache-Control "no-cache, no-store, must-revalidate" always;
        expires -1;
        try_files /coming-soon.html =404;
    }"""
else:
    root_auth = f"{private_auth}\n        " if private_auth else ""
    root_location = f"""location = / {{
        {root_auth}add_header X-Robots-Tag "noindex, nofollow, noarchive, nosnippet" always;
        add_header Cache-Control "no-cache, no-store, must-revalidate" always;
        expires -1;
        try_files /index.html =404;
    }}"""

config_text = config_text.replace("__PRIVATE_AUTH__", private_auth)
config_text = config_text.replace("__ROOT_LOCATION__", root_location)
downloads_origin = os.environ["DOWNLOADS_ORIGIN"]
downloads_action = f"return 302 {downloads_origin}$request_uri;" if research_public_enabled else "return 404;"
config_text = config_text.replace("__DOWNLOADS_ACTION__", downloads_action)
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
  configure_basic_auth_file
  write_nginx_tls_config
  nginx -t
  systemctl reload nginx
  enable_renewal_timer
  log "HTTPS configuration complete."
}

main "$@"
