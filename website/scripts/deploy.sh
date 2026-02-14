#!/usr/bin/env bash
set -euo pipefail

BUCKET_REGION="us-east-2"
ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
BUCKET_NAME="nektron-ai-site-${ACCOUNT_ID}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -d "${SCRIPT_DIR}/../site" ]]; then
  SITE_DIR="$(cd "${SCRIPT_DIR}/../site" && pwd)"
else
  SITE_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
fi

echo "== Deploy NektronAI site =="
echo "Bucket: ${BUCKET_NAME}"
echo "Site dir: ${SITE_DIR}"

# Optional: if a brand/logo folder exists next to the site repo, copy assets in.
# This lets you drop new logo files without editing the site code.
BRAND_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../logo" 2>/dev/null && pwd || true)"
if [[ -n "${BRAND_DIR}" && -d "${BRAND_DIR}" ]]; then
  BRAND_OUT_DIR="${SITE_DIR}/assets/brand"
  mkdir -p "${BRAND_OUT_DIR}"

  # Keep deploy deterministic and avoid accidentally publishing docs/PDFs.
  rm -f "${BRAND_OUT_DIR}"/* 2>/dev/null || true

  WORDMARK_SRC="${BRAND_DIR}/JPGs & PNGs/Logo.png"
  ICON_SRC="${BRAND_DIR}/Icon & Social Media/Icon.png"
  FAVICON_SRC="${BRAND_DIR}/Favicon.png"
  SVG_SRC="${BRAND_DIR}/logo.svg"

  if [[ -f "${WORDMARK_SRC}" ]]; then
    cp -f "${WORDMARK_SRC}" "${BRAND_OUT_DIR}/wordmark.png"
  fi
  if [[ -f "${ICON_SRC}" ]]; then
    cp -f "${ICON_SRC}" "${BRAND_OUT_DIR}/icon.png"
  fi
  if [[ -f "${FAVICON_SRC}" ]]; then
    cp -f "${FAVICON_SRC}" "${SITE_DIR}/assets/favicon.png"
  fi
  if [[ -f "${SVG_SRC}" ]]; then
    cp -f "${SVG_SRC}" "${BRAND_OUT_DIR}/logo.svg"
  fi

fi

aws s3 sync "${SITE_DIR}/" "s3://${BUCKET_NAME}/" --delete --region "${BUCKET_REGION}" \
  --exclude ".git/*" \
  --exclude "node_modules/*" \
  --exclude "scripts/*" \
  --exclude "archive/*" \
  --exclude "dist/*" \
  --exclude ".gitignore" \
  --exclude "README.md" \
  --exclude "package.json" \
  --exclude "package-lock.json" \
  --exclude "*.zip"
echo "S3 sync complete."

# Find CloudFront distribution by alias
DIST_ID="$(aws cloudfront list-distributions --query "DistributionList.Items[?Aliases.Items && contains(Aliases.Items, 'nektron.ai')].Id | [0]" --output text)"

if [[ -z "${DIST_ID}" || "${DIST_ID}" == "None" ]]; then
  echo "WARN: Could not find CloudFront distribution by alias. Skipping invalidation."
  exit 0
fi

aws cloudfront create-invalidation --distribution-id "${DIST_ID}" --paths "/*" >/dev/null
echo "CloudFront invalidation submitted: ${DIST_ID}"
