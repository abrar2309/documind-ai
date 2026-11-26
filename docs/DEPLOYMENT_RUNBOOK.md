# Stage 5 — AWS deployment and operations runbook

## Architecture target

- Route 53 + ACM + Application Load Balancer (HTTPS).
- ECS Fargate services: frontend, FastAPI backend, and document worker.
- ECR repositories for immutable, scan-on-push container images.
- CloudWatch Logs for service logs.
- RDS PostgreSQL with pgvector support, ElastiCache Redis, and Amazon MSK (or another Kafka-compatible managed cluster).
- S3 for document object storage is the recommended next storage migration; the current application writes to a local filesystem volume and is not yet S3-compatible.
- Secrets Manager for database URL, JWT secret, Redis URL and provider API keys.

The Terraform in `infra/aws/terraform` provisions the ECS/ALB compute foundation and ECR repositories only. It expects an existing VPC, private/public subnets, TLS certificate, image URIs, and managed data-service endpoints/secrets. It does not create RDS, MSK, ElastiCache, S3, Route 53, ACM, WAF or NAT gateways.

## Important application deployment blockers

1. The current document storage implementation uses `STORAGE_ROOT` and local filesystem paths. ECS task-local storage is ephemeral. Do not deploy real user documents until the storage adapter is migrated to S3 or a deliberately managed shared filesystem.
2. The current Ollama defaults point to `host.docker.internal`, which is a local-development address. For AWS, choose a reachable hosted model endpoint or a secured GPU inference service and set `OLLAMA_BASE_URL`, or configure supported OpenAI-compatible providers and secrets. Do not expose Ollama publicly.
3. The current Kafka deployment is a single-node local KRaft broker and the current client configuration is bootstrap-server based. Use managed multi-AZ Kafka for production and implement/test the selected MSK TLS/SASL/IAM authentication mode before connecting the worker or outbox publisher.
4. The current local Compose stack exposes PostgreSQL and application ports for developer access. Keep database, Redis and Kafka endpoints private in AWS.
5. The current app uses `localStorage` for bearer/refresh tokens. Review the security note before public launch.

## Provisioning sequence

1. Create or select an AWS account and region; configure MFA and least-privilege IAM.
2. Create VPC, public/private subnets across at least two Availability Zones, NAT/egress, security groups, ACM certificate and DNS.
3. Provision RDS PostgreSQL with pgvector, ElastiCache Redis, MSK and S3. Enable encryption, private networking, backups and monitoring.
4. Store database URL, JWT secret and Redis URL in Secrets Manager. Terraform consumes secret ARNs only; do not pass plaintext values into Terraform variables.
5. Populate `terraform.tfvars` from `terraform.tfvars.example`, then run `terraform init`, `terraform fmt -check`, `terraform validate`, and inspect a plan.
6. Create only the ECR repositories first: `terraform apply -target=aws_ecr_repository.backend -target=aws_ecr_repository.frontend`. Review the targeted plan before applying.
7. Build and push initial bootstrap images using `backend/Dockerfile.production` and `frontend/Dockerfile`. Set `backend_image` and `frontend_image` to those immutable image URIs in `terraform.tfvars`.
8. Run a fresh full `terraform plan`, review costs/network exposure/secret ARNs, and apply only after explicit approval. The plan creates ECS/ALB compute resources.
9. Configure the GitHub production environment: `AWS_ROLE_TO_ASSUME` secret and `AWS_REGION`, ECR repository names, ECS cluster/service/task-family variables. Configure GitHub OIDC trust to allow only this repository and protected `production` environment. Grant narrowly scoped ECR push, ECS task-definition/service-update, and `iam:PassRole` permissions for only the two ECS task roles.
10. Push a commit to run CI. After reviewing the commit and infrastructure, manually run the `DocuMind AWS deployment` workflow from GitHub Actions. It builds immutable SHA-tagged images, registers new task definitions and waits for ECS stability.
11. After a database backup, run Alembic migrations as a controlled one-off task. Verify registration/login, workspace isolation, upload, worker completion, chat citations, exact count, Redis, Kafka lag, logs and alarms.
12. Configure DNS/HTTPS, WAF, alarms, backups, a recovery test and public demo content.

## Bootstrap image example

Replace the account, region and repository names with the values from your AWS account:

```bash
docker build -f backend/Dockerfile.production -t BACKEND_ECR_URI:bootstrap ./backend
docker push BACKEND_ECR_URI:bootstrap
docker build --build-arg VITE_API_BASE_URL=/api/v1 -t FRONTEND_ECR_URI:bootstrap ./frontend
docker push FRONTEND_ECR_URI:bootstrap
```

Use the exact immutable image URIs in Terraform variables. Do not put secrets in image build arguments.

## Terraform commands

From `infra/aws/terraform`:

```bash
terraform init
terraform fmt -check
terraform validate
terraform plan -out=tfplan
```

Review `tfplan` carefully. Apply is a separate, explicit approval step. Terraform state may contain sensitive infrastructure metadata; use an encrypted, access-controlled remote backend before team use.

## Rollback

- Roll back ECS task definitions to the last known-good image digest.
- Do not roll back database migrations automatically. Use forward fixes unless a tested backward migration exists.
- Preserve S3 objects, RDS snapshots, Kafka topics and Redis persistence according to the retention policy.
- Never use `docker compose down -v`, delete persistent volumes, or reset the database as a deployment rollback.
