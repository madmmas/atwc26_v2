variable "aws_region" {
  description = "AWS region for S3 (CloudFront is global)."
  type        = string
  default     = "us-east-1"
}

variable "name_prefix" {
  description = "Resource name prefix."
  type        = string
  default     = "atwc26-v2"
}

variable "environment" {
  description = "Environment label."
  type        = string
  default     = "prod"
}

variable "backend_api_url" {
  description = "API URL baked into the static frontend at build time (same-origin after DNS cutover)."
  type        = string
  default     = "https://atwc26.com"
}

variable "enable_custom_domain" {
  description = "Issue ACM cert via Route53 DNS validation and attach atwc26.com to CloudFront."
  type        = bool
  default     = true
}

variable "domain_zone_name" {
  description = "Route53 public hosted zone name."
  type        = string
  default     = "atwc26.com"
}

variable "domain_name" {
  description = "Primary custom domain for CloudFront."
  type        = string
  default     = "atwc26.com"
}

variable "domain_subject_alternative_names" {
  description = "Additional custom domains (SANs on the ACM certificate)."
  type        = list(string)
  default     = ["www.atwc26.com"]
}

variable "manage_dns_alias_records" {
  description = "Create Route53 A alias records for apex + SANs pointing at CloudFront."
  type        = bool
  default     = true
}

# Fallback when enable_custom_domain=false: supply an external ACM ARN and aliases manually.
variable "aliases" {
  description = "Custom domain names (used only when enable_custom_domain=false)."
  type        = list(string)
  default     = []
}

variable "acm_certificate_arn" {
  description = "External ACM certificate ARN (used only when enable_custom_domain=false)."
  type        = string
  default     = null
}

variable "data_s3_prefix" {
  description = "S3 key prefix for ETL-published data artifacts."
  type        = string
  default     = "data"
}

variable "cors_allow_origins" {
  description = "CORS origins for API Gateway and Lambda services."
  type        = list(string)
  default     = ["https://atwc26.com", "https://www.atwc26.com"]
}

variable "lambda_package_dir" {
  description = "Optional override for Lambda zip directory (default: infra/build/lambdas)."
  type        = string
  default     = ""
}

variable "enable_ecs_compute" {
  description = "Run POST /api/predict on ECS/Fargate instead of predict Lambda."
  type        = bool
  default     = false
}

variable "build_ecs_image" {
  description = "When enable_ecs_compute=true, docker build + push predict image to ECR during terraform apply."
  type        = bool
  default     = true
}

variable "ecs_container_image" {
  description = "ECR image URI for ECS compute service (required when enable_ecs_compute=true)."
  type        = string
  default     = ""
}

variable "enable_github_oidc" {
  description = "Create GitHub Actions OIDC IAM role for CI/CD."
  type        = bool
  default     = true
}

variable "github_org" {
  description = "GitHub org/user for OIDC trust policy."
  type        = string
  default     = "madmmas"
}

variable "github_repo" {
  description = "GitHub repository name for OIDC trust policy."
  type        = string
  default     = "atwc26_v2"
}

variable "enable_etl_scheduler" {
  description = "EventBridge match-based checker → Lambda → GitHub workflow_dispatch for ETL."
  type        = bool
  default     = false
}

variable "github_dispatch_token" {
  description = "GitHub PAT with actions:write (required when enable_etl_scheduler=true). Set via TF_VAR_github_dispatch_token."
  type        = string
  sensitive   = true
  default     = ""
}
