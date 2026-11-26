import pytest
from app.evaluation.metrics import citation_alignment, evaluate_records, retrieval_metrics

def test_ndcg_rewards_relevant_results_at_top():
    top = retrieval_metrics(["relevant", "other"], ["relevant"], k=2)
    lower = retrieval_metrics(["other", "relevant"], ["relevant"], k=2)
    assert top["ndcg_at_k"] > lower["ndcg_at_k"]

def test_answer_support_rate_uses_human_boolean_labels():
    report = evaluate_records([
        {"retrieved_chunk_ids": ["a"], "relevant_chunk_ids": ["a"], "cited_chunk_ids": ["a"], "answer_supported": True},
        {"retrieved_chunk_ids": ["b"], "relevant_chunk_ids": ["b"], "cited_chunk_ids": ["b"], "answer_supported": False},
        {"retrieved_chunk_ids": [], "relevant_chunk_ids": [], "cited_chunk_ids": []},
    ])
    assert report["answer_support_rate"] == pytest.approx(0.5)
    assert report["answer_support_labeled_cases"] == 2

def test_empty_relevant_set_has_zero_recall_and_ndcg():
    result = retrieval_metrics(["a"], [], k=3)
    assert result["recall_at_k"] == 0
    assert result["ndcg_at_k"] == 0

def test_id_inputs_must_be_arrays_not_plain_strings():
    with pytest.raises(ValueError):
        retrieval_metrics("chunk-a", ["chunk-a"], k=1)

def test_citation_alignment_remains_membership_only():
    result = citation_alignment(["a", "x"], ["a", "b"])
    assert result["aligned_citations"] == 1
    assert result["citation_alignment_precision"] == pytest.approx(0.5)
