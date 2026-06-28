variable "name_prefix" {
  description = "Prefix for AWS resource names (e.g. atwc26-v2)."
  type        = string
}

variable "environment" {
  description = "Environment label (e.g. dev, prod)."
  type        = string
  default     = "dev"
}

variable "tags" {
  description = "Tags applied to all resources."
  type        = map(string)
  default     = {}
}

variable "aliases" {
  description = "Optional custom domain names for CloudFront (requires acm_certificate_arn)."
  type        = list(string)
  default     = []
}

variable "acm_certificate_arn" {
  description = "ACM certificate ARN in us-east-1 for custom CloudFront domains (optional)."
  type        = string
  default     = null
}

variable "price_class" {
  description = "CloudFront price class."
  type        = string
  default     = "PriceClass_100"
}

variable "backend_api_url" {
  description = "v1 backend URL the static bundle calls (documentation/output only; baked at build time)."
  type        = string
  default     = "https://atwc26.com"
}
