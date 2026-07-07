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
  description = "Unified CloudFront URL (static + /api/*)"
}

output "site_url" {
  value       = module.frontend_cdn.site_url
  description = "Same as cloudfront_url — use for static build NEXT_PUBLIC_* when routing via CDN"
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

output "ecs_cluster_name" {
  value       = var.enable_ecs_compute ? module.ecs_compute[0].cluster_name : null
  description = "ECS cluster for compute routes (when enable_ecs_compute=true)"
}

output "ecs_service_name" {
  value       = var.enable_ecs_compute ? module.ecs_compute[0].service_name : null
  description = "ECS service to pass to ATWC26_ECS_SERVICES after publish"
}

output "compute_alb_dns" {
  value       = var.enable_ecs_compute ? module.ecs_compute[0].alb_dns_name : null
  description = "Public ALB for ECS compute (debug only; use API Gateway/CloudFront in prod)"
}

output "github_actions_role_arn" {
  value       = var.enable_github_oidc ? module.github_oidc[0].role_arn : null
  description = "Set as ATWC26_AWS_ROLE_ARN GitHub secret for OIDC auth"
}

output "etl_schedule_rule_name" {
  value       = var.enable_etl_scheduler ? module.etl_scheduler[0].schedule_rule_name : null
  description = "EventBridge rule that triggers ETL every 15 minutes"
}

output "etl_dispatch_lambda_name" {
  value       = var.enable_etl_scheduler ? module.etl_scheduler[0].dispatch_lambda_name : null
  description = "Lambda that dispatches the GitHub ETL workflow"
}
