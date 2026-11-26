from __future__ import annotations
import math
from typing import Iterable

def _ids(values: Iterable[str], field: str) -> list[str]:
    if values is None:
        return []
    if isinstance(values, (str, bytes)):
        raise ValueError(f"{field} must be an array of string IDs, not a string.")
    result = []
    for value in values:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field} must contain only non-empty string IDs.")
        result.append(value.strip())
    return result

def retrieval_metrics(retrieved_ids: Iterable[str], relevant_ids: Iterable[str], k: int = 5) -> dict:
    if isinstance(k, bool) or not isinstance(k, int) or k < 1:
        raise ValueError("k must be an integer of at least 1")
    retrieved = list(dict.fromkeys(_ids(retrieved_ids, "retrieved_ids")))[:k]
    relevant = set(_ids(relevant_ids, "relevant_ids"))
    hits = [rank for rank, item in enumerate(retrieved, 1) if item in relevant]
    dcg = sum(1.0 / math.log2(rank + 1) for rank in hits)
    ideal_hits = min(len(relevant), k)
    idcg = sum(1.0 / math.log2(rank + 1) for rank in range(1, ideal_hits + 1))
    return {
        "k": k, "retrieved_count": len(retrieved), "relevant_count": len(relevant),
        "relevant_retrieved": len(hits), "precision_at_k": len(hits) / k,
        "recall_at_k": len(hits) / len(relevant) if relevant else 0.0,
        "reciprocal_rank": 1.0 / hits[0] if hits else 0.0,
        "hit_rate": 1.0 if hits else 0.0, "ndcg_at_k": dcg / idcg if idcg else 0.0,
    }

def citation_alignment(cited_chunk_ids: Iterable[str], retrieved_chunk_ids: Iterable[str]) -> dict:
    cited = list(dict.fromkeys(_ids(cited_chunk_ids, "cited_chunk_ids")))
    retrieved = set(_ids(retrieved_chunk_ids, "retrieved_chunk_ids"))
    aligned = sum(1 for item in cited if item in retrieved)
    return {"cited_count": len(cited), "aligned_citations": aligned,
            "citation_alignment_precision": aligned / len(cited) if cited else 0.0}

def evaluate_records(records: Iterable[dict], k: int = 5) -> dict:
    rows = list(records)
    if not rows:
        return {"cases": 0, "precision_at_k": 0.0, "recall_at_k": 0.0,
                "mrr": 0.0, "hit_rate": 0.0, "ndcg_at_k": 0.0,
                "citation_alignment_precision": 0.0, "answer_support_rate": None,
                "answer_support_labeled_cases": 0}
    retrieval = [retrieval_metrics(r.get("retrieved_chunk_ids", []), r.get("relevant_chunk_ids", []), k) for r in rows]
    citation = [citation_alignment(r.get("cited_chunk_ids", []), r.get("retrieved_chunk_ids", [])) for r in rows]
    support = [r["answer_supported"] for r in rows if isinstance(r.get("answer_supported"), bool)]
    n = len(rows)
    return {"cases": n,
            "precision_at_k": sum(x["precision_at_k"] for x in retrieval) / n,
            "recall_at_k": sum(x["recall_at_k"] for x in retrieval) / n,
            "mrr": sum(x["reciprocal_rank"] for x in retrieval) / n,
            "hit_rate": sum(x["hit_rate"] for x in retrieval) / n,
            "ndcg_at_k": sum(x["ndcg_at_k"] for x in retrieval) / n,
            "citation_alignment_precision": sum(x["citation_alignment_precision"] for x in citation) / n,
            "answer_support_rate": sum(support) / len(support) if support else None,
            "answer_support_labeled_cases": len(support),
            "evaluation_note": "Citation alignment checks ID membership only, not semantic faithfulness or factual correctness. answer_support_rate is meaningful only for human-reviewed boolean labels."}
