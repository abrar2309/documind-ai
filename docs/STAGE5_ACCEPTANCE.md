# Stage 5 acceptance checklist

- [ ] Production configuration validates and refuses weak secrets / wildcard CORS / public API docs.
- [ ] Backend and frontend images build and run as non-root where applicable.
- [ ] CI succeeds on main and pull requests.
- [ ] AWS infrastructure plan reviewed and approved.
- [ ] Managed PostgreSQL/pgvector, Redis, Kafka and S3 provisioned privately.
- [ ] Application storage migrated from local filesystem to S3/shared durable storage.
- [ ] Ollama replaced with a secured reachable inference endpoint or supported hosted provider.
- [ ] ECS backend, worker and frontend healthy behind HTTPS ALB.
- [ ] Alembic migration executed as a controlled one-off task after backup.
- [ ] Auth, RBAC, workspace isolation, ingestion, RAG citations and worker recovery verified in cloud.
- [ ] CloudWatch dashboards/alarms, backup/restore and incident runbook tested.
- [ ] Public demo URL, GitHub repository, architecture diagram and demo video published.

Do not mark Stage 5 complete until the public live demo and portfolio deliverables are actually available.
