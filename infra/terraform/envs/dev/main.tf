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

  lambda_build_dir = abspath("${path.module}/../../../build/lambdas")
  layer_zip        = "${local.lambda_build_dir}/layer.zip"
  analytics_zip    = "${local.lambda_build_dir}/analytics.zip"
  predict_zip      = "${local.lambda_build_dir}/predict.zip"
  has_lambda_zips  = fileexists(local.analytics_zip) && fileexists(local.predict_zip) && fileexists(local.layer_zip)
  layer_zip_sha256 = local.has_lambda_zips ? filebase64sha256(local.layer_zip) : ""
  layer_zip_md5    = local.has_lambda_zips ? filemd5(local.layer_zip) : ""
}

module "frontend_cdn" {
  source = "../../modules/frontend-cdn"

  name_prefix         = var.name_prefix
  environment         = var.environment
  backend_api_url     = var.backend_api_url
  aliases             = var.aliases
  acm_certificate_arn = var.acm_certificate_arn
  tags                = local.tags
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

module "api_gateway" {
  source = "../../modules/api-gateway"

  name_prefix             = var.name_prefix
  environment             = var.environment
  tags                    = local.tags
  analytics_invoke_arn    = module.lambda_analytics.invoke_arn
  predict_invoke_arn      = module.lambda_predict.invoke_arn
  analytics_function_name = module.lambda_analytics.function_name
  predict_function_name   = module.lambda_predict.function_name
  cors_allow_origins      = var.cors_allow_origins
}
