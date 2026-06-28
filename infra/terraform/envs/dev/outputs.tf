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
  description = "Legacy v1 monolith URL (use api_gateway_url for v2 split APIs)"
}

output "api_gateway_url" {
  value       = module.api_gateway.api_endpoint
  description = "v2 HTTP API base URL (analytics + predict routes)"
}

output "analytics_api_url" {
  value       = module.api_gateway.api_endpoint
  description = "Use as NEXT_PUBLIC_ANALYTICS_API_URL at static build time"
}

output "predict_api_url" {
  value       = module.api_gateway.api_endpoint
  description = "Use as NEXT_PUBLIC_PREDICT_API_URL at static build time"
}

output "data_bucket_name" {
  value       = module.s3_data.bucket_name
  description = "S3 bucket for ETL-published parquet/JSON artifacts"
}

output "dynamodb_table_name" {
  value       = module.dynamodb.table_name
  description = "DynamoDB manifest table for published data"
}

output "lambda_analytics_name" {
  value = module.lambda_analytics.function_name
}

output "lambda_predict_name" {
  value = module.lambda_predict.function_name
}
