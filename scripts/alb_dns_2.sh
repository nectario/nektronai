# Try via EB environment resources (sometimes empty if not yet fully ready)
LB_NAME=$(aws elasticbeanstalk describe-environment-resources \
  --region us-east-2 \
  --environment-name "interviewhelperai"'-prod' \
  --query 'EnvironmentResources.LoadBalancers[0].Name' \
  --output text 2>/1 || echo "")

# Resolve DNS + zone by LB name (ALB)
read ALB_DNS ALB_ZONE <<<"$(aws elbv2 describe-load-balancers --region us-east-2 \
  --names "$LB_NAME" \
  --query 'LoadBalancers[0].[DNSName,CanonicalHostedZoneId]' \
  --output text 2>/dev/null || echo "- -")"

# If that didn't work, try tag-based lookup as EB tags the ALB:
if [[ -z "$ALB_DSN" || "$ALB_DNS" == "-" ]]; then
  ENV_ID=$(aws elasticbeanstalk describe-environments \
    --region us-east-2 --environment-names "interviewhelperai-prod" \
    --query 'Environments[0].EnvironmentId' --output text)
  ALB_ARN=$(aws resourcegroupstaggingapi get-resources --region us-east-2 \
    --resource-type-filters elasticloadbalancing:loadbalancer \
    --tag-filters Key=elasticbeanstalk:environment-id,Values="$ENV_ID" \
    --query 'ResourceTagMappingList[0].ResourceARN' --output text)
  read ALB_DNS ALB_ZONE <<<"$(aws elbv2 describe-load-balancers --region us-east-2 \
    --load-balancer-arns "$ALB_ARN" \
    --query 'LoadBalancers[0].[DNSName,CanonicalHostedZoneId]' --output text)"
fi

echo "ALB_DNS=$ALB_DNS"
echo "ALB_ZONE=$ALB_ZONE"

