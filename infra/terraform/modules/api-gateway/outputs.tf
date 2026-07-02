output "api_endpoint" {
  value = aws_apigatewayv2_api.http.api_endpoint
}

output "api_domain" {
  description = "API Gateway hostname (no scheme) for CloudFront origin."
  value       = replace(aws_apigatewayv2_api.http.api_endpoint, "https://", "")
}

output "api_id" {
  value = aws_apigatewayv2_api.http.id
}
