
# DocuMind retrieval evaluation

This offline evaluator computes Precision@K, Recall@K, MRR, hit rate and citation-ID alignment.

1. Copy `retrieval_eval_template.jsonl` to a private dataset.
2. Replace placeholders with real chunk IDs returned by DocuMind.
3. Have a human reviewer identify relevant chunk IDs and cited chunk IDs.
4. Run inside the backend container:
   `python -m app.evaluation.run_retrieval_eval /app/evaluation/my_dataset.jsonl --k 5`

Citation alignment does not prove semantic faithfulness, factual correctness or absence of hallucinations.
Those require human-reviewed labels or a separately validated evaluator. Do not put customer documents,
tokens or personal data in a public repository.
