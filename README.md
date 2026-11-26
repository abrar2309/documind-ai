# DocuMind — AI Document Intelligence Platform

Multi-tenant document intelligence built with FastAPI, PostgreSQL/pgvector, Ollama and React/TypeScript.

## Stage 2 capabilities

- Workspace-scoped PDF and UTF-8 TXT upload (20 MB limit).
- PDF/TXT extraction, overlapping chunks and page metadata.
- Local semantic embeddings through Ollama `all-minilm` (384 dimensions).
- Local grounded answer generation through Ollama `qwen3:1.7b`.
- PostgreSQL/pgvector cosine retrieval plus PostgreSQL full-text candidate retrieval.
- Weighted hybrid ranking and duplicate-excerpt suppression.
- Workspace-filtered citations with document, page, excerpt and relevance score.
- Persistent conversations and message history.
- Document-wide exact term/phrase counting with per-page counts.
- Re-index endpoint that generates new vectors before replacing existing chunks.
- Workspace membership checks and viewer restrictions on upload/delete/re-index.

## Local configuration

Keep your existing `.env` values. The local AI defaults are:

```env
EMBEDDING_PROVIDER=ollama
CHAT_PROVIDER=ollama
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_EMBEDDING_MODEL=all-minilm
OLLAMA_CHAT_MODEL=qwen3:1.7b
EMBEDDING_DIMENSIONS=384
```

Ollama must be running on the Windows host with both models pulled. The Docker backend reaches it through `host.docker.internal`.

## Start and verify

```powershell
docker compose config --quiet
docker compose up -d --build backend frontend
docker compose ps
Invoke-RestMethod http://localhost:8000/health
Invoke-RestMethod http://localhost:8000/health/db
```

Frontend: http://localhost:3000
Backend API: http://localhost:8000
API documentation: http://localhost:8000/docs

## API

- `POST /api/v1/workspaces/{workspace_id}/documents`
- `GET /api/v1/workspaces/{workspace_id}/documents`
- `DELETE /api/v1/workspaces/{workspace_id}/documents/{document_id}`
- `POST /api/v1/workspaces/{workspace_id}/documents/{document_id}/reindex`
- `GET /api/v1/workspaces/{workspace_id}/documents/{document_id}/exact-count?term=ball`
- `POST /api/v1/workspaces/{workspace_id}/chat`
- `GET /api/v1/workspaces/{workspace_id}/conversations`
- `GET /api/v1/workspaces/{workspace_id}/conversations/{conversation_id}/messages`

## Tests

```powershell
docker compose exec -T backend python -m compileall -q app
docker compose exec -T backend python -m pytest -q
Set-Location frontend
npm.cmd run build
```

The existing test harness uses a separate `document_intelligence_test` database. Inspect `backend/tests/conftest.py` before running tests: it recreates tables in that test database only, not the development database.

## Known boundaries

- Scanned PDFs require OCR; OCR is not included in this stage.
- Exact counting is based on extractable PDF/TXT text. PDF page numbers are returned where available.
- Upload/indexing remains synchronous; a background worker is a later-stage concern.
- Ollama inference speed depends on local CPU/GPU and model size.
- Production hardening, cloud deployment, CI/CD, agents/tools, Redis/Kafka and full observability are later stages.

Never commit `.env`, API keys, passwords or tokens. Do not use destructive volume reset commands.
