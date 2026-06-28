output "bucket_name" {
  value       = module.frontend_cdn.bucket_name
  description = "Pass to ATWC26_FRONTEND_BUCKET for deploy_frontend.sh"
}

output "cloudfront_distribution_id" {
  value       = module.frontend_cdn.cloudfront_distribution_id
  description = "Pass to ATWC26_CLOUDFRONT_DISTRIBUTION_ID for deploy_frontend.sh"
}

output "cloudfront_url" {
  value       = module.frontend_cdn.cloudfront_url
  description = "Candidate static frontend URL"
}

output "cors_origin_hint" {
  value       = module.frontend_cdn.cors_origin_hint
  description = "Add to ATWC26_CORS_ORIGINS on the v1 backend"
}

output "backend_api_url" {
  value       = module.frontend_cdn.backend_api_url
  description = "Use as NEXT_PUBLIC_API_URL when running build_frontend_static.sh"
}
