#!/usr/bin/env bash
set -euo pipefail

DOMAIN="nektron.ai"
WWW_DOMAIN="www.nektron.ai"
HOSTED_ZONE_ID="Z07806793LCB4P8REHMLC"

BUCKET_REGION="us-east-2"
CERT_REGION="us-east-1"

ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
BUCKET_NAME="nektron-ai-site-${ACCOUNT_ID}"

echo "== NektronAI site infra =="
echo "Domain: ${DOMAIN}"
echo "Bucket: ${BUCKET_NAME} (${BUCKET_REGION})"
echo "HostedZone: ${HOSTED_ZONE_ID}"

echo
echo "== 1) Create S3 bucket (private) =="
if aws s3api head-bucket --bucket "${BUCKET_NAME}" 2>/dev/null; then
  echo "Bucket already exists: ${BUCKET_NAME}"
else
  aws s3api create-bucket \
    --bucket "${BUCKET_NAME}" \
    --region "${BUCKET_REGION}" \
    --create-bucket-configuration LocationConstraint="${BUCKET_REGION}"
  echo "Created bucket: ${BUCKET_NAME}"
fi

aws s3api put-public-access-block --bucket "${BUCKET_NAME}" --public-access-block-configuration \
  BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true

aws s3api put-bucket-ownership-controls --bucket "${BUCKET_NAME}" --ownership-controls \
  'Rules=[{ObjectOwnership=BucketOwnerEnforced}]'

echo
echo "== 2) Request ACM certificate (DNS validation; CloudFront requires us-east-1) =="
CERT_ARN="$(aws acm request-certificate \
  --region "${CERT_REGION}" \
  --domain-name "${DOMAIN}" \
  --subject-alternative-names "${WWW_DOMAIN}" \
  --validation-method DNS \
  --query CertificateArn \
  --output text)"

echo "Certificate ARN: ${CERT_ARN}"

echo
echo "== 3) Create/UPSERT Route53 validation records for ACM =="
python3 - "${CERT_ARN}" "${HOSTED_ZONE_ID}" <<'PY'
import json, subprocess, sys, time

CERT_REGION="us-east-1"
CERT_ARN=sys.argv[1]
HOSTED_ZONE_ID=sys.argv[2]

def aws_json(cmd):
  out = subprocess.check_output(cmd, text=True)
  return json.loads(out)

for _ in range(30):
  d = aws_json(["aws","acm","describe-certificate","--region",CERT_REGION,"--certificate-arn",CERT_ARN])
  opts = d.get("Certificate", {}).get("DomainValidationOptions", [])
  recs = []
  for o in opts:
    rr = o.get("ResourceRecord")
    if rr and rr.get("Name") and rr.get("Type") and rr.get("Value"):
      recs.append(rr)
  if recs:
    break
  time.sleep(2)

if not recs:
  raise SystemExit("ACM did not return DNS validation records in time.")

changes = []
for rr in recs:
  changes.append({
    "Action":"UPSERT",
    "ResourceRecordSet":{
      "Name": rr["Name"],
      "Type": rr["Type"],
      "TTL": 300,
      "ResourceRecords":[{"Value": rr["Value"]}],
    }
  })

batch = {"Comment":"ACM validation records (NektronAI website)","Changes":changes}
subprocess.check_call([
  "aws","route53","change-resource-record-sets",
  "--hosted-zone-id",HOSTED_ZONE_ID,
  "--change-batch", json.dumps(batch)
])
print(f"UPSERTed {len(changes)} validation record(s).")
PY

echo
echo "== 4) Wait for certificate validation =="
aws acm wait certificate-validated --region "${CERT_REGION}" --certificate-arn "${CERT_ARN}"
echo "Certificate validated."

echo
echo "== 5) Create CloudFront Origin Access Control (OAC) =="
OAC_NAME="nektron-ai-site-oac"
EXISTING_OAC_ID="$(aws cloudfront list-origin-access-controls --query "OriginAccessControlList.Items[?Name=='${OAC_NAME}'].Id | [0]" --output text)"

if [[ -n "${EXISTING_OAC_ID}" && "${EXISTING_OAC_ID}" != "None" ]]; then
  OAC_ID="${EXISTING_OAC_ID}"
  echo "Found existing OAC: ${OAC_ID}"
else
  OAC_ID="$(aws cloudfront create-origin-access-control \
    --origin-access-control-config "{
      \"Name\":\"${OAC_NAME}\",
      \"Description\":\"OAC for nektron.ai static site\",
      \"SigningProtocol\":\"sigv4\",
      \"SigningBehavior\":\"always\",
      \"OriginAccessControlOriginType\":\"s3\"
    }" \
    --query 'OriginAccessControl.Id' \
    --output text)"
fi

echo "OAC ID: ${OAC_ID}"

echo
echo "== 6) Create CloudFront distribution =="

ORIGIN_DOMAIN="${BUCKET_NAME}.s3.${BUCKET_REGION}.amazonaws.com"
CALLER_REF="$(date +%s)"

EXISTING_DIST_ROW="$(aws cloudfront list-distributions --query "DistributionList.Items[?Aliases.Items && contains(Aliases.Items, '${DOMAIN}')].[Id,DomainName] | [0]" --output text)"
EXISTING_DIST_ID="$(echo "${EXISTING_DIST_ROW}" | awk '{print $1}')"
EXISTING_DIST_DOMAIN="$(echo "${EXISTING_DIST_ROW}" | awk '{print $2}')"

if [[ -n "${EXISTING_DIST_ID}" && "${EXISTING_DIST_ID}" != "None" ]]; then
  DIST_ID="${EXISTING_DIST_ID}"
  DIST_DOMAIN="${EXISTING_DIST_DOMAIN}"
  echo "Found existing distribution: ${DIST_ID}"
else
  DIST_CONFIG_FILE="$(mktemp)"
  cat > "${DIST_CONFIG_FILE}" <<JSON
{
  "CallerReference": "${CALLER_REF}",
  "Comment": "NektronAI static website",
  "Enabled": true,
  "Aliases": {
    "Quantity": 2,
    "Items": ["${DOMAIN}", "${WWW_DOMAIN}"]
  },
  "DefaultRootObject": "index.html",
  "PriceClass": "PriceClass_100",
  "Origins": {
    "Quantity": 1,
    "Items": [
      {
        "Id": "S3-${BUCKET_NAME}",
        "DomainName": "${ORIGIN_DOMAIN}",
        "OriginAccessControlId": "${OAC_ID}",
        "S3OriginConfig": { "OriginAccessIdentity": "" }
      }
    ]
  },
  "DefaultCacheBehavior": {
    "TargetOriginId": "S3-${BUCKET_NAME}",
    "ViewerProtocolPolicy": "redirect-to-https",
    "AllowedMethods": { "Quantity": 2, "Items": ["GET","HEAD"], "CachedMethods": { "Quantity": 2, "Items": ["GET","HEAD"] } },
    "Compress": true,
    "CachePolicyId": "658327ea-f89d-4fab-a63d-7e88639e58f6"
  },
  "ViewerCertificate": {
    "ACMCertificateArn": "${CERT_ARN}",
    "SSLSupportMethod": "sni-only",
    "MinimumProtocolVersion": "TLSv1.2_2021"
  },
  "HttpVersion": "http2"
}
JSON

  DIST_JSON="$(aws cloudfront create-distribution --distribution-config "file://${DIST_CONFIG_FILE}")"
  DIST_ID="$(python3 -c 'import json,sys; print(json.loads(sys.stdin.read())["Distribution"]["Id"])' <<<"${DIST_JSON}")"
  DIST_DOMAIN="$(python3 -c 'import json,sys; print(json.loads(sys.stdin.read())["Distribution"]["DomainName"])' <<<"${DIST_JSON}")"
fi

echo "Distribution ID: ${DIST_ID}"
echo "Distribution Domain: ${DIST_DOMAIN}"

echo
echo "== 7) Apply S3 bucket policy for CloudFront OAC =="
DIST_ARN="arn:aws:cloudfront::${ACCOUNT_ID}:distribution/${DIST_ID}"

POLICY_FILE="$(mktemp)"
cat > "${POLICY_FILE}" <<JSON
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowCloudFrontReadOnly",
      "Effect": "Allow",
      "Principal": { "Service": "cloudfront.amazonaws.com" },
      "Action": ["s3:GetObject"],
      "Resource": "arn:aws:s3:::${BUCKET_NAME}/*",
      "Condition": { "StringEquals": { "AWS:SourceArn": "${DIST_ARN}" } }
    }
  ]
}
JSON

aws s3api put-bucket-policy --bucket "${BUCKET_NAME}" --policy "file://${POLICY_FILE}"
echo "Bucket policy applied."

echo
echo "== 8) Create Route 53 alias records for nektron.ai and www =="
python3 - "${HOSTED_ZONE_ID}" "${DIST_DOMAIN}" "${DOMAIN}" "${WWW_DOMAIN}" <<'PY'
import json, subprocess, sys

HOSTED_ZONE_ID=sys.argv[1]
DIST_DOMAIN=sys.argv[2]
DOMAIN=sys.argv[3]
WWW_DOMAIN=sys.argv[4]

CF_ZONE_ID="Z2FDTNDATAQYW2"

def alias_change(name, rrtype):
  return {
    "Action":"UPSERT",
    "ResourceRecordSet":{
      "Name": name,
      "Type": rrtype,
      "AliasTarget":{
        "HostedZoneId": CF_ZONE_ID,
        "DNSName": DIST_DOMAIN,
        "EvaluateTargetHealth": False
      }
    }
  }

changes = [
  alias_change(DOMAIN, "A"),
  alias_change(DOMAIN, "AAAA"),
  alias_change(WWW_DOMAIN, "A"),
  alias_change(WWW_DOMAIN, "AAAA"),
]

batch = {"Comment":"NektronAI website CloudFront aliases","Changes":changes}
subprocess.check_call([
  "aws","route53","change-resource-record-sets",
  "--hosted-zone-id",HOSTED_ZONE_ID,
  "--change-batch", json.dumps(batch)
])
print("Alias records UPSERTed.")
PY

echo
echo "== Done =="
echo "Bucket: ${BUCKET_NAME}"
echo "CloudFront: ${DIST_DOMAIN}"
echo "Site URLs:"
echo "  https://${DOMAIN}"
echo "  https://${WWW_DOMAIN}"
echo
echo "Next: run ./deploy.sh"
