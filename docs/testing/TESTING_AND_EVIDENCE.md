# Testing, Verification and Evidence Register

This document separates recorded local verification from tests that still need to be run for a release. Evidence below is based on the project work recorded on 27 November 2026; it is not a cloud deployment certificate.

## 1. Recorded evidence

| Check | Recorded result | Scope / qualification |
|---|---|---|
| Backend automated tests in Docker | 32 passed, 1 warning | Ran inside `document-intelligence-backend`; temporary `TRUSTED_HOSTS=localhost,127.0.0.1,testserver` was applied only to the pytest process |
| HTTP smoke tests | 7/7 HTTP 200 | Local endpoints: backend root, health, DB health, Redis health, metrics, docs and frontend |
| Six Compose containers | Running at inspection | Backend, PostgreSQL, frontend, worker, Kafka and Redis; backend/Postgres/Kafka/Redis reported healthy |
| Kafka consumer group | Active consumer; lag 0 | Topic `documind.document.ingest`, partition 0 at the time inspected; not proof that a new end-to-end upload succeeded |
| Redis server ping | PONG | Redis container responds |
| Worker-to-Redis ping | True | Worker container could ping Redis at time checked |
| GitHub docs | README and verification doc previously published | See repository history and links |

The test warning was a Starlette/httpx TestClient deprecation warning. A separate Windows-host test run had environment-specific issues (TestClient hostname and Docker-only Redis hostname); the recorded 32-pass result is from the Docker backend container with a per-process trusted-host override.

## 2. Reproduce backend tests safely

From the active runtime Compose directory, first inspect the compose project and containers. The known active runtime directory in the developer's environment was `C:\AI-Document-Intelligence`; verify it still exists before using it.

```powershell
docker exec -e TRUSTED_HOSTS=localhost,127.0.0.1,testserver document-intelligence-backend python -m pytest -q
```

Expected recorded result: 32 passed, 1 warning. Results may change as source changes.

Do not run destructive database or volume reset commands. The test harness must use its dedicated test database; inspect `backend/tests/conftest.py` before running tests and never point test fixtures at the development database.

## 3. Reproduce local health checks

```powershell
$urls = @(
  "http://localhost:8000/",
  "http://localhost:8000/health",
  "http://localhost:8000/health/db",
  "http://localhost:8000/health/redis",
  "http://localhost:8000/ops/metrics",
  "http://localhost:8000/docs",
  "http://localhost:3000/"
)
foreach ($url in $urls) {
  try {
    $r = Invoke-WebRequest -Uri $url -UseBasicParsing
    [PSCustomObject]@{ Url=$url; Status=[int]$r.StatusCode; Result="PASS" }
  } catch {
    [PSCustomObject]@{ Url=$url; Status=$_.Exception.Response.StatusCode.value__; Result="FAIL" }
  }
}
```

Previously recorded result: all seven returned HTTP 200. Re-run before using this as current release evidence.

## 4. Additional acceptance evidence still required

The following must be demonstrated in the current UI/runtime before claiming complete end-to-end RAG acceptance:
- Sign in using an existing account.
- Open an existing workspace.
- Upload a synthetic non-sensitive PDF or UTF-8 TXT.
- Observe processing -> ready.
- Confirm page/chunk metadata.
- Ask a question whose answer exists in the uploaded test file.
- Verify the answer and citation filename/page/excerpt.
- Ask a question absent from the file and inspect abstention behavior.
- Verify conversation history.
- Verify exact-count output against a known test string.
- Verify delete/re-index only on a disposable test document.
- Test cross-workspace access denial with a second authorized test identity/workspace, if available.

Do not claim these tests passed until recorded.

## 5. Evidence capture checklist

Store sanitized evidence under `docs/evidence/` only after reviewing it:
- `backend-tests.txt`: command and full pass/fail summary.
- `health-smoke-test.txt`: URLs/status codes, no secrets.
- `containers.txt`: service names/status/health.
- `kafka-consumer.txt`: topic, partition, current offset, log-end offset and lag.
- `rag-acceptance.md`: test document name, questions, expected/actual outcomes and citation checks.
- `screenshots/`: sanitized browser screenshots.
- `demo-link.md`: final video URL once uploaded.

Never commit .env files, bearer tokens, passwords, JWTs, personal documents, raw production data or unredacted logs. Redact hostnames/IPs if they expose sensitive infrastructure.

## 6. Release evidence rules

A test report must identify date, environment, commit SHA, command, result and known limitations. A health endpoint returning 200 proves only that endpoint responded; it does not prove ingestion, retrieval quality, high availability or cloud readiness.
