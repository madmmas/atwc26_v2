provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = var.name_prefix
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

locals {
  tags = {
    Project     = var.name_prefix
    Environment = var.environment
  }

  predict_ecr_name    = "${var.name_prefix}-${var.environment}-predict"
  ecr_predict_url     = aws_ecr_repository.predict.repository_url
  repo_root           = abspath("${path.module}/../../../..")
  ecs_build_script    = abspath("${path.module}/../../../scripts/build_push_predict_ecs.sh")
  ecs_container_image = var.ecs_container_image != "" ? var.ecs_container_image : (
    var.enable_ecs_compute && var.build_ecs_image ? module.ecs_predict_image[0].image_uri : "${local.ecr_predict_url}:latest"
  )

  lambda_build_dir = abspath("${path.module}/../../../build/lambdas")
  layer_zip        = "${local.lambda_build_dir}/layer.zip"
  analytics_zip    = "${local.lambda_build_dir}/analytics.zip"
  predict_zip      = "${local.lambda_build_dir}/predict.zip"
  has_lambda_zips  = fileexists(local.analytics_zip) && fileexists(local.predict_zip) && fileexists(local.layer_zip)
  layer_zip_sha256 = local.has_lambda_zips ? filebase64sha256(local.layer_zip) : ""
  layer_zip_md5    = local.has_lambda_zips ? filemd5(local.layer_zip) : ""
}

module "s3_data" {
  source = "../../modules/s3-data"

  name_prefix = var.name_prefix
  environment = var.environment
  tags        = local.tags
}

module "dynamodb" {
  source = "../../modules/dynamodb"

  name_prefix = var.name_prefix
  environment = var.environment
  tags        = local.tags
}

resource "aws_ecr_repository" "predict" {
  name                 = local.predict_ecr_name
  image_tag_mutability = "MUTABLE"
  force_delete         = true

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = local.tags
}

resource "aws_s3_object" "lambda_layer" {
  count = local.has_lambda_zips ? 1 : 0

  bucket = module.s3_data.bucket_name
  key    = "lambda/layer-${local.layer_zip_sha256}.zip"
  source = local.layer_zip
  etag   = local.layer_zip_md5
}

resource "aws_lambda_layer_version" "core" {
  count = local.has_lambda_zips ? 1 : 0

  layer_name               = "${var.name_prefix}-${var.environment}-core"
  s3_bucket                = aws_s3_object.lambda_layer[0].bucket
  s3_key                   = aws_s3_object.lambda_layer[0].key
  compatible_runtimes      = ["python3.11"]
  compatible_architectures = ["arm64"]

  depends_on = [aws_s3_object.lambda_layer]
}

module "lambda_analytics" {
  source = "../../modules/lambda-analytics"

  name_prefix         = var.name_prefix
  environment         = var.environment
  tags                = local.tags
  s3_bucket_name      = module.s3_data.bucket_name
  dynamodb_table_name = module.dynamodb.table_name
  s3_prefix           = var.data_s3_prefix
  cors_origins        = join(",", var.cors_allow_origins)
  lambda_layer_arn    = local.has_lambda_zips ? aws_lambda_layer_version.core[0].arn : null
  package_path        = local.has_lambda_zips ? local.analytics_zip : ""
}

module "lambda_predict" {
  source = "../../modules/lambda-predict"

  name_prefix         = var.name_prefix
  environment         = var.environment
  tags                = local.tags
  s3_bucket_name      = module.s3_data.bucket_name
  dynamodb_table_name = module.dynamodb.table_name
  s3_prefix           = var.data_s3_prefix
  cors_origins        = join(",", var.cors_allow_origins)
  lambda_layer_arn    = local.has_lambda_zips ? aws_lambda_layer_version.core[0].arn : null
  package_path        = local.has_lambda_zips ? local.predict_zip : ""
}

module "ecs_predict_image" {
  count  = var.enable_ecs_compute && var.build_ecs_image ? 1 : 0
  source = "../../modules/ecs-predict-image"

  enabled            = true
  ecr_repository_url = local.ecr_predict_url
  repo_root          = local.repo_root
  aws_region         = var.aws_region
  build_script       = local.ecs_build_script
}

module "ecs_compute" {
  count  = var.enable_ecs_compute ? 1 : 0
  source = "../../modules/ecs-compute"

  name_prefix         = var.name_prefix
  environment         = var.environment
  tags                = local.tags
  container_image     = local.ecs_container_image
  s3_bucket_name      = module.s3_data.bucket_name
  dynamodb_table_name = module.dynamodb.table_name
  s3_prefix           = var.data_s3_prefix
  cors_origins        = join(",", var.cors_allow_origins)
  aws_region          = var.aws_region

  depends_on = [module.ecs_predict_image]
}

module "api_gateway" {
  source = "../../modules/api-gateway"

  name_prefix             = var.name_prefix
  environment             = var.environment
  tags                    = local.tags
  analytics_invoke_arn    = module.lambda_analytics.invoke_arn
  predict_invoke_arn      = module.lambda_predict.invoke_arn
  analytics_function_name = module.lambda_analytics.function_name
  predict_function_name   = module.lambda_predict.function_name
  enable_ecs_compute      = var.enable_ecs_compute
  compute_alb_dns         = var.enable_ecs_compute ? module.ecs_compute[0].alb_dns_name : null
  cors_allow_origins      = var.cors_allow_origins
}

module "frontend_cdn" {
  source = "../../modules/frontend-cdn"

  name_prefix         = var.name_prefix
  environment         = var.environment
  backend_api_url     = var.backend_api_url
  aliases             = var.aliases
  acm_certificate_arn = var.acm_certificate_arn
  api_gateway_domain  = module.api_gateway.api_domain
  tags                = local.tags
}

module "github_oidc" {
  count  = var.enable_github_oidc ? 1 : 0
  source = "../../modules/github-oidc"

  github_org  = var.github_org
  github_repo = var.github_repo
  role_name   = "${var.name_prefix}-${var.environment}-github-actions"
  tags        = local.tags
}

module "etl_scheduler" {
  count  = var.enable_etl_scheduler ? 1 : 0
  source = "../../modules/etl-scheduler"

  name_prefix           = var.name_prefix
  environment           = var.environment
  github_org            = var.github_org
  github_repo           = var.github_repo
  github_dispatch_token = var.github_dispatch_token
  s3_bucket_name        = module.s3_data.bucket_name
  dynamodb_table_name   = module.dynamodb.table_name
  schedule_s3_key       = "${var.data_s3_prefix}/schedule.json"
  tags                  = local.tags
}

check "etl_scheduler_token" {
  assert {
    condition     = !var.enable_etl_scheduler || length(var.github_dispatch_token) > 0
    error_message = "Set github_dispatch_token (TF_VAR_github_dispatch_token) when enable_etl_scheduler is true."
  }
}
