# set the domain
NEK_DOMAIN=nektron.ai

# find the hosted zone id
NEK_HZ_ID=$(aws route53 list-hosted-zones-by-name \
  --dns-name "$NEK_DOMAIN" \
  --query 'HostedZones[0].Id' --output text)
NEK_HZ_ID=${NEK_HZ_ID#/hostedzone/}

# fetch current TTL and target of the existing CNAME so we can DELETE it exactly
TTL=$(aws route53 list-resource-record-sets --hosted-zone-id "$NEK_HZ_ID" \
  --query "ResourceRecordSets[?Name=='www.${NEK_DOMAIN}.' && Type=='CNAME'].TTL | [0]" \
  --output text)

TARGET=$(aws route53 list-resource-record-sets --hosted-zone-id "$NEK_HZ_ID" \
  --query "ResourceRecordSets[?Name=='www.${NEK_DOMAIN}.' && Type=='CNAME'].ResourceRecords[0].Value | [0]" \
  --output text)

# If there is no CNAME, these may be "None"; guard for that:
if [ "$TTL" = "None" ] || [ -z "$TTL" ]; then
  echo "[ok] No www CNAME exists on ${NEK_DOMAIN} — nothing to remove."
else
  cat > /tmp/del_www_${NEK_DOMAIN}.json <<JSON
{
  "Comment":"Delete wrong www CNAME pointing to InterviewHelperAI",
  "Changes":[
    {"Action":"DELETE","ResourceRecordSet":{
      "Name":"www.${NEK_DOMAIN}.",
      "Type":"CNAME",
      "TTL": ${TTL},
      "ResourceRecords":[{"Value":"${TARGET}"}]
    }}
  ]
}
JSON

  aws route53 change-resource-record-sets \
    --hosted-zone-id "$NEK_HZ_ID" \
    --change-batch file:///tmp/del_www_${NEK_DOMAIN}.json
  echo "[ok] Removed www.${NEK_DOMAIN} CNAME → ${TARGET}"
fi

