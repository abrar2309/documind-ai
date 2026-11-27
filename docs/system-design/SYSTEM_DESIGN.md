# System Design — DocuMind AI

## 1. Problem statement

Build a multi-user document intelligence service that accepts supported documents, indexes their content and answers natural-language questions with traceable source passages.

## 2. Functional requirements

1. Register and authenticate users.
2. Create and list workspaces.
3. Manage workspace membership and roles.
4. Upload, list, delete and re-index PDF/TXT documents.
5. Extract text and retain PDF page metadata.
6. Generate embeddings and store searchable chunks.
7. Ask questions against a workspace's ready documents.
8. Return grounded answers and citations.
9. Persist conversations and message history.
10. Count exact terms/phrases across complete source documents.
11. Provide an agent endpoint (inspect its implementation and contract before describing specific tool capabilities).

## 3. Non-functional requirements and design targets

These are design goals, not measured service-level objectives:
- Tenant isolation: no cross-workspace retrieval.
- Durability: persist source metadata and conversation history.
- Reliability: outbox-based event publication, idempotent worker processing, retry and DLQ.
- Security: JWT auth, role checks, input validation, safe secret handling and HTTPS in cloud.
- Observability: request IDs, health routes and metrics hooks.
- Responsiveness: keep expensive extraction/embedding outside the upload HTTP request.
- Cost control: local Ollama for local demo; stop cloud resources when not in use.

No production throughput, latency SLO, availability percentage or capacity benchmark is claimed by this document.

## 4. API design

All application routes are mounted under `/api/v1`. See [API.md](../API.md). The frontend uses a typed API client and bearer access token; it attempts refresh on 401 when a refresh token exists.

## 5. Data and indexing design

The relational database is the system of record. Documents and chunks carry workspace IDs. Original files are persisted in a mounted storage volume. Chunk embeddings are 384-dimensional. Chunk size/overlap are configuration-driven (current defaults 900/150 characters).

## 6. Retrieval design

Hybrid retrieval uses:
- Semantic candidate search with pgvector cosine distance.
- Lexical candidate search with PostgreSQL English full-text search.
- Rank fusion: 75% semantic, 25% normalized lexical score.
- Duplicate-excerpt suppression.
- Minimum fused score 0.12.
- Up to five selected passages by default.

The weights and threshold are implementation defaults, not a claim of benchmark optimality. Evaluate with a labeled question/document set before tuning.

## 7. Reliability and failure handling

| Failure | Current mechanism / expected behavior |
|---|---|
| API process restarts | Durable DB records and outbox rows remain |
| Kafka temporarily unavailable | Unpublished outbox rows can be retried by dispatcher |
| Duplicate Kafka delivery | Processed-event marker prevents duplicate work |
| Transient provider/network failure | Retry policy with exponential delay |
| Terminal/exhausted processing failure | Document failed state and DLQ publication |
| Redis unavailable | Rate-limit fail-open behavior is configurable; review production setting |
| Ollama unavailable | Embedding/generation request fails; ingestion retry path applies to worker provider calls |
| Invalid or unsupported file | API rejects request before ingestion |

At-least-once event delivery with idempotent processing is the appropriate mental model; do not claim exactly-once end-to-end execution.

## 8. Security model

- Passwords are hashed; never store plaintext passwords.
- Access tokens are short-lived and refresh tokens are tracked/revocable.
- Workspace membership gates access.
- Viewer role is blocked from upload/delete/re-index.
- File extension and MIME type must match the supported pair; PDF signature is checked.
- File size is capped at 20 MiB.
- The LLM prompt treats document excerpts as untrusted content.
- Production configuration validates secret length, HTTPS origins, explicit trusted hosts, disabled docs and fail-closed rate limiting.
- Add rate limits, quotas, audit trails, malware scanning, object-store encryption, secrets manager and backup/restore tests before public production use.

## 9. Capacity planning approach

Do not invent capacity numbers. Measure:
- Average and p95 upload size.
- Pages and extracted characters per file.
- Chunks per document.
- Embedding throughput and model memory.
- Worker processing duration and Kafka lag.
- Chat request latency split into embedding, retrieval and generation.
- PostgreSQL CPU, memory, storage, connection count and vector query latency.
- Redis hit rate and memory.
- Per-user/workspace request and storage usage.

Estimate storage as original-file bytes + extracted chunk text + vector storage + indexes + database overhead + backups. Vector payload alone is approximately 4 bytes × 384 dimensions per vector before row/index overhead.

## 10. Scaling strategy

- API: stateless replicas behind ALB; shared PostgreSQL/Redis and externalized files.
- Workers: scale consumers and partitions based on lag and processing throughput; do not exceed useful partition parallelism.
- Database: connection pool limits, query plans, backups, index selection and read replicas only when justified.
- Vector retrieval: benchmark exact vs approximate indexes on representative data before choosing HNSW/IVFFlat settings.
- Broker: multi-broker cluster and replication for production availability.
- AI: separate inference capacity, bounded concurrency, timeouts, quotas and provider fallback strategy.
- Files: private object storage with lifecycle policies.

## 11. Trade-offs

- Local Ollama avoids hosted inference charges but ties latency and throughput to local hardware.
- pgvector simplifies architecture but couples vector workloads to PostgreSQL.
- Kafka improves decoupling but increases operational complexity.
- Outbox adds a polling/dispatch component but closes the dual-write gap.
- Hybrid retrieval improves coverage but introduces tunable weights and evaluation needs.
- Workspace authorization in application code is flexible but requires comprehensive negative cross-tenant tests.

## 12. Open design questions

- Should OCR be added for scanned PDFs?
- Should files move to S3 for cloud deployment?
- What retention/deletion policy applies to source files and conversations?
- Should PostgreSQL row-level security supplement application checks?
- What are target corpus sizes and query concurrency?
- Which vector index performs best on representative evaluation data?
- Should ingestion support cancellation and per-workspace quotas?
- What are the desired availability, recovery point and recovery time objectives?
