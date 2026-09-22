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
require_cmd jq
require_cmd sed

AWS_REGION="${AWS_REGION:-}"
EB_ENV_NAME="${EB_ENV_NAME:-}"
EB_APP_NAME="${EB_APP_NAME:-}"

if [[ -z "${AWS_REGION}" ]]; then
  AWS_REGION="$(aws configure get region || true)"
fi
if [[ -z "${AWS_REGION}" ]]; then
  echo "ERROR: AWS_REGION not set and no default AWS CLI region configured."
  exit 1
fi

log "Using region: ${AWS_REGION}"

# --- Discover EB environment if not provided ---
if [[ -z "${EB_ENV_NAME}" ]]; then
  log "EB_ENV_NAME not set; attempting auto-detect of a Ready environment..."

  READY_QUERY="Environments[?Status=='Ready'].EnvironmentName"
  if [[ -n "${EB_APP_NAME}" ]]; then
    READY_QUERY="Environments[?Status=='Ready' && ApplicationName=='${EB_APP_NAME}'].EnvironmentName"
  fi

  mapfile -t READY_ENVS < <(
    aws elasticbeanstalk describe-environments \
      --region "${AWS_REGION}" \
      --query "${READY_QUERY}" \
      --output text \
      | tr '\t' '\n' \
      | sed '/^$/d'
  )

  if [[ "${#READY_ENVS[@]}" -eq 0 ]]; then
    echo "ERROR: Could not detect any Ready Elastic Beanstalk environment."
    if [[ -n "${EB_APP_NAME}" ]]; then
      echo "       Application filter used: ${EB_APP_NAME}"
    fi
    echo "       Set EB_ENV_NAME and retry."
    exit 1
  fi

  if [[ "${#READY_ENVS[@]}" -gt 1 ]]; then
    echo "ERROR: Multiple Ready environments found. Set EB_ENV_NAME to avoid targeting the wrong environment."
    printf '       Ready environments: %s\n' "${READY_ENVS[*]}"
    exit 1
  fi

  EB_ENV_NAME="${READY_ENVS[0]}"
fi

if [[ -z "${EB_ENV_NAME}" || "${EB_ENV_NAME}" == "None" ]]; then
  echo "ERROR: Could not detect Elastic Beanstalk environment. Set EB_ENV_NAME and retry."
  exit 1
fi

if [[ -n "${EB_APP_NAME}" ]]; then
  log "Using Elastic Beanstalk app filter: ${EB_APP_NAME}"
fi
log "Using Elastic Beanstalk environment: ${EB_ENV_NAME}"

# --- Discover ALB ref (name or ARN) from EB env resources ---
LB_REF="$(aws elasticbeanstalk describe-environment-resources \
  --region "${AWS_REGION}" \
  --environment-name "${EB_ENV_NAME}" \
  --query "EnvironmentResources.LoadBalancers[0].Name" \
  --output text)"

if [[ -z "${LB_REF}" || "${LB_REF}" == "None" ]]; then
  echo "ERROR: Could not find a Load Balancer attached to EB env ${EB_ENV_NAME}."
  exit 1
fi

log "Load balancer reference: ${LB_REF}"

# --- Get ALB details (DNS name + canonical hosted zone id) ---
if [[ "${LB_REF}" == arn:aws:elasticloadbalancing:*:loadbalancer/* ]]; then
  LB_LOOKUP_FLAG="--load-balancer-arns"
else
  LB_LOOKUP_FLAG="--names"
fi

if ! ALB_JSON="$(aws elbv2 describe-load-balancers \
  --region "${AWS_REGION}" \
  "${LB_LOOKUP_FLAG}" "${LB_REF}" \
  --query "LoadBalancers[0]" \
  --output json)"; then
  echo "ERROR: Failed to describe ALB via elbv2. Ensure EB is using an Application Load Balancer."
  exit 1
fi

ALB_ARN="$(echo "${ALB_JSON}" | jq -r '.LoadBalancerArn // empty')"
ALB_DNS="$(echo "${ALB_JSON}" | jq -r '.DNSName // empty')"
ALB_CANONICAL_ZONE_ID="$(echo "${ALB_JSON}" | jq -r '.CanonicalHostedZoneId // empty')"

if [[ -z "${ALB_ARN}" || -z "${ALB_DNS}" || -z "${ALB_CANONICAL_ZONE_ID}" ]]; then
  echo "ERROR: Incomplete ALB details returned from AWS."
  exit 1
fi

# Avoid accidental dualstack.dualstack.*
ALIAS_DNS="${ALB_DNS}"
if [[ "${ALIAS_DNS}" != dualstack.* ]]; then
  ALIAS_DNS="dualstack.${ALIAS_DNS}"
fi

log "ALB ARN: ${ALB_ARN}"
log "ALB DNS: ${ALB_DNS}"
log "ALB Alias DNS: ${ALIAS_DNS}"
log "ALB Canonical ZoneId: ${ALB_CANONICAL_ZONE_ID}"

# --- Find hosted zones exactly (public zones only) ---
get_hosted_zone_id() {
  local domain="$1"
  aws route53 list-hosted-zones-by-name \
    --dns-name "${domain}" \
    --output json \
    | jq -r --arg fqdn "${domain}." '.HostedZones[] | select(.Name == $fqdn and .Config.PrivateZone == false) | .Id' \
    | sed 's|/hostedzone/||' \
    | head -n1
}

HZ_COM_ID="$(get_hosted_zone_id "nektron.com")"
HZ_AI_ID="$(get_hosted_zone_id "nektron.ai")"

if [[ -z "${HZ_COM_ID}" || "${HZ_COM_ID}" == "None" ]]; then
  echo "ERROR: Could not find public hosted zone for nektron.com"
  exit 1
fi
if [[ -z "${HZ_AI_ID}" || "${HZ_AI_ID}" == "None" ]]; then
  echo "ERROR: Could not find public hosted zone for nektron.ai"
  exit 1
fi

log "Hosted zone nektron.com: ${HZ_COM_ID}"
log "Hosted zone nektron.ai:  ${HZ_AI_ID}"

# --- Helper: upsert alias record ---
upsert_alias() {
  local zone_id="$1"
  local name="$2"
  local type="$3" # A or AAAA

  log "Upserting ${type} alias ${name} in zone ${zone_id} -> ${ALIAS_DNS}"

  aws route53 change-resource-record-sets \
    --hosted-zone-id "${zone_id}" \
    --change-batch "{
      \"Changes\": [{
        \"Action\": \"UPSERT\",
        \"ResourceRecordSet\": {
          \"Name\": \"${name}\",
          \"Type\": \"${type}\",
          \"AliasTarget\": {
            \"HostedZoneId\": \"${ALB_CANONICAL_ZONE_ID}\",
            \"DNSName\": \"${ALIAS_DNS}\",
            \"EvaluateTargetHealth\": false
          }
        }
      }]
    }" >/dev/null
}

# --- Route53: point nektron.com + www.nektron.com to ALB ---
upsert_alias "${HZ_COM_ID}" "nektron.com." "A"
upsert_alias "${HZ_COM_ID}" "www.nektron.com." "A"

# Optional AAAA (safe if you want IPv6 too)
upsert_alias "${HZ_COM_ID}" "nektron.com." "AAAA"
upsert_alias "${HZ_COM_ID}" "www.nektron.com." "AAAA"

# --- Request ACM cert for both domains (new cert; ACM can't add SANs to existing) ---
log "Requesting ACM certificate (DNS validation) for nektron.ai + nektron.com"
CERT_ARN="$(aws acm request-certificate \
  --region "${AWS_REGION}" \
  --domain-name "nektron.ai" \
  --subject-alternative-names "www.nektron.ai" "nektron.com" "www.nektron.com" \
  --validation-method DNS \
  --query "CertificateArn" \
  --output text)"

if [[ -z "${CERT_ARN}" || "${CERT_ARN}" == "None" ]]; then
  echo "ERROR: Failed to request ACM certificate."
  exit 1
fi

log "Certificate ARN: ${CERT_ARN}"

# --- Create DNS validation records in correct zones ---
log "Fetching domain validation records..."
VAL_RECS="[]"
for _ in {1..30}; do
  VAL_RECS="$(aws acm describe-certificate \
    --region "${AWS_REGION}" \
    --certificate-arn "${CERT_ARN}" \
    --query "Certificate.DomainValidationOptions[].ResourceRecord" \
    --output json)"

  if [[ "$(echo "${VAL_RECS}" | jq '[.[] | select(. != null)] | length')" -gt 0 ]]; then
    break
  fi
  sleep 5
done

if [[ "$(echo "${VAL_RECS}" | jq '[.[] | select(. != null)] | length')" -eq 0 ]]; then
  echo "ERROR: Validation records were not generated in time."
  exit 1
fi

# Each element: {Name, Type, Value}
echo "${VAL_RECS}" | jq -c '.[] | select(. != null)' | while read -r rec; do
  NAME="$(echo "${rec}" | jq -r '.Name')"
  TYPE="$(echo "${rec}" | jq -r '.Type')"
  VALUE="$(echo "${rec}" | jq -r '.Value')"

  # Choose zone based on suffix
  ZONE="${HZ_AI_ID}"
  if [[ "${NAME}" == *.nektron.com. ]]; then
    ZONE="${HZ_COM_ID}"
  fi

  log "Upserting validation record ${NAME} into zone ${ZONE}"
  aws route53 change-resource-record-sets \
    --hosted-zone-id "${ZONE}" \
    --change-batch "{
      \"Changes\": [{
        \"Action\": \"UPSERT\",
        \"ResourceRecordSet\": {
          \"Name\": \"${NAME}\",
          \"Type\": \"${TYPE}\",
          \"TTL\": 300,
          \"ResourceRecords\": [{\"Value\": \"${VALUE}\"}]
        }
      }]
    }" >/dev/null
done

log "Waiting for certificate to be issued (this can take a few minutes)..."
aws acm wait certificate-validated --region "${AWS_REGION}" --certificate-arn "${CERT_ARN}"
log "Certificate validated!"

# --- Attach cert to ALB 443 listener ---
LISTENER_ARN="$(aws elbv2 describe-listeners \
  --region "${AWS_REGION}" \
  --load-balancer-arn "${ALB_ARN}" \
  --query "Listeners[?Port==\`443\`].ListenerArn | [0]" \
  --output text)"

if [[ -z "${LISTENER_ARN}" || "${LISTENER_ARN}" == "None" ]]; then
  echo "ERROR: No :443 listener found on the ALB. Enable HTTPS on the EB environment first, then re-run."
  exit 1
fi

EXISTING_CERTS="$(aws elbv2 describe-listener-certificates \
  --region "${AWS_REGION}" \
  --listener-arn "${LISTENER_ARN}" \
  --query "Certificates[].CertificateArn" \
  --output text || true)"

if echo "${EXISTING_CERTS}" | tr '\t' '\n' | grep -Fxq "${CERT_ARN}"; then
  log "Certificate already attached to listener; skipping cert attach."
else
  # Add as SNI certificate by default to avoid replacing the current production default cert.
  log "Adding certificate to ALB :443 listener (SNI cert attach)..."
  aws elbv2 add-listener-certificates \
    --region "${AWS_REGION}" \
    --listener-arn "${LISTENER_ARN}" \
    --certificates "CertificateArn=${CERT_ARN}" >/dev/null
fi

SET_DEFAULT_CERT="${SET_DEFAULT_CERT:-false}"
if [[ "${SET_DEFAULT_CERT}" == "true" ]]; then
  log "SET_DEFAULT_CERT=true, updating default listener certificate..."
  aws elbv2 modify-listener \
    --region "${AWS_REGION}" \
    --listener-arn "${LISTENER_ARN}" \
    --certificates "CertificateArn=${CERT_ARN}" >/dev/null
fi

log "Done."
log "Verify:"
log "  curl -I https://nektron.com"
log "  curl -I https://www.nektron.com"
log "  aws elbv2 describe-listener-certificates --region ${AWS_REGION} --listener-arn ${LISTENER_ARN}"
