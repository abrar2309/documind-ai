
import pytest
from app.evaluation.metrics import citation_alignment, evaluate_records, retrieval_metrics

def test_retrieval_precision_recall_and_mrr():
    result = retrieval_metrics(["a", "b", "c"], ["b", "c", "d"], k=3)
    assert result["precision_at_k"] == pytest.approx(2 / 3)
    assert result["recall_at_k"] == pytest.approx(2 / 3)
    assert result["reciprocal_rank"] == pytest.approx(1 / 2)
    assert result["hit_rate"] == 1.0

def test_no_relevant_retrieval_hit():
    result = retrieval_metrics(["a"], ["z"], k=1)
    assert result["precision_at_k"] == 0
    assert result["recall_at_k"] == 0
    assert result["reciprocal_rank"] == 0

def test_invalid_k_rejected():
    with pytest.raises(ValueError):
        retrieval_metrics([], [], k=0)

def test_citation_alignment_checks_retrieved_membership_only():
    result = citation_alignment(["a", "missing"], ["a", "b"])
    assert result["aligned_citations"] == 1
    assert result["citation_alignment_precision"] == 0.5

def test_evaluation_aggregates_multiple_cases():
    result = evaluate_records([
        {"retrieved_chunk_ids":["a"],"relevant_chunk_ids":["a"],"cited_chunk_ids":["a"]},
        {"retrieved_chunk_ids":["b"],"relevant_chunk_ids":["z"],"cited_chunk_ids":["z"]},
    ], k=1)
    assert result["cases"] == 2
    assert result["precision_at_k"] == pytest.approx(0.5)
    assert result["mrr"] == pytest.approx(0.5)
