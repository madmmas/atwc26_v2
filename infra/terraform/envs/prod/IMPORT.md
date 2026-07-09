# Prod environment — Route53 import guide

Use these commands when existing Route53 records would conflict with Terraform
on first apply. Run from `infra/terraform/envs/prod` after `terraform init`.

## Zone ID

The hosted zone is looked up by name (`atwc26.com`), not hardcoded. To confirm:

```bash
terraform console
> data.aws_route53_zone.atwc26[0].zone_id
```

Or:

```bash
aws route53 list-hosted-zones-by-name --dns-name atwc26.com --query 'HostedZones[0].Id' --output text
```

Expected zone ID (from spec): `Z04095901F8UBN9TKKM13`

## Import existing apex / www A records

If `atwc26.com` and `www.atwc26.com` already have A records (e.g. pointing at
`100.50.112.9`), import them before apply so Terraform updates them to CloudFront
aliases instead of erroring with "record already exists".

```bash
ZONE_ID="Z04095901F8UBN9TKKM13"

terraform import 'aws_route53_record.cloudfront_alias["atwc26.com"]' \
  "${ZONE_ID}_atwc26.com_A"

terraform import 'aws_route53_record.cloudfront_alias["www.atwc26.com"]' \
  "${ZONE_ID}_www.atwc26.com_A"
```

IPv6 (AAAA) records are new — no import needed unless they already exist:

```bash
terraform import 'aws_route53_record.cloudfront_alias_ipv6["atwc26.com"]' \
  "${ZONE_ID}_atwc26.com_AAAA"

terraform import 'aws_route53_record.cloudfront_alias_ipv6["www.atwc26.com"]' \
  "${ZONE_ID}_www.atwc26.com_AAAA"
```

## Skip DNS management temporarily

Set in `terraform.tfvars`:

```hcl
manage_dns_alias_records = false
```

ACM + CloudFront aliases still apply; you manage apex/www records manually.

## Apply order

1. ACM certificate created (pending validation)
2. Route53 validation CNAMEs created automatically
3. `aws_acm_certificate_validation` waits until Issued (~few minutes)
4. CloudFront updated with aliases + custom cert (~5–15 min)
5. Route53 apex/www alias records point at CloudFront

## Verify

```bash
dig atwc26.com +short
curl -vI https://atwc26.com/api/health
terraform output site_url
```

Cert subject should be `atwc26.com`, not `*.cloudfront.net`.

## Rollback

Set `manage_dns_alias_records = false`, revert apex A record to the previous IP
in the console, and remove `aliases` / restore default cert on CloudFront via
`enable_custom_domain = false` + `terraform apply`.
