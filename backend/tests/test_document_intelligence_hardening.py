import pytest

from app.api.routes.documents import _asks_about_recent_document
from app.services.document_pipeline import SYSTEM_PROMPT
from app.workers.document_worker import is_retryable_error
import httpx


@pytest.mark.parametrize(
    "question",
    [
        "What does my recently uploaded document contain?",
        "Summarize the latest uploaded file",
        "Analyze the document I just uploaded",
        "Tell me about the last uploaded document",
    ],
)
def test_recent_upload_language_is_detected(question):
    assert _asks_about_recent_document(question) is True


@pytest.mark.parametrize(
    "question",
    [
        "Summarize all documents in this workspace",
        "Compare the two football reports",
        "What is the project objective?",
    ],
)
def test_general_questions_do_not_implicitly_select_latest_document(question):
    assert _asks_about_recent_document(question) is False


def test_grounded_prompt_requires_evidence_review_and_scope_honesty():
    assert "Read every excerpt" in SYSTEM_PROMPT
    assert "Never claim that the document lacks information" in SYSTEM_PROMPT
    assert "reasonable inferences" in SYSTEM_PROMPT
    assert "not a complete review" in SYSTEM_PROMPT


def test_network_transport_failures_are_retryable():
    request = httpx.Request("GET", "http://kafka.invalid")
    assert is_retryable_error(httpx.ConnectError("connection refused", request=request))


def test_invalid_document_input_is_not_retryable():
    assert is_retryable_error(ValueError("invalid PDF")) is False
