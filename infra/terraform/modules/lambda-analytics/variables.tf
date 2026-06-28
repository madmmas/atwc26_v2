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

variable "lambda_layer_arn" {
  type    = string
  default = null
}

variable "package_path" {
  description = "Path to analytics.zip from infra/scripts/package_lambdas.sh"
  type        = string
  default     = ""
}

variable "memory_size" {
  type    = number
  default = 1536
}

variable "timeout" {
  type    = number
  default = 60
}
