import pytest

from app.services.agent_tools import TOOL_REGISTRY


def test_agent_registry_is_explicit_and_read_only():
    assert set(TOOL_REGISTRY) == {"list_documents", "search_documents", "count_term"}
    assert not any(name in TOOL_REGISTRY for name in ("shell", "python", "sql", "delete_document"))


def test_agent_tool_schemas_reject_additional_properties():
    for tool in TOOL_REGISTRY.values():
        assert tool["parameters"]["additionalProperties"] is False
