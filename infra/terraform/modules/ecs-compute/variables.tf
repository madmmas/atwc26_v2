variable "name_prefix" {
  type = string
}

variable "environment" {
  type = string
}

variable "tags" {
  type    = map(string)
  default = {}
}

variable "container_image" {
  description = "ECR image URI for the predict/compute service."
  type        = string
}

variable "s3_bucket_name" {
  type = string
}

variable "dynamodb_table_name" {
  type = string
}

variable "s3_prefix" {
  type    = string
  default = "data"
}

variable "cors_origins" {
  type    = string
  default = "*"
}

variable "cpu" {
  type    = number
  default = 512
}

variable "memory" {
  type    = number
  default = 1024
}

variable "desired_count" {
  type    = number
  default = 1
}

variable "aws_region" {
  type = string
}

variable "vpc_id" {
  description = "VPC for ALB, target group, and ECS task networking."
  type        = string
}

variable "subnet_ids" {
  description = "Subnets for ALB and Fargate tasks (must span AZs used by the ALB)."
  type        = list(string)
}

variable "image_build_id" {
  description = "Optional token from ecs-predict-image; ties task definition updates to post-build apply order."
  type        = string
  default     = ""
}
