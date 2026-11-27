# AWS Deployment Guide

**Status: deployment instructions / target architecture only. The repository's current project evidence is local Docker Compose. No public AWS deployment is claimed.**

This guide gives two paths. Start with the portfolio path only if you can accept temporary AWS charges. The production target is a separate, more expensive architecture. Check current AWS pricing for your region before creating resources.

## 1. Architecture choices

### Path A — Cost-conscious portfolio deployment (single EC2)

- One EC2 Linux instance.
- Docker Engine + Docker Compose.
- Frontend Nginx, FastAPI, PostgreSQL, Redis, Kafka and worker containers.
- Ollama may run on the same instance only if its CPU/RAM capacity is sufficient; otherwise use a separate model host or a managed inference provider.
- Security group exposes HTTPS through a reverse proxy. SSH is restricted to your IP or use Systems Manager Session Manager.
- EBS volumes persist database, documents, Kafka and Redis data.
- This is a single-host demonstration architecture, not highly available production.

The current Compose file binds PostgreSQL port 55432 to the host. For cloud deployment, remove public DB ingress and bind it to loopback or keep it internal-only. Do not expose Redis or Kafka to the internet.

### Path B — Production-oriented target architecture

- Route 53 + ACM + Application Load Balancer.
- ECS/Fargate services for API and frontend, plus separately scaled worker service.
- RDS PostgreSQL with pgvector-compatible engine/version validation.
- S3 private bucket for original documents.
- ElastiCache Redis.
- Amazon MSK or another managed Kafka-compatible service, after validating client compatibility and operational requirements.
- Secrets Manager and IAM task roles.
- CloudWatch logs, metrics and alarms.
- WAF, private subnets, NAT/VPC endpoints as appropriate.

This path has materially higher baseline cost. Do not provision it casually for a portfolio demo.

## 2. Pre-deployment source review

Before any AWS deployment:
1. Review the current `docker-compose.yml`, Dockerfiles and environment variable names.
2. Confirm the backend image includes required application code and migrations.
3. Decide where original documents live. The current code uses filesystem paths; S3 support requires implementation work unless an existing storage adapter is verified.
4. Confirm the target PostgreSQL supports the required pgvector extension and 384-dimensional vector type.
5. Confirm Kafka broker authentication/TLS settings are supported by the current worker configuration. The current Compose configuration uses plaintext inside its private Docker network; do not assume it is ready for MSK IAM/SASL without code/config changes.
6. Confirm Ollama model-serving network access, model files, memory and performance.
7. Review CORS, TRUSTED_HOSTS, JWT secret, docs exposure and rate-limit fail-open setting.
8. Build and test immutable images from a known Git commit.

## 3. AWS account and region preparation

1. Enable MFA on the AWS root user; do not use root access keys.
2. Create an IAM deployment identity/role with least privilege.
3. Select a region close to the intended users and check service availability.
4. Set an AWS budget and billing alert before creating resources.
5. Use AWS Systems Manager Session Manager where practical instead of opening SSH to the world.
6. Tag resources, e.g. `Project=DocuMindAI`, `Environment=demo`, `Owner=<your-alias>`.
7. Decide a shutdown/deletion date for temporary resources.

Example local CLI checks:

```powershell
aws --version
aws sts get-caller-identity
aws configure list
```

Do not paste credentials or the output of secret-bearing commands into GitHub.

## 4. Portfolio EC2 deployment procedure

### 4.1 Create network and compute

- Use a VPC with a public subnet only for the ingress host, or place the instance in a private subnet behind an ALB.
- Create a security group with inbound HTTPS (443) only from intended users. If using temporary HTTP for certificate setup, remove it after HTTPS is configured.
- Do not allow inbound 5432, 6379, 9092 or 11434 from the internet.
- Create an EC2 instance with sufficient RAM/disk for six containers and model inference; size must be selected after measuring Ollama memory/latency. No instance size is prescribed here.
- Attach an IAM instance profile for Systems Manager and narrowly scoped access to required AWS services.
- Attach encrypted EBS storage sized for DB, document files, Kafka and logs.
- Prefer Session Manager for shell access.

### 4.2 Install runtime

Install Docker Engine and the Docker Compose plugin using the current official instructions for the selected Linux distribution. Verify:

```bash
docker --version
docker compose version
```

### 4.3 Retrieve source and configure environment

Clone the repository on the instance:

```bash
git clone https://github.com/abrar2309/documind-ai.git
cd documind-ai
```

Create the environment file on the host with restrictive permissions. Populate strong, unique values for database password and JWT signing secret. Do not commit this file.

The Compose configuration currently defaults to local Ollama at `host.docker.internal:11434`; that host alias is specific to Docker Desktop and should not be assumed to work on a Linux EC2 host. Set `OLLAMA_BASE_URL` to a reachable private model-service address or deploy Ollama on the same Docker network and use its service DNS name. Pull both configured models and verify inference from the backend/worker network.

### 4.4 Production configuration gates

Before starting:
- `ENVIRONMENT=production`
- `JWT_SECRET_KEY`: unique random secret, at least 32 characters.
- `CORS_ALLOWED_ORIGINS`: explicit HTTPS frontend origin(s), no wildcard.
- `TRUSTED_HOSTS`: exact public hostnames, no wildcard.
- `RATE_LIMIT_FAIL_OPEN=false`
- `EXPOSE_API_DOCS=false`
- `ENABLE_HSTS=true` after HTTPS is correctly terminated.
- Database password and model credentials stored securely.
- Confirm database URL uses internal service DNS or private RDS endpoint.
- Confirm all services have restart policies, persistent storage and health checks.

The current Compose file is a local topology, not a turnkey secure production configuration. Review and modify it before exposure.

### 4.5 Build and start

```bash
docker compose config --quiet
docker compose build
docker compose up -d
docker compose ps
```

Inspect logs without printing secrets:

```bash
docker compose logs --tail=100 backend
docker compose logs --tail=100 document-worker
docker compose logs --tail=100 kafka
```

Verify health locally on the instance:

```bash
curl -fsS http://127.0.0.1:8000/health
curl -fsS http://127.0.0.1:8000/health/db
curl -fsS http://127.0.0.1:3000/health
```

### 4.6 HTTPS and domain

- Register/use a domain and create DNS records.
- Configure an HTTPS reverse proxy or ALB with an ACM certificate.
- Proxy the frontend and API under the intended public hostname.
- Ensure trusted-host and CORS settings exactly match the deployed host.
- Redirect HTTP to HTTPS.
- Do not expose backend port 8000 directly if Nginx/ALB is the public entry point.

### 4.7 End-to-end validation

Run the acceptance tests in [E2E_TEST_PLAN.md](../testing/E2E_TEST_PLAN.md). Confirm:
- Login and workspace access.
- Upload -> processing -> ready.
- Worker can reach model endpoint.
- Embeddings persist in pgvector.
- Chat returns answer and source citations.
- Cross-workspace access is denied.
- Backups can be restored.
- Logs and alarms work.

Only after all checks pass should the public URL be added to the README.

## 5. Production-oriented ECS path

For a later production implementation:
1. Build backend, frontend and worker images in CI.
2. Push immutable image tags to ECR.
3. Create VPC with private application/data subnets and public ALB subnets.
4. Configure ECS cluster and separate task definitions/services for API, frontend and worker.
5. Use RDS PostgreSQL with verified pgvector extension support and private connectivity.
6. Implement S3 object storage integration in the application before switching away from filesystem storage.
7. Configure Redis and Kafka-compatible broker with TLS/auth supported by application clients.
8. Store secrets in Secrets Manager and grant access through task roles.
9. Add CloudWatch log groups, alarms, dashboards and tracing/request IDs.
10. Configure ALB health checks and HTTPS certificate.
11. Run database migrations as a controlled one-off task.
12. Deploy canary/rolling updates and verify rollback.
13. Test backups, restore and disaster recovery.

Do not treat this checklist as proof the application already supports S3 or managed Kafka authentication; those integrations need code and configuration validation.

## 6. Cost control and teardown

AWS charges may continue while resources exist, even when the application is idle. Before provisioning, use the AWS Pricing Calculator and set a budget alert.

For a temporary EC2 demo:
- Stop the instance when not demonstrating; EBS, snapshots, Elastic IPs and some attached resources may still incur charges.
- Delete unused load balancers, NAT gateways, public IP allocations, databases, caches and broker clusters.
- Keep only explicitly required backups.
- Confirm no paid resources remain in the billing console.

Never run blind Terraform destroy or delete shared resources. Review the plan and resource ownership first.

## 7. Deployment evidence

Record:
- Git commit SHA and image tags.
- AWS region and resource architecture (no account IDs or secrets).
- Successful health check outputs.
- Test report and timestamp.
- HTTPS URL only after externally verified.
- CloudWatch alarms/log evidence.
- Backup/restore evidence.

Redact account IDs, public IPs if sensitive, tokens, passwords, private keys and document contents.
