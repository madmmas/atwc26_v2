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

variable "analytics_invoke_arn" { type = string }
variable "predict_invoke_arn" { type = string }
variable "analytics_function_name" { type = string }
variable "predict_function_name" { type = string }

variable "enable_ecs_compute" {
  description = "Route POST /api/predict to ECS via ALB; false uses predict Lambda."
  type        = bool
  default     = false
}

variable "compute_listener_arn" {
  description = "ALB listener ARN for ECS compute routes; required when enable_ecs_compute=true."
  type        = string
  default     = null
}

variable "cors_allow_origins" {
  type    = list(string)
  default = ["*"]
}
