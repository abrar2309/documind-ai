import pytest

from app.api.routes.documents import _count_document_pages, _extract_count_term


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        ("How many times does the word ball appear in the entire document?", "ball"),
        ("Count the word YOLO across the document", "yolo"),
        ("How often is optical flow mentioned?", "optical flow"),
        ("Count occurrences of the phrase ball acquisition in the document", "ball acquisition"),
        ("What is optical flow?", None),
        ("Summarize the document", None),
    ],
)
def test_count_intent_detection(question, expected):
    assert _extract_count_term(question) == expected


def test_exact_counter_uses_whole_word_case_insensitive_matching():
    pages = [(1, "Ball ball football BALL. ball-like.")]
    result = _count_document_pages(pages, "ball")
    assert result["count"] == 3
    assert result["counting_mode"] == "whole_word_case_insensitive"


def test_exact_counter_uses_same_phrase_rule_everywhere():
    pages = [(1, "Optical flow, optical flow; optical-flow.")]
    result = _count_document_pages(pages, "optical flow")
    assert result["count"] == 2
    assert result["counting_mode"] == "literal_substring_case_insensitive"


def test_exact_counter_is_case_insensitive_for_phrase():
    pages = [(1, "YOLO yolo Yolo")]
    result = _count_document_pages(pages, "yolo")
    assert result["count"] == 3