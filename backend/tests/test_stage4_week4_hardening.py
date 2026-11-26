import httpx
import pytest
from app.workers.document_worker import is_retryable_error


def test_invalid_event_is_not_retried():
    assert is_retryable_error(ValueError("bad event")) is False


def test_missing_document_file_is_not_retried():
    assert is_retryable_error(FileNotFoundError("missing")) is False


def test_http_429_is_retryable():
    request = httpx.Request("POST", "http://provider.test")
    response = httpx.Response(429, request=request)
    assert is_retryable_error(httpx.HTTPStatusError("rate limited", request=request, response=response)) is True


def test_http_503_is_retryable():
    request = httpx.Request("POST", "http://provider.test")
    response = httpx.Response(503, request=request)
    assert is_retryable_error(httpx.HTTPStatusError("unavailable", request=request, response=response)) is True


def test_http_400_is_permanent():
    request = httpx.Request("POST", "http://provider.test")
    response = httpx.Response(400, request=request)
    assert is_retryable_error(httpx.HTTPStatusError("bad request", request=request, response=response)) is False
