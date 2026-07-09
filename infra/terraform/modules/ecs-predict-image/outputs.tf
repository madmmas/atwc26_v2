output "image_tag" {
  description = "Content-hash image tag pushed to ECR."
  value       = local.image_tag
}

output "image_uri" {
  description = "Full ECR image URI used by the ECS task definition."
  value       = local.image_uri
}

output "image_build_id" {
  description = "Changes when the ECR image is (re)built; wire into ECS task definition to order apply after push."
  value       = var.enabled ? terraform_data.predict_ecr_image[0].id : null
}
