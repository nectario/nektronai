# NektronAI Website (nektron.ai)

Static marketing site for NektronAI (DBA of Nektron, Inc.), hosted on AWS:

- S3 (private bucket)
- CloudFront (TLS + custom domain)
- ACM certificate (must be in us-east-1 for CloudFront)
- Route 53 (A/AAAA alias records)

This setup is designed to **not** disturb existing email DNS records (MX/SPF/DMARC/DKIM).

## Structure

- `site/` static files (`index.html`, `privacy.html`, `terms.html`, `support.html`)
- `infra/` AWS CLI scripts:
  - `create_infra.sh` creates bucket + cert + CloudFront + Route 53 records
  - `deploy.sh` uploads site files and invalidates CloudFront

## Prereqs

- AWS CLI v2 configured for the correct account
- Permission to manage: S3, CloudFront, ACM, Route 53

## One-time infra creation

```bash
cd infra
./create_infra.sh
```

Notes:
- Certificate issuance can take several minutes; the script waits for DNS validation.
- The script UPSERTs only:
  - ACM validation CNAMEs
  - `A`/`AAAA` alias for `nektron.ai` and `www.nektron.ai`

## Deploy site content

```bash
cd infra
./deploy.sh
```

## Apple URLs

- https://nektron.ai/privacy.html
- https://nektron.ai/terms.html
- https://nektron.ai/support.html

