output "zone_id" {
  description = "Route53 hosted zone ID for the domain."
  value       = data.aws_route53_zone.this.zone_id
}

output "zone_name" {
  description = "Route53 hosted zone name."
  value       = data.aws_route53_zone.this.name
}

output "certificate_arn" {
  description = "Issued ACM certificate ARN (us-east-1) for CloudFront."
  value       = aws_acm_certificate_validation.this.certificate_arn
}

output "certificate_domain_name" {
  description = "Primary domain on the certificate."
  value       = aws_acm_certificate.this.domain_name
}
