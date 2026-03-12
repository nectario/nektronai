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

# Optional: if a brand/logo folder exists next to the site repo, copy assets in.
# This lets you drop new logo files without editing the site code.
BRAND_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../logo" 2>/dev/null && pwd || true)"
if [[ -n "${BRAND_DIR}" && -d "${BRAND_DIR}" ]]; then
  BRAND_OUT_DIR="${SITE_DIR}/assets/brand"
  mkdir -p "${BRAND_OUT_DIR}"

  # Support both old and new logo folder layouts.
  WORDMARK_DARK_320_SRC="$(
    pick_first_existing \
      "${BRAND_DIR}/final/320w/NektronAI_Dark_320.png" \
      "${BRAND_DIR}/Original Logo/Artwork/1x/NektronAI_Dark.png" \
      "${BRAND_DIR}/NektronAI_Logo_PNG_Package/NektronAI_logo_512w_dark.png" \
      "${BRAND_DIR}/NektronAI_Logo_PNG_Package/NektronAI_logo_1024w_dark.png" \
      "${BRAND_DIR}/NektronAI_Logo_PNG_Package/NektronAI_logo_2048w_dark.png" \
      "${BRAND_DIR}/Original Logo/Icon & Social Media/Black.png" \
      "${BRAND_DIR}/Original Logo/JPGs & PNGs/Black.png" \
      "${BRAND_DIR}/Original Logo/JPGs & PNGs/Logo.png" \
      || true
  )"
  WORDMARK_LIGHT_320_SRC="$(
    pick_first_existing \
      "${BRAND_DIR}/final/320w/NektronAI_Light_320.png" \
      "${BRAND_DIR}/Original Logo/Artwork/1x/NektronAI_Light.png" \
      "${BRAND_DIR}/NektronAI_Logo_PNG_Package/NektronAI_logo_512w_light.png" \
      "${BRAND_DIR}/NektronAI_Logo_PNG_Package/NektronAI_logo_1024w_light.png" \
      "${BRAND_DIR}/NektronAI_Logo_PNG_Package/NektronAI_logo_2048w_light.png" \
      "${BRAND_DIR}/Original Logo/Icon & Social Media/White.png" \
      "${BRAND_DIR}/Original Logo/JPGs & PNGs/White.png" \
      "${BRAND_DIR}/Original Logo/Artwork Files/1x/Artboard 1.png" \
      "${BRAND_DIR}/Original Logo/JPGs & PNGs/Logo.png" \
      || true
  )"
  WORDMARK_DARK_280_SRC="$(
    pick_first_existing \
      "${BRAND_DIR}/final/280w/NektronAI_Dark_280.png" \
      "${BRAND_DIR}/final/320w/NektronAI_Dark_320.png" \
      "${BRAND_DIR}/Original Logo/Artwork/1x/NektronAI_Dark.png" \
      "${BRAND_DIR}/NektronAI_Logo_PNG_Package/NektronAI_logo_512w_dark.png" \
      "${BRAND_DIR}/NektronAI_Logo_PNG_Package/NektronAI_logo_1024w_dark.png" \
      "${BRAND_DIR}/NektronAI_Logo_PNG_Package/NektronAI_logo_2048w_dark.png" \
      "${BRAND_DIR}/Original Logo/Icon & Social Media/Black.png" \
      "${BRAND_DIR}/Original Logo/JPGs & PNGs/Black.png" \
      "${BRAND_DIR}/Original Logo/JPGs & PNGs/Logo.png" \
      || true
  )"
  WORDMARK_LIGHT_280_SRC="$(
    pick_first_existing \
      "${BRAND_DIR}/final/280w/NektronAI_Light_280.png" \
      "${BRAND_DIR}/final/320w/NektronAI_Light_320.png" \
      "${BRAND_DIR}/Original Logo/Artwork/1x/NektronAI_Light.png" \
      "${BRAND_DIR}/NektronAI_Logo_PNG_Package/NektronAI_logo_512w_light.png" \
      "${BRAND_DIR}/NektronAI_Logo_PNG_Package/NektronAI_logo_1024w_light.png" \
      "${BRAND_DIR}/NektronAI_Logo_PNG_Package/NektronAI_logo_2048w_light.png" \
      "${BRAND_DIR}/Original Logo/Icon & Social Media/White.png" \
      "${BRAND_DIR}/Original Logo/JPGs & PNGs/White.png" \
      "${BRAND_DIR}/Original Logo/Artwork Files/1x/Artboard 1.png" \
      "${BRAND_DIR}/Original Logo/JPGs & PNGs/Logo.png" \
      || true
  )"
  ICON_SRC="$(
    pick_first_existing \
      "${BRAND_DIR}/Icon & Social Media/Icon.png" \
      "${BRAND_DIR}/Original Logo/Icon & Social Media/Icon.png" \
      "${BRAND_DIR}/Original Logo/Artwork Files/NektronAI_Icon_1024.png" \
      || true
  )"
  FAVICON_SRC="$(
    pick_first_existing \
      "${BRAND_DIR}/Favicon.png" \
      "${BRAND_DIR}/Original Logo/Favicon.png" \
      || true
  )"
  SVG_SRC="$(
    pick_first_existing \
      "${BRAND_DIR}/logo.svg" \
      "${BRAND_DIR}/Original Logo/logo.svg" \
      "${BRAND_DIR}/Old Logo/NektronAI_Logo_Lockup.svg" \
      || true
  )"

  if [[ -z "${WORDMARK_DARK_320_SRC}" && -n "${WORDMARK_LIGHT_320_SRC}" ]]; then
    WORDMARK_DARK_320_SRC="${WORDMARK_LIGHT_320_SRC}"
  fi
  if [[ -z "${WORDMARK_LIGHT_320_SRC}" && -n "${WORDMARK_DARK_320_SRC}" ]]; then
    WORDMARK_LIGHT_320_SRC="${WORDMARK_DARK_320_SRC}"
  fi

  if [[ -z "${WORDMARK_DARK_280_SRC}" && -n "${WORDMARK_DARK_320_SRC}" ]]; then
    WORDMARK_DARK_280_SRC="${WORDMARK_DARK_320_SRC}"
  fi
  if [[ -z "${WORDMARK_LIGHT_280_SRC}" && -n "${WORDMARK_LIGHT_320_SRC}" ]]; then
    WORDMARK_LIGHT_280_SRC="${WORDMARK_LIGHT_320_SRC}"
  fi

  if [[ -z "${WORDMARK_DARK_280_SRC}" && -n "${WORDMARK_LIGHT_280_SRC}" ]]; then
    WORDMARK_DARK_280_SRC="${WORDMARK_LIGHT_280_SRC}"
  fi
  if [[ -z "${WORDMARK_LIGHT_280_SRC}" && -n "${WORDMARK_DARK_280_SRC}" ]]; then
    WORDMARK_LIGHT_280_SRC="${WORDMARK_DARK_280_SRC}"
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
  if [[ -n "${SVG_SRC}" ]]; then
    cp -f "${SVG_SRC}" "${BRAND_OUT_DIR}/logo.svg"
  fi

  if [[ -z "${WORDMARK_DARK_320_SRC}" && -z "${WORDMARK_LIGHT_320_SRC}" && -z "${WORDMARK_DARK_280_SRC}" && -z "${WORDMARK_LIGHT_280_SRC}" && -z "${ICON_SRC}" && -z "${FAVICON_SRC}" && -z "${SVG_SRC}" ]]; then
    echo "WARN: No matching brand assets found in ${BRAND_DIR}; keeping existing site assets."
  fi

fi

aws s3 sync "${SITE_DIR}/" "s3://${BUCKET_NAME}/" --delete --region "${BUCKET_REGION}" \
  --exclude ".git/*" \
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
  --exclude "NektronAI_production_ready.zip"
echo "S3 sync complete."

# Find CloudFront distribution by alias
DIST_ID="$(aws cloudfront list-distributions --query "DistributionList.Items[?Aliases.Items && contains(Aliases.Items, 'nektron.ai')].Id | [0]" --output text)"

if [[ -z "${DIST_ID}" || "${DIST_ID}" == "None" ]]; then
  echo "WARN: Could not find CloudFront distribution by alias. Skipping invalidation."
  exit 0
fi

aws cloudfront create-invalidation --distribution-id "${DIST_ID}" --paths "/*" >/dev/null
echo "CloudFront invalidation submitted: ${DIST_ID}"
