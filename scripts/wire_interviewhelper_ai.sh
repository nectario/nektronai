# --- discover Classic Load Balancer DNS + hosted zone id for the EB environment ---
REGION=us-east-2
ENV=interviewhelperai-prod

# 1) Ask EB which CLB it created for this environment
LB_NAME=$(aws elasticbeanstalk describe-environment-resources --region "$REGION" \
  --environment-name "$ENV" \
  --query 'EnvironmentResources.LoadBalancers[0].Name' --output text)

if [ -z "$LB_NAME" ] || [ "$LB_NAME" = "None" ]; then
  echo "[x] No load balancer name found for environment '$ENV' in $REGION"; exit 1
fi
echo "[i] Classic LB name: $LB_NAME"

# 2) Query ELB (v1) for DNS + CanonicalHostedZoneNameID
read LB_DNS LB_ZONE <<<"$(aws elb describe-load-balancers --region "$REGION" \
  --load-balancer-names "$LB_NAME" \
  --query 'LoadBalancerDescriptions[0].[DNSName,CanonicalHostedZoneNameID]' --output text)"

if [ -z "$LB_DNS" ] || [ "$LB_DNS" = "None" ]; then
  echo "[x] Could not resolve LB DNS/zone via ELB API"; exit 1
fi

echo "LB_DNS=${LB_DNS}"
echo "LB_ZONE=${LB_ZONE}"

