terraform {
  required_version = ">= 1.5.0"

  # Optional remote state for CI deploy (configure via backend.hcl or -backend-config).
  # Local validate-only: terraform init -backend=false
  backend "s3" {}

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = ">= 3.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = ">= 2.0"
    }
  }
}
