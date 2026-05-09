#!/usr/bin/env bash
set -euo pipefail

log() { echo "[$(date +'%H:%M:%S')] $*"; }

require_cmd() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "ERROR: Required command '$cmd' is not installed."
    exit 1
  fi
}

require_cmd aws
require_cmd rsync
require_cmd zip

AWS_REGION="${AWS_REGION:-us-east-2}"
EB_APP_NAME="${EB_APP_NAME:-NektronWeb}"
EB_ENV_NAME="${EB_ENV_NAME:-nektron-web-si-prod}"
THEME_DIR="${THEME_DIR:-}"
SITE_RESEARCH_PUBLIC_ENABLED="${SITE_RESEARCH_PUBLIC_ENABLED:-false}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SITE_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

if [[ -n "${THEME_DIR}" && ! -d "${SITE_DIR}/${THEME_DIR}" ]]; then
  echo "ERROR: Theme directory not found: ${SITE_DIR}/${THEME_DIR}"
  exit 1
fi

TS="$(date -u +%Y%m%dT%H%M%SZ)"
VERSION_LABEL="nektron-web-${TS}"
BUNDLE_DIR="/tmp/nektron-eb-bundle-${TS}"
BUNDLE_ZIP="/tmp/nektron-eb-${TS}.zip"
ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
EB_BUCKET="elasticbeanstalk-${AWS_REGION}-${ACCOUNT_ID}"
S3_KEY="nektron/${VERSION_LABEL}.zip"

log "Preparing bundle: ${VERSION_LABEL}"
log "Region=${AWS_REGION} App=${EB_APP_NAME} Env=${EB_ENV_NAME}"
if [[ -n "${THEME_DIR}" ]]; then
  log "Theme override: ${THEME_DIR}"
else
  log "Theme override: <none> (main root files)"
fi
log "Research public: ${SITE_RESEARCH_PUBLIC_ENABLED}"

version_bundle_assets() {
  log "Stamping static asset URLs with deployment version."
  BUNDLE_DIR="${BUNDLE_DIR}" VERSION_LABEL="${VERSION_LABEL}" python3 - <<'PY'
import os
import re
from pathlib import Path

bundle_dir = Path(os.environ["BUNDLE_DIR"])
version = os.environ["VERSION_LABEL"]

html_patterns = [
    "assets/styles.css",
    "/assets/styles.css",
    "assets/site.js",
    "/assets/site.js",
    "assets/favicon.svg",
    "/assets/favicon.svg",
    "assets/favicon.png",
    "/assets/favicon.png",
    "assets/coming-soon.svg",
    "/assets/coming-soon.svg",
    "assets/background_dark.jpg",
    "/assets/background_dark.jpg",
    "assets/brand/icon.png",
    "/assets/brand/icon.png",
    "assets/brand/wordmark-dark-320.png",
    "/assets/brand/wordmark-dark-320.png",
    "assets/brand/wordmark-light-320.png",
    "/assets/brand/wordmark-light-320.png",
    "assets/brand/wordmark-dark-280.png",
    "/assets/brand/wordmark-dark-280.png",
    "assets/brand/wordmark-light-280.png",
    "/assets/brand/wordmark-light-280.png",
    "https://nektron.ai/assets/og.png",
]

css_patterns = [
    "background_dark.jpg",
    "background_light.jpg",
]

def stamp(text: str, asset_path: str) -> str:
    pattern = re.escape(asset_path) + r"(?:\?v=[^\"')\\s]+)?"
    return re.sub(pattern, f"{asset_path}?v={version}", text)

for html_path in bundle_dir.rglob("*.html"):
    text = html_path.read_text(encoding="utf-8")
    updated = text
    for asset in html_patterns:
        updated = stamp(updated, asset)
    if updated != text:
        html_path.write_text(updated, encoding="utf-8")

styles_path = bundle_dir / "assets" / "styles.css"
if styles_path.exists():
    text = styles_path.read_text(encoding="utf-8")
    updated = text
    for asset in css_patterns:
        updated = stamp(updated, asset)
    if updated != text:
        styles_path.write_text(updated, encoding="utf-8")
PY
}

apply_public_safe_overlay() {
  if [[ "${SITE_RESEARCH_PUBLIC_ENABLED}" == "true" ]]; then
    return 0
  fi

  log "Applying public-safe research overlay."

  if [[ ! -d "${SITE_DIR}/public-safe" ]]; then
    echo "ERROR: public-safe overlay directory missing."
    exit 1
  fi

  cp -f "${SITE_DIR}/public-safe/index.html" "${BUNDLE_DIR}/index.html"
  cp -f "${SITE_DIR}/public-safe/about.html" "${BUNDLE_DIR}/about.html"
  cp -f "${SITE_DIR}/public-safe/sitemap.xml" "${BUNDLE_DIR}/sitemap.xml"

  for target in grownet.html grownet-formal-spec.html docs.html downloads.html changelog.html; do
    cp -f "${SITE_DIR}/public-safe/research-private.html" "${BUNDLE_DIR}/${target}"
  done

  BUNDLE_DIR="${BUNDLE_DIR}" python3 - <<'PY'
import re
from pathlib import Path

bundle_dir = Path(__import__("os").environ["BUNDLE_DIR"])
safe_nav = """<nav id="primary-nav" aria-label="Primary navigation">
      <a href="index.html#research">Research</a>
      <a href="index.html#products">Products</a>
      <a href="about.html">About</a>
      <a href="index.html#contact">Contact</a>
    </nav>"""
safe_footer = """<small>NektronAI is a research-first AI company building practical products and long-horizon AI foundations.</small>"""
safe_links = """<div class="footer-links">
        <a href="about.html">About</a>
        <a href="index.html#research">Research</a>
        <a href="index.html#products">Products</a>
        <a href="index.html#contact">Contact</a>
      </div>"""

for name in ("privacy.html", "support.html", "terms.html"):
    path = bundle_dir / name
    if not path.exists():
        continue
    text = path.read_text(encoding="utf-8")
    text = re.sub(r'<nav id="primary-nav" aria-label="Primary navigation">.*?</nav>', safe_nav, text, flags=re.S)
    text = re.sub(r'<small>NektronAI is a research-first AI company building .*?</small>', safe_footer, text, flags=re.S)
    text = re.sub(r'<div class="footer-links">\s*<a href="about\.html">About</a>.*?<a href="index\.html#contact">Contact</a>\s*</div>', safe_links, text, flags=re.S)
    path.write_text(text, encoding="utf-8")
PY

  rm -rf \
    "${BUNDLE_DIR}/ai_lab_sophisticated" \
    "${BUNDLE_DIR}/mysterious_sophisticated" \
    "${BUNDLE_DIR}/precision_sophisticated" \
    "${BUNDLE_DIR}/variants" \
    "${BUNDLE_DIR}/public-safe" \
    "${BUNDLE_DIR}/assets/docs" \
    "${BUNDLE_DIR}/assets/downloads"

  rm -f \
    "${BUNDLE_DIR}/README.md" \
    "${BUNDLE_DIR}/package.json" \
    "${BUNDLE_DIR}/package-lock.json" \
    "${BUNDLE_DIR}/assets/grownet.css" \
    "${BUNDLE_DIR}/assets/brand/grownet-logo.svg" \
    "${BUNDLE_DIR}/assets/brand/grownet-logo-preview.png" \
    "${BUNDLE_DIR}/assets/brand/grownet-mark.svg" \
    "${BUNDLE_DIR}/assets/brand/grownet-mark-preview.png"

  if grep -RIlE 'GrowNet|grownet|GROWNET' "${BUNDLE_DIR}" >/tmp/nektron-grownet-public-matches 2>/dev/null; then
    echo "ERROR: public-safe bundle still contains GrowNet references:"
    sed -n '1,80p' /tmp/nektron-grownet-public-matches
    exit 1
  fi
}

mkdir -p "${BUNDLE_DIR}"
rsync -a --delete \
  --exclude ".git/" \
  --exclude "node_modules/" \
  --exclude "dist/" \
  --exclude "scripts/" \
  --exclude "ops/" \
  --exclude "archive/" \
  --exclude "NektronAI.zip" \
  --exclude "NektronAI_production_ready.zip" \
  --exclude "nektronai_site_pr.zip" \
  --exclude ".idea/" \
  --exclude "codex.txt" \
  "${SITE_DIR}/" "${BUNDLE_DIR}/"

# Optional theme overlay: copy that theme's HTML pages to the deployment root.
if [[ -n "${THEME_DIR}" ]]; then
  cp -f "${SITE_DIR}/${THEME_DIR}/"*.html "${BUNDLE_DIR}/"
fi

apply_public_safe_overlay
version_bundle_assets

( cd "${BUNDLE_DIR}" && zip -rq "${BUNDLE_ZIP}" . )

log "Uploading application bundle to s3://${EB_BUCKET}/${S3_KEY}"
aws s3 cp "${BUNDLE_ZIP}" "s3://${EB_BUCKET}/${S3_KEY}" --region "${AWS_REGION}" >/dev/null

log "Creating application version ${VERSION_LABEL}"
aws elasticbeanstalk create-application-version \
  --region "${AWS_REGION}" \
  --application-name "${EB_APP_NAME}" \
  --version-label "${VERSION_LABEL}" \
  --source-bundle S3Bucket="${EB_BUCKET}",S3Key="${S3_KEY}" >/dev/null

log "Updating environment ${EB_ENV_NAME}"
aws elasticbeanstalk update-environment \
  --region "${AWS_REGION}" \
  --environment-name "${EB_ENV_NAME}" \
  --version-label "${VERSION_LABEL}" >/dev/null

log "Deployment started."
log "Version: ${VERSION_LABEL}"
