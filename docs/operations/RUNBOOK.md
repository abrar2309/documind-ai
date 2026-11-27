# Operations Runbook

## 1. Local URLs

| Component | URL |
|---|---|
| Frontend | http://localhost:3000 |
| Backend root | http://localhost:8000/ |
| Backend health | http://localhost:8000/health |
| Database health | http://localhost:8000/health/db |
| Redis health | http://localhost:8000/health/redis |
| Metrics | http://localhost:8000/ops/metrics |
| OpenAPI docs | http://localhost:8000/docs |

## 2. Inspect services

```powershell
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
docker logs --tail 100 document-intelligence-backend
docker logs --tail 100 documind-document-worker
docker logs --tail 100 documind-kafka
docker logs --tail 100 document-intelligence-db
docker logs --tail 100 documind-redis
```

Use the active runtime Compose directory and correct project context. A different checkout can show no containers because Compose project identity and working directory differ.

## 3. Worker and Kafka diagnosis

- Check worker logs for ingestion completion, retry, terminal failure and DLQ messages.
- Inspect consumer group and lag using Kafka CLI inside the broker container.
- A lag of zero means the group has consumed available records at that instant; it does not prove a particular file was indexed correctly.
- Verify the document row reaches ready and chunk_count is nonzero.

## 4. Redis diagnosis

```powershell
docker exec documind-redis redis-cli ping
docker exec documind-document-worker python -c "import asyncio; from redis.asyncio import Redis; r=Redis.from_url('redis://redis:6379/0'); print(asyncio.run(r.ping()))"
```

Expected outputs are PONG and True respectively when those services are reachable.

## 5. Common symptoms

| Symptom | First checks |
|---|---|
| Login 401 | Correct account, backend logs, auth route, clock and token state |
| Workspace 403 | Membership and role; confirm requested workspace ID |
| Upload 415 | Supported MIME type and extension must match PDF/.pdf or text/plain/.txt |
| Upload 413 | File exceeds 20 MiB |
| Document remains processing | Worker logs, outbox publication, Kafka consumer, Ollama reachability |
| Document failed | Inspect sanitized error_message and worker/DLQ logs |
| Chat has no citations | Confirm document status ready, chunks exist, question is grounded and retrieval returns candidates |
| Model timeout | Check Ollama process/model load, host resources and configured timeout |
| DB authentication failure | Compare environment configuration securely; never print or paste passwords |
| Frontend API error | Browser Network tab, Nginx proxy, API base URL, backend health |

## 6. Safe operational rules

- Never run `docker compose down -v`, `docker volume prune` or broad container/volume deletion as a routine fix.
- Never reset the primary database to fix a test failure.
- Use a synthetic disposable document for destructive tests.
- Do not print .env contents or tokens.
- Back up before schema changes and test restore.
- Keep the runtime directory separate from the Git working copy when they are separate Compose projects.
