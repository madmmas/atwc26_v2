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

# Single predict integration — create_before_destroy ensures route can be
# repointed before the old integration is removed when switching Lambda ↔ ECS.
resource "aws_apigatewayv2_integration" "predict" {
  api_id                 = aws_apigatewayv2_api.http.id
  integration_type       = local.use_ecs_compute ? "HTTP_PROXY" : "AWS_PROXY"
  integration_uri        = local.use_ecs_compute ? "http://${var.compute_alb_dns}" : var.predict_invoke_arn
  integration_method     = local.use_ecs_compute ? "ANY" : null
  payload_format_version = local.use_ecs_compute ? "1.0" : "2.0"
  connection_type        = local.use_ecs_compute ? "INTERNET" : null

  # HTTP_PROXY to a bare ALB DNS sends POST to "/" unless the request path is set
  # explicitly — FastAPI then returns 404 and CloudFront serves the S3 404.html page.
  request_parameters = local.use_ecs_compute ? {
    "overwrite:path" = "$request.path"
  } : null

  lifecycle {
    create_before_destroy = true
  }
}

moved {
  from = aws_apigatewayv2_integration.predict_lambda[0]
  to   = aws_apigatewayv2_integration.predict
}

resource "aws_apigatewayv2_route" "predict" {
  api_id    = aws_apigatewayv2_api.http.id
  route_key = "POST /api/predict"
  target    = "integrations/${aws_apigatewayv2_integration.predict.id}"

  depends_on = [aws_apigatewayv2_integration.predict]
}

# GET /api/health is served by analytics ($default). Predict model availability
# lives on the predict service at /api/predict/health (used by the static frontend).
resource "aws_apigatewayv2_route" "predict_health" {
  api_id    = aws_apigatewayv2_api.http.id
  route_key = "GET /api/predict/health"
  target    = "integrations/${aws_apigatewayv2_integration.predict.id}"

  depends_on = [aws_apigatewayv2_integration.predict]
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
