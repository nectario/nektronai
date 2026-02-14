REGION=us-east-2
DOMAIN=nektron.ai
HZ_ID=$(aws route53 list-hosted-zones-by-name --dns-name "$DOMAIN" --query 'HostedZones[0].Id' --output text); HZ_ID=${HZ_ID#/hostedzone/}
EB_CNAME="interviewhelperai-prod.us-east-2.elasticbeanstalk.com"

cat > /tmp/r53_www_${DOMAIN}.json <<JSON
{
  "Changes":[{"Action":"UPSERT","ResourceRecordSet":{
    "Name":"www.${DOMAIN}.",
    "Type":"CNAME",
    "TTL":60,
    "ResourceRecords":[{"Value":"${EB_CNAME}"}]
  }}]
}
JSON

aws route53 change-resource-record-sets --hosted-zone-id "$HZ_ID" \
  --change-batch file:///tmp/r53_www_${DOMAIN}.json

