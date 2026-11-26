# Stage 4 Week 4 hardening notes

## Changes
- Redis uses `noeviction` at the existing 256 MB cap. This avoids silently evicting rate-limit and operational counters. Cache writes can fail at capacity; application cache helpers already fail safely. Monitor Redis memory and configure an alert before production.
- Kafka worker classifies invalid payloads, missing files and HTTP 4xx provider responses (except 429) as permanent. Transient HTTP 429/5xx, transport/timeouts and other operational errors are retried with capped exponential delay, then sent to the DLQ.
- Outbox polling backs off up to 30 seconds when nothing is successfully published, rather than polling continuously once per second during a broker outage. Pending rows remain in PostgreSQL.
- Added focused retry-classification unit tests. They are deliberately not executed by this patch.

## Important limits
- Redis `noeviction` protects counters from eviction but can reject writes when memory is full. It is a deliberate fail-visible policy, not a substitute for capacity monitoring.
- The rate limiter still uses the TCP peer address (`request.client.host`). Do not blindly trust `X-Forwarded-For`; configure a trusted reverse proxy that overwrites forwarding headers before introducing proxy-aware client IP handling.
- This patch does not add Prometheus, alerting, a Kafka multi-broker cluster, production secrets management, TLS, cloud deployment, or automated DLQ replay.
- No database schema, Kafka offsets/topics, uploaded documents, chunks, or persistent volumes are changed by the patch.

## Test safety
The existing `tests/conftest.py` drops and recreates tables in the separate database `document_intelligence_test_run_20261125`. Do not run the full test suite until you have confirmed that database is disposable. The focused tests above can be run only after the same safety confirmation because pytest loads the shared conftest.
