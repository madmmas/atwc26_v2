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

variable "s3_bucket_name" {
  type        = string
  description = "S3 bucket containing published data/schedule.json."
}

variable "dynamodb_table_name" {
  type        = string
  description = "DynamoDB table for ETL trigger deduplication records."
}

variable "schedule_s3_key" {
  type        = string
  default     = "data/schedule.json"
  description = "S3 object key for schedule.json."
}

variable "schedule_expression" {
  type        = string
  default     = "cron(*/5 * * * ? *)"
  description = "UTC-aligned checker cadence (every 5 minutes on the clock)."
}

variable "match_duration_minutes" {
  type        = number
  default     = 105
  description = "Estimated match length from kickoff (90 min + stoppage/halftime)."
}

variable "trigger_offsets_minutes" {
  type        = list(number)
  default     = [0, 15, 30, 45, 60, 75, 90, 105, 120, 135, 150, 165, 180, 195, 210, 225]
  description = "Minutes after kickoff+match_duration to dispatch ETL (16 runs, 15 min apart, 4h window)."
}

variable "trigger_catchup_minutes" {
  type        = number
  default     = 15
  description = "Window after each trigger time to still fire if a poll was missed."
}

variable "tags" {
  type        = map(string)
  default     = {}
  description = "Tags applied to created resources."
}
