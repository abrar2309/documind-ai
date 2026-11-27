# DocuMind AI — Engineering Documentation

This directory is the engineering handbook for the current repository. It distinguishes implemented behavior, verified local evidence, design recommendations, and future deployment plans.

## Start here

| Document | Purpose |
|---|---|
| [HLD](architecture/HLD.md) | System context, containers, architecture and major decisions |
| [LLD](architecture/LLD.md) | Module responsibilities, request flows and component contracts |
| [System Design](system-design/SYSTEM_DESIGN.md) | Requirements, capacity assumptions, data, reliability, security and trade-offs |
| [Data Model](architecture/DATA_MODEL.md) | Main entities, relationships and indexing |
| [API Reference](API.md) | API routes, authentication and payload outline |
| [Testing & Evidence](testing/TESTING_AND_EVIDENCE.md) | Reproducible checks and evidence status |
| [End-to-End Test Plan](testing/E2E_TEST_PLAN.md) | Browser-driven acceptance test plan |
| [Demo Recording](demo/DEMO_GUIDE.md) | Screen recording plan and narration outline |
| [AWS Deployment](aws/DEPLOYMENT.md) | Cost-aware AWS deployment paths and operations |
| [AWS Security Checklist](aws/SECURITY_CHECKLIST.md) | Cloud security and release gates |
| [Operations Runbook](operations/RUNBOOK.md) | Local operations, diagnosis and recovery |

## Status language

- **Implemented:** visible in the current source/configuration.
- **Verified locally:** supported by a recorded local check; see Testing & Evidence.
- **Planned / deployment guide:** instructions or target design, not evidence that it has been deployed.
- **Not implemented / not verified:** do not represent as a delivered capability.

## Important current boundaries

- Current upload route accepts PDF and UTF-8 TXT, up to 20 MiB.
- Scanned-PDF OCR is not implemented.
- Current local model configuration uses Ollama: `all-minilm` embeddings and `qwen3:1.7b` chat.
- Embedding dimension is 384; chunk size is 900 characters with 150-character overlap; retrieval selects up to five passages.
- Docker Compose defines frontend, backend, PostgreSQL, Redis, Kafka and document-worker services. Ollama runs on the Windows host in the documented local setup.
- The document upload API writes a document and outbox event; a separate worker consumes Kafka events and performs extraction/chunking/embedding.
- AWS deployment and a public live demo are not claimed as completed.

See [Testing & Evidence](testing/TESTING_AND_EVIDENCE.md) for the evidence boundary and dates.
