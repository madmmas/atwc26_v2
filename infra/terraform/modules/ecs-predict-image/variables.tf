variable "enabled" {
  description = "Build and push the predict ECS image when true."
  type        = bool
  default     = true
}

variable "ecr_repository_url" {
  description = "ECR repository URL without image tag."
  type        = string
}

variable "repo_root" {
  description = "Repository root (Docker build context)."
  type        = string
}

variable "aws_region" {
  description = "AWS region for ECR login."
  type        = string
}

variable "build_script" {
  description = "Path to build_push_predict_ecs.sh."
  type        = string
}
