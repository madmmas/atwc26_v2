output "function_name" {
  value = aws_lambda_function.predict.function_name
}

output "function_arn" {
  value = aws_lambda_function.predict.arn
}

output "invoke_arn" {
  value = aws_lambda_function.predict.invoke_arn
}
