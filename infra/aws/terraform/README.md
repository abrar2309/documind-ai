# Terraform ECS foundation

This module provisions ECS Fargate compute, ECR-image consumers, CloudWatch log groups, an internet-facing ALB with HTTP→HTTPS redirect, target groups, and task/ALB security groups.

It deliberately expects the network, ACM certificate, RDS PostgreSQL/pgvector, MSK Kafka, ElastiCache Redis, and Secrets Manager values to exist already. This avoids silently creating expensive managed services or changing an AWS account.

Before use:
- Use two or more Availability Zones.
- Place ECS tasks and data services in private subnets.
- Allow inbound RDS 5432, Redis 6379 and Kafka listener ports only from the ECS task security group.
- Add NAT or VPC endpoints for ECR, CloudWatch Logs, Secrets Manager and outbound model API access.
- Give the task role only the S3 permissions required after the app is migrated to S3.
- Configure WAF and ALB access logs separately.
- Ensure the ALB target group health checks and backend trusted-host/CORS settings match the real domain.

The application currently stores uploaded files on a local filesystem and uses Ollama's local host URL by default. Those are explicit blockers to a reliable multi-task cloud deployment; see `docs/DEPLOYMENT_RUNBOOK.md`.

Run `terraform fmt -recursive`, `terraform init`, `terraform validate`, then review `terraform plan`. Do not apply until the plan, security groups, costs, and secret references are reviewed.
