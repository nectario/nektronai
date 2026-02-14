HZ_ID=$(aws route53 list-hosted-zones-by-name --dns-name nektron.ai --query 'HostedZones[0].Id' --output text); HZ_ID=${HZ_ID#/hostedzone/}
cat > /tmp/apex_nektron.ai.json <<JSON
{
  "Changes":[
    {"Action":"UPSERT","ResourceRecordSet":{
      "Name":"nektron.ai.","Type":"A",
      "AliasTarget":{"HostedZoneId":"${ALB_ZONE}","DNSName":"dualstack.${ALB_DNS}","EvaluateTargetHealth":false}
    }},
    {"Action":"UPSERT","ResourceRecordSet":{
      "Name":"nektron.ai.","Type":"AAAA",
      "AliasTarget":{"HostedZoneId":"${ALB_ZONE}","DNSName":"dualstack.${ALB_DNS}","EvaluateTargetHealth":false}
    }}
  ]
}
JSON
aws route53 change-resource-record-sets --hosted-zone-id "$HZ_ID" \
  --change-batch file:///tmp/apex_nektron.ai.json

