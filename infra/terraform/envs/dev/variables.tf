variable "aws_region" {
  description = "AWS region for S3 (CloudFront is global)."
  type        = string
  default     = "us-east-1"
}

variable "name_prefix" {
  description = "Resource name prefix (candidate stack, separate from production v1)."
  type        = string
  default     = "atwc26-v2"
}

variable "environment" {
  description = "Environment label."
  type        = string
  default     = "dev"
}

variable "backend_api_url" {
  description = "v1 monolith API URL baked into the static frontend at build time."
  type        = string
  default     = "https://atwc26.com"
}

variable "aliases" {
  description = "Optional custom domain names (requires acm_certificate_arn in us-east-1)."
  type        = list(string)
  default     = []
}

variable "acm_certificate_arn" {
  description = "ACM certificate ARN in us-east-1 for custom CloudFront domains."
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
  default     = ["*"]
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

variable "ecs_container_image" {
  description = "ECR image URI for ECS compute service (required when enable_ecs_compute=true)."
  type        = string
  default     = ""
}

variable "enable_github_oidc" {
  description = "Create GitHub Actions OIDC IAM role for CI/CD (set ATWC26_AWS_ROLE_ARN in GHA)."
  type        = bool
  default     = false
}

variable "github_org" {
  description = "GitHub org/user for OIDC trust policy."
  type        = string
  default     = "neunov"
}

variable "github_repo" {
  description = "GitHub repository name for OIDC trust policy."
  type        = string
  default     = "AnalyseThisWC26"
}
