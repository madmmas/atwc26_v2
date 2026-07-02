output "bucket_name" {
  description = "S3 bucket for static frontend assets."
  value       = aws_s3_bucket.site.id
}

output "bucket_arn" {
  description = "S3 bucket ARN."
  value       = aws_s3_bucket.site.arn
}

output "cloudfront_distribution_id" {
  description = "CloudFront distribution ID (for deploy invalidation)."
  value       = aws_cloudfront_distribution.site.id
}

output "cloudfront_domain_name" {
  description = "CloudFront domain (https://<this>) — add to v1 backend CORS origins."
  value       = aws_cloudfront_distribution.site.domain_name
}

output "cloudfront_url" {
  description = "HTTPS URL for the static site (+ /api/* when API origin is wired)."
  value       = "https://${aws_cloudfront_distribution.site.domain_name}"
}

output "site_url" {
  description = "Unified CloudFront URL for frontend and /api/* (when API origin is set)."
  value       = "https://${aws_cloudfront_distribution.site.domain_name}"
}

output "backend_api_url" {
  description = "v1 API the frontend bundle should target (set NEXT_PUBLIC_API_URL at build time)."
  value       = var.backend_api_url
}

output "cors_origin_hint" {
  description = "Add this origin to ATWC26_CORS_ORIGINS on the v1 backend."
  value       = "https://${aws_cloudfront_distribution.site.domain_name}"
}
