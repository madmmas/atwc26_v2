locals {
  api_name = "${var.name_prefix}-${var.environment}-api"

  # POST /api/predict → ECS Fargate via ALB (see ecs-compute module).
  # There is no Lambda for predict when enable_ecs_compute is true.
  use_ecs_compute = var.enable_ecs_compute
}

resource "aws_apigatewayv2_api" "http" {
  name          = local.api_name
  protocol_type = "HTTP"

  cors_configuration {
    allow_origins = var.cors_allow_origins
    allow_methods = ["GET", "POST", "OPTIONS"]
    allow_headers = ["*"]
    max_age       = 300
  }

  tags = merge(var.tags, { Component = "api-gateway" })
}

resource "aws_apigatewayv2_integration" "analytics" {
  api_id                 = aws_apigatewayv2_api.http.id
  integration_type       = "AWS_PROXY"
  integration_uri        = var.analytics_invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_integration" "predict_lambda" {
  count = local.use_ecs_compute ? 0 : 1

  api_id                 = aws_apigatewayv2_api.http.id
  integration_type       = "AWS_PROXY"
  integration_uri        = var.predict_invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_integration" "compute" {
  count = local.use_ecs_compute ? 1 : 0

  api_id               = aws_apigatewayv2_api.http.id
  integration_type     = "HTTP_PROXY"
  integration_method   = "ANY"
  integration_uri      = var.compute_listener_arn
  payload_format_version = "1.0"
}

locals {
  compute_integration_id = local.use_ecs_compute ? aws_apigatewayv2_integration.compute[0].id : aws_apigatewayv2_integration.predict_lambda[0].id
}

resource "aws_apigatewayv2_route" "predict" {
  api_id    = aws_apigatewayv2_api.http.id
  route_key = "POST /api/predict"
  target    = "integrations/${local.compute_integration_id}"
}

resource "aws_apigatewayv2_route" "analytics" {
  api_id    = aws_apigatewayv2_api.http.id
  route_key = "$default"
  target    = "integrations/${aws_apigatewayv2_integration.analytics.id}"
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.http.id
  name        = "$default"
  auto_deploy = true
  tags        = var.tags
}

resource "aws_lambda_permission" "analytics" {
  statement_id  = "AllowAPIGatewayInvokeAnalytics"
  action        = "lambda:InvokeFunction"
  function_name = var.analytics_function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.http.execution_arn}/*/*"
}

resource "aws_lambda_permission" "predict" {
  count = local.use_ecs_compute ? 0 : 1

  statement_id  = "AllowAPIGatewayInvokePredict"
  action        = "lambda:InvokeFunction"
  function_name = var.predict_function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.http.execution_arn}/*/*"
}
