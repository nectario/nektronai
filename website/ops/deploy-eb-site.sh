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
