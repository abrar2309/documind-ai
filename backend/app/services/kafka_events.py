import json
import logging
import uuid
from datetime import datetime, timezone

from aiokafka import AIOKafkaProducer

from app.core.config import settings

logger = logging.getLogger(__name__)


async def publish_document_ingestion(
    document_id: uuid.UUID,
    workspace_id: uuid.UUID,
    requested_by: uuid.UUID,
) -> str:
    """Publish a versioned, minimal event after the document row is committed."""
    event_id = str(uuid.uuid4())
    event = {
        "event_id": event_id,
        "event_type": "document.ingestion.requested",
        "schema_version": 1,
        "document_id": str(document_id),
        "workspace_id": str(workspace_id),
        "requested_by": str(requested_by),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    producer = AIOKafkaProducer(
        bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
        value_serializer=lambda value: json.dumps(
            value, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8"),
        acks="all",
        enable_idempotence=True,
        request_timeout_ms=30000,
    )
    try:
        await producer.start()
        await producer.send_and_wait(
            settings.KAFKA_DOCUMENT_TOPIC,
            event,
            key=str(document_id).encode("utf-8"),
        )
        logger.info(
            "Published document ingestion event",
            extra={"event_id": event_id, "document_id": str(document_id)},
        )
        return event_id
    finally:
        await producer.stop()