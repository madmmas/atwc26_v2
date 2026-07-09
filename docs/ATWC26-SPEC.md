# Spec: Custom Domain HTTPS for atwc26.com on CloudFront (Terraform)

## Goal
`https://atwc26.com` must serve the existing CloudFront distribution
(`d3brosganz3u2u.cloudfront.net`) with a valid TLS certificate, replacing the
current plain A record (`100.50.112.9`). Managed entirely via Terraform.

## Assumptions
- Route53 hosted zone `atwc26.com` already exists (zone ID `Z04095901F8UBN9TKKM13`).
  Reference it via `data "aws_route53_zone"`, don't hardcode the ID if avoidable.
- The CloudFront distribution already exists. State one of:
  - [ ] It is already a `aws_cloudfront_distribution` resource in this Terraform config → modify in place.
  - [ ] It was created out-of-band (console) → must `terraform import` it first, or this spec only manages the cert + DNS and the CNAME/cert gets attached manually as a stopgap.
  (Default this spec to: **already managed in Terraform**, resource name `aws_cloudfront_distribution.site`.)
- ACM certificates for CloudFront **must** be issued in `us-east-1`, regardless of where the rest of the infra lives. Requires a second `aws` provider alias if the main provider targets another region.
- DNS validation for ACM is done via Route53 (not email validation).
- Apex + `www` both need to resolve — confirm whether `www.atwc26.com` should alias to CloudFront too or stay as-is.

## Resources to add/modify

### 1. Provider alias for us-east-1
```hcl
provider "aws" {
  alias  = "us_east_1"
  region = "us-east-1"
}
```

### 2. Hosted zone data source
```hcl
data "aws_route53_zone" "atwc26" {
  name         = "atwc26.com"
  private_zone = false
}
```

### 3. ACM certificate (us-east-1)
```hcl
resource "aws_acm_certificate" "atwc26" {
  provider                  = aws.us_east_1
  domain_name               = "atwc26.com"
  subject_alternative_names = ["www.atwc26.com"]
  validation_method          = "DNS"

  lifecycle {
    create_before_destroy = true
  }
}
```

### 4. DNS validation records
```hcl
resource "aws_route53_record" "atwc26_cert_validation" {
  for_each = {
    for dvo in aws_acm_certificate.atwc26.domain_validation_options : dvo.domain_name => {
      name   = dvo.resource_record_name
      type   = dvo.resource_record_type
      record = dvo.resource_record_value
    }
  }

  zone_id = data.aws_route53_zone.atwc26.zone_id
  name    = each.value.name
  type    = each.value.type
  records = [each.value.record]
  ttl     = 60
}
```

### 5. Certificate validation (waits for ACM to mark it Issued)
```hcl
resource "aws_acm_certificate_validation" "atwc26" {
  provider                = aws.us_east_1
  certificate_arn         = aws_acm_certificate.atwc26.arn
  validation_record_fqdns = [for r in aws_route53_record.atwc26_cert_validation : r.fqdn]
}
```

### 6. CloudFront distribution changes
Add/update on the existing `aws_cloudfront_distribution.site` resource:
```hcl
resource "aws_cloudfront_distribution" "site" {
  # ...existing config (origins, default_cache_behavior, etc.)...

  aliases = ["atwc26.com", "www.atwc26.com"]

  viewer_certificate {
    acm_certificate_arn      = aws_acm_certificate_validation.atwc26.certificate_arn
    ssl_support_method       = "sni-only"
    minimum_protocol_version = "TLSv1.2_2021"
  }
}
```
Note: `aliases` was likely empty/default before — this is the field that was
missing, causing CloudFront to fall back to its default `*.cloudfront.net`
cert and reject `atwc26.com` requests.

### 7. Route53 alias records (replace the existing A records)
```hcl
resource "aws_route53_record" "atwc26_apex" {
  zone_id = data.aws_route53_zone.atwc26.zone_id
  name    = "atwc26.com"
  type    = "A"

  alias {
    name                   = aws_cloudfront_distribution.site.domain_name
    zone_id                = aws_cloudfront_distribution.site.hosted_zone_id
    evaluate_target_health = false
  }
}

resource "aws_route53_record" "atwc26_www" {
  zone_id = data.aws_route53_zone.atwc26.zone_id
  name    = "www.atwc26.com"
  type    = "A"

  alias {
    name                   = aws_cloudfront_distribution.site.domain_name
    zone_id                = aws_cloudfront_distribution.site.hosted_zone_id
    evaluate_target_health = false
  }
}
```
`aws_cloudfront_distribution.hosted_zone_id` is always the fixed CloudFront
zone ID (`Z2FDTNDATAQYW2`), Terraform fills it in automatically — don't hardcode it.

**Important:** these `aws_route53_record` resources will conflict with any
existing manually-created A records of the same name/type. Either:
- Import the existing records first (`terraform import aws_route53_record.atwc26_apex Z04095901F8UBN9TKKM13_atwc26.com_A`), or
- Delete them manually in the console before first `apply`, or
- Terraform will error with "record already exists" on `apply`.

## Suggested file layout
```
dns.tf          → hosted zone data source, alias records
acm.tf          → certificate, validation records, validation resource
cloudfront.tf   → existing distribution + new aliases/viewer_certificate block
providers.tf    → us_east_1 provider alias
```

## Apply order (handled automatically by Terraform's dependency graph, but for review)
1. `aws_acm_certificate.atwc26` created (status: pending validation)
2. `aws_route53_record.atwc26_cert_validation.*` created
3. `aws_acm_certificate_validation.atwc26` waits until ACM shows Issued (can take a few minutes)
4. `aws_cloudfront_distribution.site` updated with `aliases` + `viewer_certificate` (CloudFront deploy takes 5–15 min)
5. `aws_route53_record.atwc26_apex` / `atwc26_www` created, replacing old A records

## Verification after apply
- `dig atwc26.com` → CNAME/ALIAS resolves through CloudFront, not `100.50.112.9`.
- `curl -vI https://atwc26.com` → cert subject should show `atwc26.com`, not `*.cloudfront.net`.
- Load in Firefox — HSTS error should be gone since the cert now matches.
- `aws acm describe-certificate --certificate-arn <arn> --region us-east-1` → status `ISSUED`.

## Rollback
Revert `aliases` to `[]` and `viewer_certificate` to CloudFront default
(`cloudfront_default_certificate = true`) on the distribution, and change the
apex A record back to the static IP alias. Cert and validation records can be
left in place or destroyed independently — they don't affect traffic once
detached from the distribution.
