locals {
  function_name = "${var.name_prefix}-${var.environment}-etl-dispatch"
}

data "archive_file" "lambda" {
  type        = "zip"
  source_dir  = "${path.module}/lambda"
  output_path = "${path.module}/build/dispatch.zip"
}

data "aws_iam_policy_document" "lambda_assume" {
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
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
  tags               = var.tags
}

resource "aws_iam_role_policy_attachment" "basic" {
  role       = aws_iam_role.lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_secretsmanager_secret" "github_dispatch" {
  name        = "${var.name_prefix}-${var.environment}-github-etl-dispatch"
  description = "GitHub PAT for EventBridge ETL workflow_dispatch (actions:write)."
  tags        = var.tags
}

resource "aws_secretsmanager_secret_version" "github_dispatch" {
  secret_id     = aws_secretsmanager_secret.github_dispatch.id
  secret_string = var.github_dispatch_token
}

data "aws_iam_policy_document" "lambda" {
  statement {
    sid    = "ReadGitHubDispatchToken"
    effect = "Allow"
    actions = [
      "secretsmanager:GetSecretValue",
    ]
    resources = [aws_secretsmanager_secret.github_dispatch.arn]
  }
}

resource "aws_iam_role_policy" "lambda" {
  name   = "${local.function_name}-policy"
  role   = aws_iam_role.lambda.id
  policy = data.aws_iam_policy_document.lambda.json
}

resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${local.function_name}"
  retention_in_days = 14
  tags              = var.tags
}

resource "aws_lambda_function" "dispatch" {
  function_name = local.function_name
  role          = aws_iam_role.lambda.arn
  handler       = "index.handler"
  runtime       = "python3.11"
  architectures = ["arm64"]
  timeout       = 30
  memory_size   = 128

  filename         = data.archive_file.lambda.output_path
  source_code_hash = data.archive_file.lambda.output_base64sha256

  environment {
    variables = {
      GITHUB_TOKEN_SECRET_ARN = aws_secretsmanager_secret.github_dispatch.arn
      GITHUB_OWNER            = var.github_org
      GITHUB_REPO             = var.github_repo
      GITHUB_WORKFLOW         = var.github_workflow_file
      GITHUB_REF              = var.github_ref
    }
  }

  depends_on = [
    aws_cloudwatch_log_group.lambda,
    aws_iam_role_policy_attachment.basic,
    aws_secretsmanager_secret_version.github_dispatch,
  ]

  tags = var.tags
}

resource "aws_cloudwatch_event_rule" "etl_schedule" {
  name                = "${var.name_prefix}-${var.environment}-etl-every-15m"
  description         = "Trigger GitHub Actions ETL workflow every 15 minutes (UTC :00/:15/:30/:45)."
  schedule_expression = var.schedule_expression
  tags                = var.tags
}

resource "aws_cloudwatch_event_target" "etl_dispatch" {
  rule      = aws_cloudwatch_event_rule.etl_schedule.name
  target_id = "dispatch-etl-workflow"
  arn       = aws_lambda_function.dispatch.arn
}

resource "aws_lambda_permission" "eventbridge" {
  statement_id  = "AllowEventBridgeInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.dispatch.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.etl_schedule.arn
}
