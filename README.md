# DocuMind AI — Document Intelligence Platform

A workspace-scoped document intelligence application built with React/TypeScript, FastAPI, PostgreSQL + pgvector, Redis, Kafka, a background document worker and Ollama-based local inference.

## What it does

- User authentication and workspace-scoped access.
- PDF and UTF-8 TXT upload (20 MiB maximum).
- Asynchronous document ingestion through a transactional outbox, Kafka and a worker.
- Text extraction, overlapping chunking, 384-dimensional embeddings and vector persistence.
- Hybrid semantic (pgvector) + lexical (PostgreSQL full-text) retrieval.
- Grounded question answering with source citation metadata.
- Persistent conversations, document re-indexing and document-wide exact term/phrase counting.
- React frontend served by Nginx; API requests are proxied to FastAPI.

## Local development

- Frontend: http://localhost:3000
- Backend: http://localhost:8000
- API docs: http://localhost:8000/docs

The local Docker Compose topology defines six containers: frontend, backend, PostgreSQL, Redis, Kafka and document worker. In the documented Windows setup, Ollama runs on the host and containers reach it through `host.docker.internal:11434`.

Configured local models are `all-minilm` for embeddings and `qwen3:1.7b` for chat. Confirm model availability on the machine with `ollama list`; configuration does not prove that a model is installed.

## Start and verify

Run from the directory containing the active `docker-compose.yml`:

```powershell
docker compose config --quiet
docker compose up -d --build
docker compose ps
Invoke-RestMethod http://localhost:8000/health
Invoke-RestMethod http://localhost:8000/health/db
Invoke-WebRequest http://localhost:3000/ -UseBasicParsing
```

Run backend tests only after confirming the test harness points to its dedicated test database:

```powershell
docker exec -e TRUSTED_HOSTS=localhost,127.0.0.1,testserver document-intelligence-backend python -m pytest -q
```

Frontend production build (from `frontend`):

```powershell
npm.cmd run build
```

## Engineering documentation

The full engineering handbook is in **[docs/README.md](docs/README.md)**.

It includes:
- High-Level Design (HLD) and Low-Level Design (LLD)
- System design, data model and API reference
- Ingestion and RAG architecture, sequence flows and design trade-offs
- Test evidence register and browser end-to-end test plan
- AWS deployment guide, production security checklist and operations runbook
- Demo recording guide (add/complete after the final browser acceptance run)

## Important limitations and deployment status

- Scanned-PDF OCR is not implemented.
- Supported upload formats are PDF and UTF-8 TXT.
- Local Ollama inference performance depends on host CPU/GPU and available memory.
- The local Kafka Compose setup is a single broker/controller and is not a highly available production cluster.
- AWS deployment instructions are documentation only. No public AWS deployment or live demo URL is claimed as completed.
- The recorded local test results and their scope/limitations are documented in [Testing & Evidence](docs/testing/TESTING_AND_EVIDENCE.md).

## Security

Never commit `.env`, API keys, passwords, JWTs, private keys or real user documents. Do not expose PostgreSQL, Redis, Kafka or Ollama directly to the public internet. Avoid destructive volume-reset commands; back up before database or storage changes.
