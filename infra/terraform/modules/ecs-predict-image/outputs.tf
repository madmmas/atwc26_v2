output "image_tag" {
  description = "Content-hash image tag pushed to ECR."
  value       = local.image_tag
}

output "image_uri" {
  description = "Full ECR image URI used by the ECS task definition."
  value       = local.image_uri
}
