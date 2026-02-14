DOMAIN=nektron.ai
REGION=US-EAST-2   # not used here but keeping for consistency
HZ_ID=$(aws route53 list-hosted-zones-by-name --dns-name "$DOMAIN" --query 'HostedZones[0].Id' --output text)
HZ_ID=${HZ_ID#/hostedzone/}
EB_CNAME="interviewhelperai-prod.us-east-2.elasticbeanstalk.com"

cat > /tmp/r53_www_${DOMAIN}.json <<JSON
{
  "Comment":"www CNAME -> EB CNAME",
  "Changes":[
    {"Action":"UPSERT","ResourceRecordSet":{
      "Name":"www.${DOMAIN}.",
      "Type":"CLOSEST_MATCH",
      "Region":"us-east-2",
      "SetIdentifier":"www-cname",
      "ResourceRecords":[{"Value":"${EB_CNAME}"}],
      "TTL":60
    }}
  ]
}
JSON

aws route53 change-resource-record-sets --hosted-zone-id "$HZ_ID" --change-batch file:///tmp/r53_www_${DOMAIN}.json

