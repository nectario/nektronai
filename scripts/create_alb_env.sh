#!/usr/bin/env bash
set -euo pipefail

# ==========
# Helpers
# ==========
c(){ local code="$1"; shift; printf "\033[%sm%s\033[0m\n" "$code" "$*"; }
info(){ c "36" "[i] $*"; }
ok(){   c "32" "[ok] $*"; }
warn(){ c "33" "[warn] $*"; }
err(){  c "31" "[x] $*"; }

need(){ command -v "$1" >/dev/null 2>&1 || { err "Missing dependency: $1"; exit 1; }; }

json_escape() {
  python3 - <<'PY' "$1"
import json,sys
print(json.dumps(sys.argv[1]))
PY
}

# ==========
# Defaults (override with flags or env)
# ==========
REGION="${REGION:-us-east-2}"
APP="${APP:-InterviewHelperAIWeb}"
SRC_ENV="${SRC_ENV:-interviewhelperai-prod}"       # existing (CLB) env to clone
NEW_ENV="${NEW_ENV:-interviewhelperai-alb-prod}"   # new ALB env name
CNAME="${CNAME:-ihai-alb}"                          # EB URL prefix

NEW_DOMAIN="${NEW_DOMAIN:-interviewhelper.ai}"     # apex domain to wire
WWW_HOST="www.${NEW_DOMAIN}"

HEALTH_PATH="${HEALTH_PATH:-/health}"

# If you already have an ISSUED ACM cert, set ACM_ARN to skip discovery
ACM_ARN="${ACM_ARN:-}"

NO_DNS=0
NO_HTTPS=0

usage(){
  cat <<USAGE
Usage:
  $(basename "$0") [--region us-east-2] [--app NAME] [--src-env NAME] [--new-env NAME] [--cname PREFIX] \\
                   [--domain interviewhelper.ai] [--health /health] [--cert-arn ARN] [--no-dns] [--no-https]

Example:
  $(basename "$0") --region us-east-2 --app InterviewHelperAIWeb --src-env interviewhelperai-prod \\
                   --new-env interviewhelperai-alb-prod --cname interviewhelperai-alb \\
                   --domain interviewhelper.ai
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --region) REGION="$2"; shift 2;;
    --app) APP="$2"; shift 2;;
    --src-env) SRC_ENV="$2"; shift 2;;
    --new-env) NEW_ENV="$2"; shift 2;;
    --cname) CNAME="$2"; shift 2;;
    --domain) NEW_DOMAIN="$2"; WWW_HOST="www.${NEW_DOMAIN}"; shift 2;;
    --health) HEALTH_PATH="$2"; shift 2;;
    --cert-arn) ACM_ARN="$2"; shift 2;;
    --no-dns) NO_DNS=1; shift;;
    --no-https) NO_HTTPS=1; shift;;
    -h|--help) usage; exit 0;;
    *) err "Unknown argument: $1"; usage; exit 1;;
  esac
done

need aws
need jq
need python3

info "Region      : $REGION"
info "App         : $APP"
info "Clone from  : $SRC_ENV"
info "Create env  : $NEW_ENV (CNAME=$CNAME)"
info "Domain      : $NEW_DOMAIN"
info "Health path : $HEALTH_PATH"
[[ -n "$ACM_ARN" ]] && info "Using ACM ARN : $ACM_ARN"
[[ $NO_HTTPS -eq 1 ]] && warn "HTTPS disabled (--no-https)"
[[ $NO_DNS -eq 1 ]] && warn "DNS wiring disabled (--no-dns)"

# ==========
# Discover latest Node.js on Amazon Linux 2023 (22→20→any)  << REPLACE THIS BLOCK
# ==========
discover_platform() {
  local needle="$1"   # e.g., "Node.js 22" or "Node.js"
  aws elasticbeanstalk list-platform-versions --region "$REGION" \
    --filters "Type=PlatformName,Operator=contains,Values=Amazon Linux 2023" \
              "Type=PlatformName,Operator=contains,Values=${needle}" \
    --query 'PlatformSummaryList[?PlatformStatus==`Ready`]
             | sort_by(@,&PlatformVersion)[-1].PlatformArn' \
    --output text 2>/dev/null || true
}

info "Discovering latest Node.js on Amazon Linux 2023 platform…"
PLATFORM_ARN="$(discover_platform "Node.js 22")"
if [[ -z "$PLATFORM_ARN" || "$PLATFORM_ARN" == "None" ]]; then
  PLATFORM_ARN="$(discover_platform "Node.js 20")"
fi
if [[ -z "$PLATFORM_ARN" || "$PLATFORM_ARN" == "None" ]]; then
  PLATFORM_ARN="$(discover_platform "Node.js")"
fi

if [[ -z "$PLATFORM_ARN" || "$PLATFORM_ARN" == "None" ]]; then
  err "No Node.js platform on Amazon Linux 2023 found in $REGION."
  info "Tip: see what's available with:"
  info "  aws elasticbeanstalk list-platform-versions --region $REGION \\"
  info "    --filters 'Type=PlatformName,Operator=contains,Values=Amazon Linux 2023' \\"
  info "              'Type=PlatformName,Operator=contains,Values=Node.js' \\"
  info "    --query 'PlatformSummaryList[?PlatformStatus==\`Ready\`].[PlatformArn,PlatformVersion,PlatformName]' --output table"
  exit 1
fi
ok "Platform ARN: $PLATFORM_ARN"

# ==========
# Determine version label to deploy
# ==========
info "Resolving VersionLabel to deploy (from source env or latest)..."
SRC_VERSION=$(
  aws elasticbeanstalk describe-environments \
    --region "$REGION" --application-name "$APP" --environment-names "$SRC_ENV" \
    --query 'Environments[0].VersionLabel' --output text 2>/dev/null || true
)
if [[ -z "$SRC_VERSION" || "$SRC_VERSION" == "None" ]]; then
  SRC_VERSION=$(
    aws elasticbeanstalk describe-application-versions \
      --region "$REGION" --application-name "$APP" \
      --query 'reverse(sort_by(ApplicationVersions,&DateCreated))[0].VersionLabel' \
      --output text
  )
  warn "Source env has no VersionLabel; using latest app version: $SRC_VERSION"
else
  ok "Using source env version: $SRC_VERSION"
fi

# ==========
# Pull source config & keep safe settings (drop classic ELB namespaces)
# ==========
TMP_CFG="$(mktemp)"
aws elasticbeanstalk describe-configuration-settings \
  --region "$REGION" --application-name "$APP" --environment-name "$SRC_ENV" \
  --query 'ConfigurationSettings[0].OptionSettings' \
  --output json > "$TMP_CFG"

SAFE_SETTINGS=$(jq '
  [ .[] 
    | select(.Namespace
      | startswith("aws:elasticbeanstalk:application:environment")
      or startswith("aws:autoscaling:")
      or startswith("aws:ec2:")
      or startswith("aws:elasticbeanstalk:environment")
      or startswith("aws:elasticbeanstalk:managedactions")
      or startswith("aws:elasticbeanstalk:monitoring")
      or startswith("aws:elasticbeanstalk:hostmanager"))
    | select(.Namespace | startswith("aws:elb:") | not) ]' "$TMP_CFG")

ALB_SETTINGS=$(cat <<JSON
[
  {"Namespace":"aws:elasticbeanstalk:environment","OptionName":"LoadBalancerType","Value":"application"},
  {"Namespace":"aws:elasticbeanstalk:environment:process:default","OptionName":"HealthCheckPath","Value":$(json_escape "$HEALTH_PATH")},
  {"Namespace":"aws:autoscaling:launchconfiguration","OptionName":"IamInstanceProfile","Value":"aws-elasticbeanstalk-ec2-role"},
  {"Namespace":"aws:elasticbeanstalk:environment","OptionName":"ServiceRole","Value":"aws-elasticbeanstalk-service-role"}
]
JSON
)

ADD_HTTPS="[]"
if [[ $NO_HTTPS -eq 0 ]]; then
  if [[ -z "$ACM_ARN" ]]; then
    info "Searching for ISSUED ACM cert that covers $NEW_DOMAIN ..."
    ACM_ARN=$(
      aws acm list-certificates --region "$REGION" --certificate-statuses ISSUED \
        --query "CertificateSummaryList[?contains(DomainName, \`$NEW_DOMAIN\`) || contains(SubjectAlternativeNameSummaries, \`$NEW_DOMAIN\`)].CertificateArn | [0]" \
        --output text 2>/dev/null || true
    )
  fi
  if [[ -n "$ACM_ARN" && "$ACM_ARN" != "None" ]]; then
    ok "Using ACM cert: $ACM_ARN"
    ADD_HTTPS=$(cat <<JSON
[
  {"Namespace":"aws:elbv2:listener:443","OptionName":"Protocol","Value":"HTTPS"},
  {"Namespace":"aws:elbv2:listener:443","OptionName":"SSLCertificateArns","Value":$(json_escape "$ACM_ARN")},
  {"Namespace":"aws:elbv2:listener:443","OptionName":"SSLPolicy","Value":"ELBSecurityPolicy-TLS13-1-2-2021-06"}
]
JSON
)
  else
    warn "No ISSUED ACM cert found for $NEW_DOMAIN; creating env without 443 (you can attach later)."
  fi
fi

OPTION_SETTINGS=$(jq -n \
  --argjson safe "$SAFE_SETTINGS" \
  --argjson alb  "$ALB_SETTINGS" \
  --argjson https "$ADD_HTTPS" \
  '$safe + $alb + $https')

# ==========
# Create environment (idempotent)
# ==========
EXISTS=$(aws elasticbeanstalk describe-environments \
  --region "$REGION" --application-name "$APP" --environment-names "$NEW_ENV" \
  --query 'Environments[0].Status' --output text 2>/dev/null || true)

if [[ -n "$EXISTS" && "$EXISTS" != "None" ]]; then
  warn "Environment $NEW_ENV already exists (status=$EXISTS). Skipping create."
else
  info "Creating ALB environment $NEW_ENV ..."
  aws elasticbeanstalk create-environment \
    --region "$REGION" \
    --application-name "$APP" \
    --environment-name "$NEW_ENV" \
    --cname-prefix "$CNAME" \
    --version-label "$SRC_VERSION" \
    --platform-arn "$PLATFORM_ARN" \
    --option-settings "$OPTION_SETTINGS" >/dev/null

  info "Waiting for environment to be discoverable..."
  aws elasticbeanstalk wait environment-exists --region "$REGION" --environment-names "$NEW_ENV"

  info "Waiting until Ready..."
  for i in {1..120}; do
    ST=$(aws elasticbeanstalk describe-environments --region "$REGION" --application-name "$APP" --environment-names "$NEW_ENV" \
          --query 'Environments[0].{Status:Status,Health:Health}' --output text)
    info "  status/health: $ST"
    [[ "$ST" == *"Ready"* ]] && break
    sleep 10
  done
fi

ENV_CNAME=$(aws elasticbeanstalk describe-environments --region "$REGION" --application-name "$APP" --environment-names "$NEW_ENV" \
  --query 'Environments[0].CNAME' --output text)
ok "New EB URL: http://$ENV_CNAME"

# ==========
# Resolve ALB by tag
# ==========
get_alb_by_env() {
  local env="$1"
  local arns
  arns=$(aws elbv2 describe-load-balancers --region "$REGION" \
          --query "LoadBalancers[?Type=='application'].LoadBalancerArn" --output text | tr '\t' '\n' || true)
  for arn in $arns; do
    local has
    has=$(aws elbv2 describe-tags --region "$REGION" --resource-arns "$arn" \
            --query "TagDescriptions[0].Tags[?Key=='elasticbeanstalk:environment-name' && Value=='$env'] | length(@)" \
            --output text 2>/dev/null || echo 0)
    if [[ "$has" == "1" ]]; then
      aws elbv2 describe-load-balancers --region "$REGION" --load-balancer-arns "$arn" \
        --query 'LoadBalancers[0].{DNS:DNSName,Zone:CanonicalHostedZoneId,ARN:LoadBalancerArn}' --output json
      return 0
    fi
  done
  return 1
}

ALB_JSON=$(get_alb_by_env "$NEW_ENV" || true)
if [[ -z "$ALB_JSON" ]]; then
  warn "Could not resolve ALB; skipping DNS wiring."
  NO_DNS=1
else
  ALB_DNS=$(echo "$ALB_JSON" | jq -r '.DNS')
  ALB_ZONE=$(echo "$ALB_JSON" | jq -r '.Zone')
  ok "ALB DNS : $ALB_DNS"
  ok "ALB Zone : $ALB_ZONE"
fi

# ==========
# Route 53 wiring (A/AAAA alias → ALB, www CNAME → apex)
# ==========
if [[ $NO_DNS -eq 0 && -n "${ALB_DNS:-}" && -n "${ALB_ZONE:-}" ]]; then
  HOSTED_ZONE_ID=$(
    aws route53 list-hosted-zones-by-name --dns-name "$NEW_DOMAIN" \
      --query 'HostedZones[?Name==`'"$NEW_DOMAIN."\"'] | [0].Id' --output text 2>/dev/null || true
  )
  if [[ -z "$HOSTED_ZONE_ID" || "$HOSTED_ZONE_ID" == "None" ]]; then
    warn "No Route 53 hosted zone for $NEW_DOMAIN. Creating one..."
    HZ_OUT=$(aws route53 create-hosted-zone --name "$NEW_DOMAIN" --caller-reference "ihai-$(date +%s)")
    HOSTED_ZONE_ID=$(echo "$HZ_OUT" | jq -r '.HostedZone.Id')
    ok "Hosted zone created: $HOSTED_ZONE_ID"
    warn "Update registrar NS to Route 53 before HTTPS can validate."
  fi

  CHANGES=$(cat <<JSON
{
  "Comment": "interviewhelper.ai → ALB ($NEW_ENV)",
  "Changes": [
    {
      "Action": "UPSERT",
      "ResourceRecordSet": {
        "Name": "$NEW_DOMAIN.",
        "Type": "A",
        "AliasTarget": {
          "HostedZoneId": "$ALB_ZONE",
          "DNSName": "dualstack.${ALB_DNS}.",
          "EvaluateTargetHealth": false
        }
      }
    },
    {
      "Action": "UPSERT",
      "ResourceRecordSet": {
        "Name": "$NEW_DOMAIN.",
        "Type": "AAAA",
        "AliasTarget": {
          "HostedZoneId": "$ALB_ZONE",
          "DNSName": "dualstack.${ALB_DNS}.",
          "EvaluateTargetHealth": false
        }
      }
    },
    {
      "Action": "UPSERT",
      "ResourceRecordSet": {
        "Name": "$WWW_HOST.",
        "Type": "CNAME",
        "TTL": 60,
        "ResourceRecords": [{ "Value": "$NEW_DOMAIN." }]
      }
    }
  ]
}
JSON
)
  info "Upserting Route 53 DNS for $NEW_DOMAIN and $WWW_HOST ..."
  aws route53 change-resource-record-sets --hosted-zone-id "$HOSTED_ZONE_ID" --change-batch "$CHANGES" >/dev/null
  ok "DNS wired."
else
  warn "DNS wiring skipped."
fi

cat <<OUT

[done] New ALB environment created.

  App           : $APP
  Old env       : $SRC_ENV
  New env       : $NEW_ENV
  EB URL        : http://$ENV_CNAME
  Health path   : $HEALTH_PATH
  Domain        : $NEW_DOMAIN
  HTTPS         : $([[ -n "${ACM_ARN:-}" && $NO_HTTPS -eq 0 ]] && echo "attached" || echo "not attached")

If HTTPS wasn't attached:
  1) Request an ACM cert in $REGION for $NEW_DOMAIN and www.$NEW_DOMAIN (DNS validation).
  2) Then attach it:

     aws elasticbeanstalk update-environment --region $REGION --environment-name $NEW_ENV \\
       --option-settings Namespace=aws:elbv2:listener:443,OptionName=Protocol,Value=HTTPS \\
                         Namespace=aws:elbv2:listener:443,OptionName=SSLCertificateArns,Value=<ACM_ARN> \\
                         Namespace=aws:elbv2:listener:443,OptionName=SSLPolicy,Value=ELBSecurityPolicy-TLS13-1-2-2021-06

When you are satisfied, keep DNS on the new env or swap EB URLs between old and new.
OUT

