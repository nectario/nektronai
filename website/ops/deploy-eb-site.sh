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
