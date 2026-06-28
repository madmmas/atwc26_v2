locals {
  function_name = "${var.name_prefix}-${var.environment}-predict"
  package_path  = var.package_path != "" ? var.package_path : "${path.module}/placeholder.zip"
}

data "archive_file" "placeholder" {
  count       = var.package_path == "" ? 1 : 0
  type        = "zip"
  output_path = "${path.module}/placeholder.zip"

  source {
    content  = "def handler(event, context): return {'statusCode': 503, 'body': 'package lambdas first'}"
    filename = "predict_api/handler.py"
  }
}

data "aws_iam_policy_document" "assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "lambda" {
  name               = "${local.function_name}-role"
  assume_role_policy = data.aws_iam_policy_document.assume.json
  tags               = var.tags
}

resource "aws_iam_role_policy_attachment" "basic" {
  role       = aws_iam_role.lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

data "aws_iam_policy_document" "data_access" {
  statement {
    actions   = ["s3:GetObject", "s3:ListBucket"]
    resources = [
      "arn:aws:s3:::${var.s3_bucket_name}",
      "arn:aws:s3:::${var.s3_bucket_name}/*",
    ]
  }

  statement {
    actions   = ["dynamodb:GetItem", "dynamodb:Query", "dynamodb:Scan"]
    resources = ["arn:aws:dynamodb:*:*:table/${var.dynamodb_table_name}"]
  }
}

resource "aws_iam_role_policy" "data_access" {
  name   = "${local.function_name}-data"
  role   = aws_iam_role.lambda.id
  policy = data.aws_iam_policy_document.data_access.json
}

resource "aws_lambda_function" "predict" {
  function_name = local.function_name
  role          = aws_iam_role.lambda.arn
  handler       = "predict_api.handler.handler"
  runtime       = "python3.11"
  architectures = ["arm64"]
  memory_size   = var.memory_size
  timeout       = var.timeout

  filename         = local.package_path
  source_code_hash = filebase64sha256(local.package_path)

  layers = var.lambda_layer_arn != null ? [var.lambda_layer_arn] : []

  environment {
    variables = {
      ATWC26_DATA_DIR       = "/tmp/data"
      ATWC26_S3_BUCKET      = var.s3_bucket_name
      ATWC26_S3_PREFIX      = var.s3_prefix
      ATWC26_DYNAMODB_TABLE = var.dynamodb_table_name
      ATWC26_CORS_ORIGINS   = var.cors_origins
    }
  }

  tags = merge(var.tags, { Component = "lambda-predict" })
}
