# Try EB → env resources → ALBv2
LB_NAME=$(aws elasticbeanstalk describe-environment-resources --region us-east-2 \
  --environment-name interviewhelperai-prod \
  --query 'EnvironmentResources.LoadBalancers[0].Name' --output text 2>/dev/null || echo "-")

# Resolve ALBv2 DNS/zone from name
read ALB_DNS ALB_ZONE <<<"$(aws elbv2 describe-load-balancers --region us-east-2 \
  --names "$LB_NAME" \
  --query 'LoadBalancers[0].[DNSName,CanonicalHostedZoneId]' --output text 2>/dev/null || echo "- -")"

# Fallback via tags (env-name/env-id)
if [[ -z "$ALB_DNS" || "$ALB_DNS" == "-" ]]; then
  ENV_ID=$(aws elasticbeanstalk describe-environments --region us-east-2 \
    --environment-names interviewhelperai-prod \
    --query 'Environments[0].EnvironmentId' --output text 2>/dev/null || echo "")
  ALB_ARN=$(aws resourcegroupstaggingapi get-resources --region us-east-2 \
    --resource-type-filters elasticloadbalancing:loadbalancer \
    --tag-filters Key=elasticbeanstalk:environment-name,Values=interviewhelperai-prod \
    --query 'ResourceTagMappingList[0].ResourceARN' --output text 2>/dev/null || echo "")
  [[ -z "$ALB_ARN" || "$ALB_ARN" == "None" ]] && ALB_ARN=$(aws resourcegroupstaggingapi get-resources --region us-east-2 \
    --resource-type-filters elasticloadbalancing:loadbalancer \
    --tag-filters Key=elasticbeanstalk:environment-id,Values="$ENV_ID" \
    --query 'ResourceTagMappingList[0].ResourceARN' --output text 2>/dev/null || echo "")

  read ALB_DNS ALB_ZONE <<<"$(aws elbv2 describe-load-balancers --region us-east-2 \
    --load-balancer-arns "$ALB_ARN" \
    --query 'LoadBalancers[0].[DNSName,CanonicalHostedZoneId]' --output text 2>/dev/null || echo "- -")"
fi

# As a final fallback (classic ELB):
if [[ -z "$ALB_DNS" || "$ALB_DNS" == "-" ]]; then
  read ALB_DNS ALB_ZONE <<<"$(aws elb describe-load-balancers --region us-east-2 \
    --load-balancer-names "$LB_NAME" \
    --query 'LoadBalancerDescriptions[0].[DNSName,CanonicalHostedZoneNameID]' --output text 2>/dev/null || echo "- -")"
fi

echo "ALB_DNS=$ALB_DNS"
echo "ALB_ZONE=$ALB_ZONE"

