AI_DOMAIN=interviewhelper.ai

# Route 53 hosted zone for the .ai domain
AI_HZ_ID=$(aws route53 list-hosted-zones-by-name --dns-name "$AI_DOMAIN" \
  --query 'HostedZones[0].Id' --output text); AI_HZ_ID=${AI_HZ_ID#/hostedzone/}

if [ -z "$AI_HZ_ID" ] || [ "$AI_HZ_ID" = "None" ]; then
  echo "[x] Hosted zone for ${AI_DOMAIN} not found in Route 53"; exit 1
fi

# APEX A alias -> Classic LB
cat > /tmp/apex_${AI_DOMAIN}.json <<JSON
{
  "Changes":[
    {"Action":"UPSERT","ResourceRecordSet":{
      "Name":"${AI_DOMAIN}.",
      "Type":"A",
      "AliasTarget":{
        "HostedZoneId":"${LB_ZONE}",
        "DNSName":"${LB_DNS}",
        "EvaluateTargetHealth":false
      }
    }}
  ]
}
JSON

aws route53 change-resource-record-sets \
  --hosted-zone-id "$AI_HZ_ID" \
  --change-batch file:///tmp/apex_${AI_DOMAIN}.json
echo "[ok] ${AI_DOMAIN} A (alias) → ${LB_DNS}"

# Optional AAAA (many Classic LBs support dualstack; if this errors, skip AAAA)
cat > /tmp/aaaa_${AI_DOMAIN}.json <<JSON
{
  "Changes":[
    {"Action":"UPSERT","ResourceRecordSet":{
      "Name":"${AI_DOMAIN}.",
      "Type":"AAAA",
      "AliasTarget":{
        "HostedZoneId":"${LB_ZONE}",
        "DNSName":"dualstack.${LB_DNS}",
        "EvaluateTargetHealth":false
      }
    }}
  ]
}
JSON
aws route53 change-resource-record-sets \
  --hosted-zone-id "$AI_HZ_ID" \
  --change-batch file:///tmp/aaaa_${AI_DOMAIN}.json || echo "[warn] AAAA alias failed (may be unsupported for this CLB) – safe to ignore."

# WWW -> APEX
cat > /tmp/www_${AI_DOMAIN}.json <<JSON
{
  "Changes":[
    {"Action":"UPSERT","ResourceRecordSet":{
      "Name":"www.${AI_DOMAIN}.",
      "Type":"CNAME",
      "TTL":60,
      "ResourceRecords":[{"Value":"${AI_DOMAIN}"}]
    }}
  ]
}
JSON

aws route53 change-resource-record-sets \
  --hosted-zone-id "$AI_HZ_ID" \
  --change-batch file:///tmp/www_${AI_DOMAIN}.json
echo "[ok] www.${AI_DOMAIN} CNAME → ${AI_DOMAIN}"

