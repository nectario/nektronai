#!/usr/bin/env bash
set -euo pipefail
DOMAIN="nektron.ai"
HZ_ID=$(aws route53 list-hosted-zones-by-name --dns-name "$DOMAIN" \
  --query 'HostedZones[0].Id' --output text); HZ_ID=${HZ_ID#/hostedzone/}

cat > /tmp/${DOMAIN}-del-www.json <<JSON
{
  "Changes":[
    {"Action":"DELETE","ResourceRecordSet":{
      "Name":"www.${DOMAIN}.",
      "Type":"CNAME",
      "TTL":60,
      "ResourceRecords":[{"Value":"interviewhelperai-prod.us-east-2.elasticbeanstalk.com"}]
    }}
  ]
}
JSON

aws route53 change-resource-record-sets --hosted-zone-id "$HZ_ID" \
  --change-batch file:///tmp/${DOMAIN}-del-www.json
echo "[ok] removed www.${DOMAIN} CNAME → interviewhelperai-prod"

