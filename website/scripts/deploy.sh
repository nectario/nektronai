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

pick_first_existing() {
  local candidate
  for candidate in "$@"; do
    if [[ -f "${candidate}" ]]; then
      printf "%s" "${candidate}"
      return 0
    fi
  done
  return 1
}

# OneDrive is the canonical logo source. Override this only when intentionally
# deploying from another synchronized copy.
BRAND_DIR="${NEKTRON_LOGO_DIR:-/c/Users/nektarios/OneDrive/Documents/Nektron/logo}"
if [[ ! -d "${BRAND_DIR}" ]]; then
  echo "ERROR: Canonical brand directory not found: ${BRAND_DIR}"
  echo "Set NEKTRON_LOGO_DIR to an alternate logo directory if needed."
  exit 1
fi

BRAND_DIR="$(cd "${BRAND_DIR}" && pwd)"
BRAND_OUT_DIR="${SITE_DIR}/assets/brand"
mkdir -p "${BRAND_OUT_DIR}"
echo "Brand source: ${BRAND_DIR}"

  # Use only finalized assets so a deploy cannot silently fall back to an
  # archived or working logo.
  WORDMARK_DARK_320_SRC="$(
    pick_first_existing \
      "${BRAND_DIR}/final/320w/NektronAI_Dark_320.png" \
      || true
  )"
  WORDMARK_LIGHT_320_SRC="$(
    pick_first_existing \
      "${BRAND_DIR}/final/320w/NektronAI_Light_320.png" \
      || true
  )"
  WORDMARK_DARK_280_SRC="$(
    pick_first_existing \
      "${BRAND_DIR}/final/280w/NektronAI_Dark_280.png" \
      || true
  )"
  WORDMARK_LIGHT_280_SRC="$(
    pick_first_existing \
      "${BRAND_DIR}/final/280w/NektronAI_Light_280.png" \
      || true
  )"
  ICON_SRC="$(
    pick_first_existing \
      "${BRAND_DIR}/final/icon.png" \
      "${BRAND_DIR}/final/Icon.png" \
      "${BRAND_DIR}/final/icons/1x/icon_NektronAI_Dark.png" \
      "${BRAND_DIR}/final/icons/1x/icon_NektronAI_Light.png" \
      || true
  )"
  FAVICON_SRC="$(
    pick_first_existing \
      "${BRAND_DIR}/final/favicon.png" \
      "${BRAND_DIR}/final/Favicon.png" \
      "${BRAND_DIR}/final/icons/0.1x/icon_NektronAI_Dark@0.1x.png" \
      "${BRAND_DIR}/final/icons/0.1x/icon_NektronAI_Light@0.1x.png" \
      || true
  )"
  FAVICON_SVG_SRC="$(
    pick_first_existing \
      "${BRAND_DIR}/final/favicon.svg" \
      "${BRAND_DIR}/final/Favicon.svg" \
      "${BRAND_DIR}/final/icons/SVG/icon_NektronAI_Dark.svg" \
      "${BRAND_DIR}/final/icons/SVG/icon_NektronAI_Light.svg" \
      || true
  )"
  SVG_SRC="$(
    pick_first_existing \
      "${BRAND_DIR}/final/SVG/NektronAI_Dark.svg" \
      "${BRAND_DIR}/final/SVG/NektronAI_Light.svg" \
      || true
  )"

  MISSING_BRAND_ASSETS=()
  [[ -n "${WORDMARK_DARK_320_SRC}" ]] || MISSING_BRAND_ASSETS+=("final dark 320px wordmark")
  [[ -n "${WORDMARK_LIGHT_320_SRC}" ]] || MISSING_BRAND_ASSETS+=("final light 320px wordmark")
  [[ -n "${WORDMARK_DARK_280_SRC}" ]] || MISSING_BRAND_ASSETS+=("final dark 280px wordmark")
  [[ -n "${WORDMARK_LIGHT_280_SRC}" ]] || MISSING_BRAND_ASSETS+=("final light 280px wordmark")
  [[ -n "${ICON_SRC}" ]] || MISSING_BRAND_ASSETS+=("final PNG icon")
  [[ -n "${FAVICON_SRC}" ]] || MISSING_BRAND_ASSETS+=("final PNG favicon")
  [[ -n "${FAVICON_SVG_SRC}" ]] || MISSING_BRAND_ASSETS+=("final SVG favicon")
  [[ -n "${SVG_SRC}" ]] || MISSING_BRAND_ASSETS+=("final SVG wordmark")

  if (( ${#MISSING_BRAND_ASSETS[@]} > 0 )); then
    echo "ERROR: Canonical logo source is incomplete:"
    printf '  - %s\n' "${MISSING_BRAND_ASSETS[@]}"
    exit 1
  fi

  if [[ -n "${WORDMARK_DARK_320_SRC}" ]]; then
    cp -f "${WORDMARK_DARK_320_SRC}" "${BRAND_OUT_DIR}/wordmark-dark-320.png"
    cp -f "${WORDMARK_DARK_320_SRC}" "${BRAND_OUT_DIR}/wordmark-dark.png"
  fi
  if [[ -n "${WORDMARK_LIGHT_320_SRC}" ]]; then
    cp -f "${WORDMARK_LIGHT_320_SRC}" "${BRAND_OUT_DIR}/wordmark-light-320.png"
    cp -f "${WORDMARK_LIGHT_320_SRC}" "${BRAND_OUT_DIR}/wordmark-light.png"
    # Backward-compatible fallback path used by older templates.
    cp -f "${WORDMARK_LIGHT_320_SRC}" "${BRAND_OUT_DIR}/wordmark.png"
  elif [[ -n "${WORDMARK_DARK_320_SRC}" ]]; then
    cp -f "${WORDMARK_DARK_320_SRC}" "${BRAND_OUT_DIR}/wordmark.png"
  fi
  if [[ -n "${WORDMARK_DARK_280_SRC}" ]]; then
    cp -f "${WORDMARK_DARK_280_SRC}" "${BRAND_OUT_DIR}/wordmark-dark-280.png"
  fi
  if [[ -n "${WORDMARK_LIGHT_280_SRC}" ]]; then
    cp -f "${WORDMARK_LIGHT_280_SRC}" "${BRAND_OUT_DIR}/wordmark-light-280.png"
  fi
  if [[ -n "${ICON_SRC}" ]]; then
    cp -f "${ICON_SRC}" "${BRAND_OUT_DIR}/icon.png"
  fi
  if [[ -n "${FAVICON_SRC}" ]]; then
    cp -f "${FAVICON_SRC}" "${SITE_DIR}/assets/favicon.png"
  fi
  if [[ -n "${FAVICON_SVG_SRC}" ]]; then
    cp -f "${FAVICON_SVG_SRC}" "${SITE_DIR}/assets/favicon.svg"
  fi
  if [[ -n "${SVG_SRC}" ]]; then
    cp -f "${SVG_SRC}" "${BRAND_OUT_DIR}/logo.svg"
  fi

aws s3 sync "${SITE_DIR}/" "s3://${BUCKET_NAME}/" --delete --region "${BUCKET_REGION}" \
  --exclude ".git/*" \
  --exclude ".ebextensions/*" \
  --exclude ".idea/*" \
  --exclude ".platform/*" \
  --exclude "node_modules/*" \
  --exclude "ops/*" \
  --exclude "scripts/*" \
  --exclude "archive/*" \
  --exclude "dist/*" \
  --exclude "assets/downloads/*.msi" \
  --exclude "assets/downloads/*.exe" \
  --exclude "assets/downloads/*.zip" \
  --exclude ".gitignore" \
  --exclude "README.md" \
  --exclude "package.json" \
  --exclude "package-lock.json" \
  --exclude "codex.txt" \
  --exclude "NektronAI.zip" \
  --exclude "NektronAI_production_ready.zip" \
  --exclude "nektronai_site_pr.zip"
echo "S3 sync complete."

PRIVATE_PATHS=(
  ".git/"
  ".ebextensions/"
  ".idea/"
  ".platform/"
  "node_modules/"
  "ops/"
  "scripts/"
  "dist/"
  "archive/"
  ".gitignore"
  "README.md"
  "package.json"
  "package-lock.json"
  "codex.txt"
  "NektronAI.zip"
  "NektronAI_production_ready.zip"
  "nektronai_site_pr.zip"
)

for target in "${PRIVATE_PATHS[@]}"; do
  if [[ "${target}" == */ ]]; then
    aws s3 rm "s3://${BUCKET_NAME}/${target}" --recursive --region "${BUCKET_REGION}" >/dev/null 2>&1 || true
  else
    aws s3 rm "s3://${BUCKET_NAME}/${target}" --region "${BUCKET_REGION}" >/dev/null 2>&1 || true
  fi
done
echo "Private path cleanup complete."

# Find CloudFront distribution by alias
DIST_ID="$(aws cloudfront list-distributions --query "DistributionList.Items[?Aliases.Items && contains(Aliases.Items, 'nektron.ai')].Id | [0]" --output text)"

if [[ -z "${DIST_ID}" || "${DIST_ID}" == "None" ]]; then
  echo "WARN: Could not find CloudFront distribution by alias. Skipping invalidation."
  exit 0
fi

aws cloudfront create-invalidation --distribution-id "${DIST_ID}" --paths "/*" >/dev/null
echo "CloudFront invalidation submitted: ${DIST_ID}"
