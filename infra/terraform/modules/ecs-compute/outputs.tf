output "cluster_name" {
  value = aws_ecs_cluster.predict.name
}

output "service_name" {
  value = aws_ecs_service.predict.name
}

output "alb_listener_arn" {
  description = "Pass to API Gateway HTTP integration for compute routes."
  value       = aws_lb_listener.http.arn
}

output "alb_dns_name" {
  value = aws_lb.predict.dns_name
}
