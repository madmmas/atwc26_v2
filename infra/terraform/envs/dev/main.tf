provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = var.name_prefix
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

module "frontend_cdn" {
  source = "../../modules/frontend-cdn"

  name_prefix         = var.name_prefix
  environment         = var.environment
  backend_api_url     = var.backend_api_url
  aliases             = var.aliases
  acm_certificate_arn = var.acm_certificate_arn
}
