import uuid
import pytest
from app.workers.document_worker import validate_event

def sample():
    return {
        "event_id": str(uuid.uuid4()),
        "schema_version": 1,
        "document_id": str(uuid.uuid4()),
        "workspace_id": str(uuid.uuid4()),
        "requested_by": str(uuid.uuid4()),
    }

def test_valid_event():
    parsed = validate_event(sample())
    assert len(parsed) == 4
    assert all(isinstance(v, uuid.UUID) for v in parsed[1:])

def test_rejects_bad_schema():
    event = sample()
    event["schema_version"] = 9
    with pytest.raises(ValueError):
        validate_event(event)

def test_rejects_missing_event_id():
    event = sample()
    del event["event_id"]
    with pytest.raises((ValueError, KeyError)):
        validate_event(event)