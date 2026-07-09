locals {
  predict_api_files = fileset("${var.repo_root}/services/predict_api", "**")
  shared_files      = fileset("${var.repo_root}/services/shared", "**")
  core_files        = fileset("${var.repo_root}/packages/atwc26_core/atwc26_core", "**")

  predict_content_hash = sha256(join("", concat(
    [filesha256("${var.repo_root}/services/predict_api/Dockerfile")],
    [filesha256("${var.repo_root}/services/predict_api/requirements.txt")],
    [for f in sort(local.predict_api_files) : filesha256("${var.repo_root}/services/predict_api/${f}")],
    [for f in sort(local.shared_files) : filesha256("${var.repo_root}/services/shared/${f}")],
    [for f in sort(local.core_files) : filesha256("${var.repo_root}/packages/atwc26_core/atwc26_core/${f}")],
  )))

  image_tag = substr(local.predict_content_hash, 0, 12)
  image_uri = "${var.ecr_repository_url}:${local.image_tag}"
}

resource "terraform_data" "predict_ecr_image" {
  count = var.enabled ? 1 : 0

  triggers_replace = [
    local.predict_content_hash,
    var.ecr_repository_url,
    var.aws_region,
    filesha256(var.build_script),
  ]

  provisioner "local-exec" {
    command     = var.build_script
    working_dir = var.repo_root
    environment = {
      ECR_REPOSITORY_URL = var.ecr_repository_url
      IMAGE_TAG          = local.image_tag
      AWS_REGION         = var.aws_region
    }
  }
}
