# API Reference (Current Source Contract)

Base path: `/api/v1`. The OpenAPI document at `/openapi.json` is the runtime contract when API docs are enabled.

## Authentication

| Method | Path | Purpose |
|---|---|---|
| POST | `/auth/register` | Register user |
| POST | `/auth/login` | Issue access and refresh tokens |
| POST | `/auth/refresh` | Rotate refresh token and issue new tokens |
| POST | `/auth/logout` | Revoke refresh token |

Protected requests use `Authorization: Bearer <access_token>`.

## Users and workspaces

| Method | Path | Purpose |
|---|---|---|
| GET | `/users/me` | Current user |
| POST | `/workspaces` | Create workspace |
| GET | `/workspaces` | List current user's workspaces |
| GET | `/workspaces/{workspace_id}/members` | List workspace members |
| POST | `/workspaces/{workspace_id}/members` | Add member (manager permission) |
| PATCH | `/workspaces/{workspace_id}/members/{user_id}` | Update member role |
| DELETE | `/workspaces/{workspace_id}/members/{user_id}` | Remove member |

## Documents and RAG

| Method | Path | Purpose |
|---|---|---|
| POST | `/workspaces/{workspace_id}/documents` | Upload PDF/TXT; HTTP 202 |
| GET | `/workspaces/{workspace_id}/documents` | List workspace documents |
| DELETE | `/workspaces/{workspace_id}/documents/{document_id}` | Delete source and associated records |
| POST | `/workspaces/{workspace_id}/documents/{document_id}/reindex` | Rebuild index |
| GET | `/workspaces/{workspace_id}/documents/{document_id}/exact-count?term=...` | Count term/phrase in full document |
| POST | `/workspaces/{workspace_id}/chat` | Ask question; returns answer and citations |
| GET | `/workspaces/{workspace_id}/conversations` | List conversations |
| GET | `/workspaces/{workspace_id}/conversations/{conversation_id}/messages` | Retrieve message history |

The agent router is mounted under the API router. Inspect the current OpenAPI schema and agent route source for its exact request/response contract before integrating clients.

## Key request/response details

### Upload
- Content type: multipart/form-data.
- Required field: `file`.
- Supported: PDF and UTF-8 TXT.
- Maximum: 20 MiB.
- Returns document metadata with status initially processing.
- Poll list endpoint until status is ready or failed.

### Chat
Request:
```json
{
  "question": "What is the approved project budget?",
  "conversation_id": null
}
```

The question length contract is 2–8000 characters. Conversation ID is optional.

Response includes:
- `conversation_id`
- `answer`
- `citations[]`: document_id, filename, chunk_id, page_number, excerpt, score.

## Operational endpoints

The current application exposes:
- `GET /`
- `GET /health`
- `GET /health/db`
- `GET /health/redis`
- `GET /ops/metrics`
- `GET /docs` and `GET /openapi.json` when enabled by configuration.

Do not expose interactive API docs publicly in production unless explicitly protected and required.
