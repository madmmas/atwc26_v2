output "role_arn" {
  value       = aws_iam_role.github_actions.arn
  description = "IAM role ARN for GitHub Actions (set as ATWC26_AWS_ROLE_ARN secret)."
}

output "oidc_provider_arn" {
  value       = aws_iam_openid_connect_provider.github.arn
  description = "GitHub OIDC provider ARN."
}
