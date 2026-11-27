# Low-Level Design (LLD)

## 1. Backend package responsibilities

| Module / area | Responsibility |
|---|---|
| `app.main` | FastAPI construction, middleware, routers, health routes and lifecycle |
| `app.api.router` | Mounts auth, users, workspaces, documents and agent routers under `/api/v1` |
| `app.api.routes.auth` | Registration, login, refresh and logout |
| `app.api.routes.workspaces` | Workspace creation, listing and membership administration |
| `app.api.routes.documents` | Upload/list/delete/re-index, exact count, chat, retrieval and conversation endpoints |
| `app.api.dependencies` | Current-user authentication dependency |
| `app.core.config` | Pydantic settings and production configuration validation |
| `app.core.security` | Password hashing and token functions |
| `app.database` | SQLAlchemy base, engine, sessions and migrations |
| `app.models` | User, workspace, membership, document, chunk, conversation, event and token entities |
| `app.services.document_pipeline` | Extraction, chunking, embedding validation/provider calls and answer generation |
| `app.workers.document_worker` | Outbox dispatch, Kafka consumption, retry, dedupe, DLQ and document persistence |

Exact names can evolve; use the source tree as the implementation authority.

## 2. Frontend responsibilities

- `frontend/src/App.tsx`: application screens and interaction flows.
- `frontend/src/lib/api.ts`: typed API client, bearer-token attachment, refresh retry and endpoint wrappers.
- `frontend/src/main.tsx`: React application entry point.
- `frontend/src/*.css`: presentation and responsive layout.

The API client reads `VITE_API_BASE_URL`, defaulting to `http://127.0.0.1:8000/api/v1`. The Docker frontend build supplies `/api/v1`, which Nginx proxies to the backend.

## 3. Upload endpoint contract

`POST /api/v1/workspaces/{workspace_id}/documents`

- Auth: bearer access token.
- Body: multipart/form-data with required `file`.
- Supported MIME/extension pairs: PDF/.pdf and text/plain/.txt.
- Maximum size: 20 MiB.
- Returns: HTTP 202 and a document response initially in processing state.
- Permission: workspace member; viewer role cannot upload.
- Persistence: original file + document row + outbox event.

The HTTP 202 means the ingestion request has been accepted. It does not mean extraction and indexing are already complete. Poll the document list until status is ready or failed.

## 4. Worker algorithm

```text
start worker
  start Kafka producer and consumer
  periodically dispatch unpublished outbox rows
  consume document event
    validate schema and UUIDs
    begin database transaction
      if event already processed: skip idempotently
      lock and validate document/workspace/uploader
      set status=processing
      read original file
      extract page text
      chunk text (900 chars, 150 overlap)
      request embeddings from configured provider
      validate vector count, dimension=384 and finite values
      replace chunk records and persist vectors
      update page_count/chunk_count/status=ready
      insert processed-event marker
    commit
    invalidate document-list cache
  on retryable failure: retry with exponential backoff
  on terminal/exhausted failure: mark failed and publish DLQ
  acknowledge only after durable completion/finalization
```

The worker uses an inbox-style `processed_events` marker for deduplication. The outbox event and document record are written atomically by the API.

## 5. Chunking and embedding

- PDF extraction preserves page numbers.
- TXT extraction uses UTF-8 (with BOM tolerance).
- Whitespace is normalized before chunking.
- Default chunk size: 900 characters.
- Default overlap: 150 characters.
- Embedding provider: Ollama by default; OpenAI provider is configurable if a valid key and compatible settings are supplied.
- Local embedding model: `all-minilm`.
- Expected vector dimensions: 384.
- Vector validation rejects wrong item count, wrong dimensions and non-finite values.

Hash embeddings remain in code as an explicit legacy provider option; do not describe them as the configured semantic model.

## 6. Retrieval algorithm

1. Embed the question.
2. Build cosine-distance expression against `DocumentChunk.embedding`.
3. Retrieve semantic candidates scoped to workspace and ready documents.
4. Retrieve lexical candidates using `to_tsvector('english', content)` and `plainto_tsquery`.
5. Normalize lexical rank against the maximum returned lexical score.
6. Merge candidate maps by chunk ID.
7. Normalize chunk text and suppress exact normalized duplicates.
8. Compute `0.75 * semantic + 0.25 * keyword`.
9. Keep scores >= 0.12.
10. Sort descending and select up to `RETRIEVAL_TOP_K` (default 5).
11. Build citation objects and context lines.
12. Generate grounded answer or return a no-relevant-passages response.

## 7. Chat persistence

- A new conversation is created when no conversation ID is supplied.
- A supplied conversation must belong to the same workspace and current user.
- User and assistant messages are persisted.
- Citation metadata is returned in the chat response and persisted with assistant message.
- Conversation list and message-history endpoints support frontend history.

## 8. Exact count behavior

The exact-count endpoint extracts the complete source document and counts a requested term rather than counting only retrieved chunks. Word-like terms use case-insensitive whole-word matching; phrases/punctuation use case-insensitive literal substring matching. PDF page-level counts are returned. TXT content has no PDF page numbers.

## 9. Important operational invariants

- Never accept a client-supplied storage path; storage keys are generated server-side.
- Always scope document/chunk queries by workspace.
- Do not mark a document ready before chunks and embeddings are committed.
- Do not acknowledge a valid Kafka event before durable processing or confirmed DLQ finalization.
- Do not log bearer tokens, passwords, secret keys or raw document contents.
- Do not use destructive volume commands to resolve application-level issues.
