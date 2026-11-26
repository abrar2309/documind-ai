output "load_balancer_dns_name" {
  value = aws_lb.documind.dns_name
}
output "ecs_cluster_name" {
  value = aws_ecs_cluster.documind.name
}
output "task_security_group_id" {
  value = aws_security_group.tasks.id
}

output "backend_ecr_repository_url" {
  value = aws_ecr_repository.backend.repository_url
}
output "frontend_ecr_repository_url" {
  value = aws_ecr_repository.frontend.repository_url
}
