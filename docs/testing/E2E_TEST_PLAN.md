# End-to-End Test Plan

## 1. Test objective

Validate the user journey through the actual browser UI and the backend services: authentication, workspace selection, document ingestion, retrieval, citations, history and document operations.

Use synthetic test content only. Do not upload private or confidential documents for a portfolio recording.

## 2. Preconditions

- Docker Compose services are running and healthy.
- Ollama is running on the Windows host.
- Configured models are present: `all-minilm` and `qwen3:1.7b`.
- Frontend opens at `http://localhost:3000`.
- Backend docs open at `http://localhost:8000/docs`.
- An existing account and workspace are available.
- A disposable synthetic PDF/TXT is prepared.
- Browser developer tools are available for diagnosing failed requests.

Do not create a duplicate user/workspace if an existing one is available.

## 3. Synthetic test fixture

Create a short document titled **Project Falcon — Demo Brief** containing these facts:
- Project name: Project Falcon.
- Project manager: Sarah Mitchell.
- Approved budget: 1,250,000 USD.
- Engineering team: 12 engineers.
- Data store: PostgreSQL with pgvector.
- Phases: ingestion, semantic retrieval, answer generation with citations.
- Do not include an office location.

Keep this fixture deterministic so expected answers can be checked. For PDF citation testing, put facts on clearly numbered pages; for a one-page file, expected citation page is 1.

## 4. Browser acceptance scenarios

| ID | Scenario | Expected result |
|---|---|---|
| E2E-01 | Open frontend | Login screen loads without fatal console error |
| E2E-02 | Login with existing account | User reaches dashboard |
| E2E-03 | Open existing workspace | Workspace view loads |
| E2E-04 | Upload synthetic PDF | API accepts supported file; document initially processing |
| E2E-05 | Wait for processing | Document becomes ready; chunk count > 0 |
| E2E-06 | Ask project-name question | Answer matches source and includes citation |
| E2E-07 | Ask budget question | Answer matches 1,250,000 USD and cites source |
| E2E-08 | Ask semantic paraphrase | Relevant passage retrieved even if wording differs |
| E2E-09 | Ask absent office-location question | Assistant acknowledges source lacks the answer; no invented location |
| E2E-10 | Refresh/reopen conversation | Conversation and message history persist |
| E2E-11 | Exact-count test | Count equals known occurrences in complete fixture |
| E2E-12 | Re-index disposable file | Re-index completes and document remains queryable |
| E2E-13 | Delete disposable file | File disappears from listing and associated content is removed |
| E2E-14 | Workspace authorization | Non-member cannot access another workspace's documents/chat |
| E2E-15 | Unsupported file | DOCX or mismatched MIME/extension is rejected |
| E2E-16 | Oversized file | File above 20 MiB is rejected |

Do not perform delete/re-index scenarios on valuable existing documents. Use only the synthetic fixture.

## 5. API-level verification

Use the runtime OpenAPI contract at `/openapi.json`. Authentication:
- `POST /api/v1/auth/login`
- `GET /api/v1/workspaces` with bearer token

Upload:
- `POST /api/v1/workspaces/{workspace_id}/documents`
- multipart field `file`

List:
- `GET /api/v1/workspaces/{workspace_id}/documents`

Chat:
- `POST /api/v1/workspaces/{workspace_id}/chat`
- JSON fields: `question`, optional `conversation_id`

Never paste credentials or tokens into a ticket, chat transcript, screenshot or committed evidence file.

## 6. Pass/fail recording

For each scenario record:
- Date and commit SHA.
- Browser and local environment.
- Test ID.
- Input document and question.
- Expected result.
- Actual result.
- HTTP status/request ID if useful.
- Citation filename/page/excerpt check.
- Pass/fail and defect reference.

## 7. Known limitations

- Scanned PDF OCR is not supported.
- The API's upload response is HTTP 202; wait for the worker to mark the document ready.
- Model generation time depends on host CPU/GPU and Ollama model loading.
- A passing health check or zero Kafka lag is not a substitute for a complete upload-to-answer test.
