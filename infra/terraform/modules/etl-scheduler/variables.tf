variable "name_prefix" {
  type        = string
  description = "Resource name prefix."
}

variable "environment" {
  type        = string
  description = "Environment label."
}

variable "github_org" {
  type        = string
  description = "GitHub organization or user that owns the repository."
}

variable "github_repo" {
  type        = string
  description = "Repository name (without org)."
}

variable "github_workflow_file" {
  type        = string
  default     = "etl.yml"
  description = "Workflow file name in .github/workflows/."
}

variable "github_ref" {
  type        = string
  default     = "main"
  description = "Git ref passed to workflow_dispatch."
}

variable "github_dispatch_token" {
  type        = string
  sensitive   = true
  description = "GitHub PAT with actions:write on the repo (stored in Secrets Manager)."
}

variable "schedule_expression" {
  type        = string
  default     = "cron(0/15 * * * ? *)"
  description = "EventBridge schedule expression (every 15 min on the clock by default)."
}

variable "tags" {
  type        = map(string)
  default     = {}
  description = "Tags applied to created resources."
}
