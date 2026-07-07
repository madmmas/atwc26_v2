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
