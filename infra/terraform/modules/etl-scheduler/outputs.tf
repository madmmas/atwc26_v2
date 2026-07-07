output "schedule_rule_arn" {
  value       = aws_cloudwatch_event_rule.etl_schedule.arn
  description = "EventBridge rule ARN for the 15-minute ETL schedule."
}

output "schedule_rule_name" {
  value       = aws_cloudwatch_event_rule.etl_schedule.name
  description = "EventBridge rule name."
}

output "dispatch_lambda_name" {
  value       = aws_lambda_function.dispatch.function_name
  description = "Lambda that calls GitHub workflow_dispatch."
}

output "github_dispatch_secret_arn" {
  value       = aws_secretsmanager_secret.github_dispatch.arn
  description = "Secrets Manager ARN for the GitHub dispatch PAT."
}
