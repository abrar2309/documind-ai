# AWS and Production Security Checklist

Use this as a release gate. A checked item requires evidence, not an assumption.

## Identity and secrets
- [ ] Root MFA enabled; no root access keys.
- [ ] Human access uses IAM Identity Center/assumed roles where available.
- [ ] EC2/ECS uses instance/task roles with least privilege.
- [ ] Database password and JWT secret are unique, strong and stored in Secrets Manager or an approved secret store.
- [ ] No .env, tokens, passwords, certificates or private keys committed.
- [ ] Secrets rotation and incident response procedure documented.

## Network
- [ ] Database, Redis, Kafka and Ollama are not internet-facing.
- [ ] App/data resources use private subnets where practical.
- [ ] Inbound security-group rules are minimal and reviewed.
- [ ] Administrative access uses Session Manager or tightly restricted source IP.
- [ ] HTTPS enforced; certificate renewal monitored.
- [ ] CORS and trusted-host lists contain only exact production hosts.

## Application
- [ ] Production mode validation passes.
- [ ] API docs disabled or access-controlled.
- [ ] Rate limiter configured fail-closed where required.
- [ ] Workspace isolation tests pass.
- [ ] Upload size/type validation and quotas reviewed.
- [ ] Malware scanning and abuse controls assessed.
- [ ] LLM prompt injection defenses tested with hostile document content.
- [ ] Sensitive data is excluded from logs and metrics.
- [ ] Access/refresh token expiry and revocation tested.

## Data
- [ ] Encryption at rest enabled for database, object storage and volumes.
- [ ] TLS in transit configured for managed services.
- [ ] Database and file backups configured.
- [ ] Restore test completed and timed.
- [ ] Retention/deletion policy documented.
- [ ] S3 public access blocked if S3 is introduced.
- [ ] Tenant-aware access controls tested at API and data layers.

## Operations
- [ ] Centralized logs and request IDs.
- [ ] Alerts for API errors, worker failures, Kafka lag, DB capacity and model failures.
- [ ] Dependency/image scanning in CI.
- [ ] Rollback procedure tested.
- [ ] Cost budget and billing alert configured.
- [ ] Incident owner and escalation process identified.

Do not describe the application as production-secure until the relevant controls are implemented and verified.
