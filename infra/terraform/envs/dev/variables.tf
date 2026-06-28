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
