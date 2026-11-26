# DocuMind Stage 4 Week 5 â€” Evaluation and operational readiness

## Offline retrieval evaluation
The evaluator computes Precision@K, Recall@K, MRR, Hit Rate, nDCG@K, citation-ID alignment precision, and optional human-labeled answer support rate.

Citation-ID alignment verifies only that cited chunk IDs occur in the retrieved set. It does NOT establish semantic faithfulness, entailment, factual correctness, or absence of hallucinations. `answer_supported` must be assigned by a human reviewer.

## Dataset
Copy `retrieval_eval_template.jsonl` to a private dataset and replace placeholders with actual chunk IDs and reviewed labels. Each JSONL record uses:
- `retrieved_chunk_ids`: ordered retrieved IDs
- `relevant_chunk_ids`: human-reviewed relevant IDs
- `cited_chunk_ids`: IDs actually cited
- optional `answer_supported`: human-reviewed boolean
- optional `case_id` and `query` (avoid sensitive content)

Never publish customer documents, private queries, tokens, personal information, or proprietary chunk text.

## Run in backend container
```powershell
docker exec document-intelligence-backend python -m app.evaluation.run_retrieval_eval /app/evaluation/retrieval_eval_template.jsonl --k 5
```
Use `--strict` to require at least one case, `--output /tmp/report.json` to save a report, and `--metric mrr --fail-below 0.60` for a regression threshold (exit code 2 on failure).

## Operational counters
The shared Redis metrics hash includes Kafka lag, worker messages received, worker processing attempt failures, terminal failures, DLQ sends, outbox publishes/failures, LLM provider/operation calls, latency, token counts, configured estimated cost, and agent capacity rejections.

`/ops/metrics` returns application counters, not Prometheus format. DLQ sent and failure counters are cumulative, not current queue depth or necessarily active incidents. Compare snapshots over time.

## Cost configuration
Optional `.env` prices are USD per million tokens: `OPENAI_INPUT_COST_PER_1M`, `OPENAI_OUTPUT_COST_PER_1M`, `OPENAI_EMBEDDING_COST_PER_1M`. Defaults are zero; no price is assumed. Ollama local inference records latency and returned token counts when available, but no monetary cost is invented.

## Agent concurrency
`AGENT_MAX_CONCURRENT` is a per-backend-process semaphore, not a distributed global limit. With multiple replicas, aggregate concurrency can multiply by replica count.

## Safety
The patch does not run pytest, migrations, database commands, Kafka commands, document reindexing, or Docker volume operations. Current `tests/conftest.py` drops and recreates `document_intelligence_test_run_20261125`; do not run pytest until that test database is explicitly confirmed disposable.
