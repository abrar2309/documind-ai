# Demo Recording and Portfolio Walkthrough

## 1. Goal

Record a truthful 6–9 minute walkthrough showing the running local application, its architecture, a real upload-to-answer flow, and the repository documentation. This is a local demonstration unless a separately verified public deployment is completed.

## 2. Before recording

- Run the application and verify all six Compose services.
- Confirm Ollama is running and check installed models with `ollama list`.
- Open frontend at `http://localhost:3000`.
- Open architecture page `docs/architecture/HLD.md` and system design page.
- Prepare a synthetic, non-confidential PDF with facts and page numbers.
- Run the backend test suite and health checks; save fresh sanitized outputs.
- Close unrelated tabs, notifications, terminals containing secrets and personal files.
- Use a demo account/workspace. Do not show passwords, tokens, .env, private documents or account identifiers.

## 3. OBS setup

1. Install OBS Studio from the official OBS website.
2. Create a scene named `DocuMind Demo`.
3. Add Display Capture (or Window Capture), and Audio Input Capture for microphone.
4. Set canvas/output resolution to 1920×1080 and 30 FPS if the machine supports it.
5. Use MKV recording for crash resilience; remux to MP4 in OBS after recording.
6. Make a 20-second test recording and verify microphone clarity.
7. Keep the cursor deliberate and zoom browser text enough to read.

## 4. Suggested timeline and narration

### 00:00–00:35 — Introduction
“Hi, this is DocuMind AI, a document intelligence application. It lets users upload supported PDF and text documents into a workspace, process them asynchronously, and ask questions grounded in retrieved document passages. I’ll show the application, the ingestion and retrieval architecture, and the engineering decisions behind it.”

### 00:35–01:35 — Architecture
Show the HLD diagram.
“The frontend is a React and TypeScript application served through Nginx. Nginx proxies API requests to FastAPI. PostgreSQL stores application data and document chunks, with pgvector supporting semantic retrieval. Redis supports caching and rate limiting. Upload processing is decoupled through an outbox, Kafka and a worker. Ollama provides local embedding and answer-generation inference in this development setup.”

### 01:35–02:20 — Authentication and workspace
Show login and workspace selection without exposing credentials.
“Users authenticate and work within a workspace. Workspace membership is checked on workspace-scoped operations. This boundary is important because document retrieval must not mix content across workspaces.”

### 02:20–03:25 — Upload and processing
Upload the synthetic PDF and show its processing status changing to ready.
“When a supported file is uploaded, the API validates the file and permissions, stores the original, and commits document metadata together with an outbox event. The dispatcher publishes that event to Kafka. The worker consumes it, extracts text, creates overlapping chunks, obtains embeddings, and persists the chunk records. The document becomes ready after successful persistence.”

### 03:25–04:55 — RAG question and citations
Ask a question whose answer is explicitly in the fixture. Show answer and citations.
“For a question, the backend embeds the query and retrieves candidates using both vector similarity and PostgreSQL full-text search. It fuses the candidate scores, removes duplicate excerpts and passes selected context to the language model. The response includes citation metadata so the user can inspect which document passage supported the answer. This is retrieval-augmented generation; the model is instructed to use the supplied excerpts and acknowledge when the source does not contain an answer.”

### 04:55–05:35 — Exact count and history
Show conversation history and exact-count feature if it has been verified in the current UI.
“The application also persists conversations and supports document-wide exact term or phrase counting. Exact count is different from RAG retrieval: it scans the full extracted source text rather than relying only on a small set of retrieved chunks.”

### 05:35–06:30 — Engineering and operations
Show repository folders, tests and Compose services.
“The system separates the synchronous API from expensive document processing. The transactional outbox addresses the database-and-message dual-write problem, and worker deduplication makes repeated event delivery safe. The local broker is a single-broker development topology, not a highly available production Kafka cluster.”

### 06:30–07:20 — Tests and limitations
Show sanitized test report.
“The recorded backend test run completed with 32 passing tests and one warning in the local Docker environment. The health smoke test also returned successful responses for the checked endpoints. These results are scoped to the recorded local environment. Scanned-PDF OCR is not implemented, and this repository does not claim a public AWS deployment.”

### 07:20–08:00 — Close
Show GitHub repository and documentation index.
“The repository includes the HLD, LLD, system design, data model, API reference, test plan, evidence register, AWS deployment guide and operations checklist. The next steps are to complete browser acceptance evidence and, if budget permits, deploy a separately verified cloud demo. Thank you.”

## 5. Demo questions for synthetic fixture

Use questions with known answers:
- “What is the project name?”
- “What is the approved budget?”
- “How many engineers are on the team?”
- “Which database technology is specified?”
- “What are the three project phases?”
- “Does the document specify an office location?” (Expected: it does not.)

Do not stage fabricated answers or citations. If a response is incorrect, record it as a defect and investigate rather than editing the evidence.

## 6. After recording

- Review the entire video and confirm audio is intelligible.
- Blur/redact sensitive information.
- Export MP4.
- Upload to an appropriate video host or attach it to the portfolio.
- Add the real video URL to the README only after upload and playback verification.
- Keep a copy of the final test evidence and recording date/commit SHA.
