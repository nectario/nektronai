#!/usr/bin/env bash
set -euo pipefail

# --------- CONFIG (export or edit these) ----------
: "${REGION:=us-east-2}"                 # EB region
: "${APP:=InterviewHelperAIWeb}"         # EB application name
: "${ENV:=interviewhelperai-prod}"       # EB environment name
: "${DOMAIN:?Set DOMAIN=example.tld}"    # e.g., nektron.ai or interviewhelper.ai
# -----------------------------------------------

# Pretty logs (one function per line; no single-line chaining)
logc() { printf '\033[%sm%s\033[0m\n' "$1" "$2"; }
log_i() { logc "36" "$*"; }
log_ok(){ logc "32" "$*"; }
log_warn(){ logc "33" "$*"; }
log_err(){ logc "31" "$*"; }

log_i "[i] Region : $REGION"
log_i "[i] App/Env: $APP / $ENV"
log_i "[i] Domain : $DOMAIN"
echo

# 1) Hosted Zone
HZ_ID="$(aws route53 list-hosted-zones-by-name --dns-name "$DOMAIN" \
        --query 'HostedZones[0].Id' --output text 2>/dev/null || true)"
if [[ -z "$HZ_ID" || "$HZ_ID" == "None" ]]; then
  log_err "[x] No Route 53 hosted zone found for $DOMAIN"
  exit 1
fi
HZ_ID="${HZ_ID#/hostedzone/}"
log_ok "[ok] Hosted Zone: $HZ_ID"

# 2) Nameservers
echo
log_i "Authoritative NS in Route 53:"
aws route53 list-resource-record-sets --hosted-zone-id "$HZ_ID" \
  --query "ResourceRecordSets[?Type=='NS']|[0].ResourceRecords[].Value" \
  --output text | tr '\t' '\n' || true

echo
log_i "Registrar (public) NS view:"
dig +short NS "$DOMAIN" @1.1.1.1 || true

# 3) Apex A/AAAA and www CNAME
echo
log_i "Apex A/AAAA and www CNAME records:"
aws route53 list-resource-record-sets --hosted-zone-id "$HZ_ID" --output table \
  --query "ResourceRecordSets[?Name==\`${DOMAIN}.\` || Name==\`www.${DOMAIN}.\`].[Name,Type,AliasTarget.DNSName,ResourceRecords]"

# 4) EB env → CNAME, ALB
echo
EB_CNAME="$(aws elasticbeanstalk describe-environments --region "$REGION" \
            --application-name "$APP" --environment-names "$ENV" \
            --query 'Environments[0].CNAME' --output text 2>/dev/null || echo "-")"
log_ok "[ok] EB CNAME: $EB_CNAME"

LB_NAME="$(aws elasticbeanstalk describe-environment-resources --region "$REGION" \
          --environment-name "$ENV" \
          --query 'EnvironmentResources.LoadBalancers[0].Name' --output text 2>/dev/null || echo "-")"

ALB_DNS=""; ALB_ZONE=""
if [[ "$LB_NAME" != "-" && "$LB_NAME" != "None" ]]; then
  read -r ALB_DNS ALB_ZONE <<<"$(aws elbv2 describe-load-balancers --region "$REGION" \
    --names "$LB_NAME" --query 'LoadBalancers[0].[DNSName,CanonicalHostedZoneId]' --output text 2>/dev/null || echo "- -")"
fi
if [[ -n "$ALB_DNS" && "$ALB_DNS" != "-" ]]; then
  log_ok "[ok] ALB: $ALB_DNS (zone $ALB_ZONE)"
else
  log_warn "[!] Could not resolve ALB (env resources)."
fi

# 5) Listeners (80/443)
echo
log_i "ALB listeners (80/443):"
LB_ARN="$(aws elbv2 describe-load-balancers --region "$REGION" --names "$LB_NAME" \
         --query 'LoadBalancers[0].LoadBalancerArn' --output text 2>/dev/null || echo "")"
if [[ -n "$LB_ARN" && "$LB_ARN" != "None" ]]; then
  aws elbv2 describe-listeners --region "$REGION" --load-balancer-arn "$LB_ARN" \
    --query 'Listeners[].{Port:Port,Protocol:Protocol,CertArns:Certificates[].CertificateArn}' --output table || true
else
  log_warn "[!] No LB ARN; skipping listeners."
fi

# 6) ACM certificates that cover apex + www
echo
log_i "ACM certificates (region $REGION) that cover ${DOMAIN} and www.${DOMAIN}:"
aws acm list-certificates --region "$REGION" \
  --query "CertificateSummaryList[?DomainName=='${DOMAIN}' || contains(SubjectAlternativeNameSummaries, 'www.${DOMAIN}')].[DomainName,CertificateArn]" \
  --output table || true

CERT_ARN="$(aws acm list-certificates --region "$REGION" \
  --query "CertificateSummaryList[?DomainName=='${DOMAIN}' && contains(SubjectAlternativeNameSummaries, 'www.${DOMAIN}')].CertificateArn|[0]" \
  --output text 2>/dev/null || echo "")"
if [[ -n "$CERT_ARN" && "$CERT_ARN" != "None" ]]; then
  echo
  log_i "Primary ACM cert status:"
  aws acm describe-certificate --region "$REGION" --certificate-arn "$CERT_ARN" \
    --query 'Certificate.{Status:Status,Type:Type,InUseBy:InUseBy,NotAfter:NotAfter}' --output table || true
fi

echo
log_ok "[done] Audit complete for $DOMAIN"

