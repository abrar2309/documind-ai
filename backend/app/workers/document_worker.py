import asyncio
import json
import logging
import signal
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import httpx

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from sqlalchemy import delete, select

from app.core.config import settings
from app.core.observability import add_metric, set_metric
from app.core.redis_client import cache_delete_pattern
from app.database.session import AsyncSessionLocal, engine
from app.models.document import Document, DocumentChunk
from app.models.events import OutboxEvent, ProcessedEvent
from app.services.document_pipeline import chunk_pages, embed_texts, extract_text

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("documind.document_worker")


def is_retryable_error(exc: Exception) -> bool:
    """Retry transient provider/network/DB failures, not invalid input or missing files."""
    if isinstance(exc, (ValueError, TypeError, KeyError, FileNotFoundError)):
        return False
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        return status == 429 or status >= 500
    if isinstance(exc, (httpx.TimeoutException, httpx.TransportError)):
        return True
    # Unknown operational failures remain retryable; final failure is sent to the DLQ.
    return True


def validate_event(event: Any) -> tuple[str, uuid.UUID, uuid.UUID, uuid.UUID]:
    if not isinstance(event, dict) or event.get("schema_version") != 1:
        raise ValueError("Unsupported or malformed document event.")
    return (
        str(uuid.UUID(event["event_id"])),
        uuid.UUID(event["document_id"]),
        uuid.UUID(event["workspace_id"]),
        uuid.UUID(event["requested_by"]),
    )


async def process_document(event: dict[str, Any]) -> None:
    event_id, document_id, workspace_id, requested_by = validate_event(event)
    # Inbox marker + document/chunks commit atomically. Crash before commit => Kafka replay.
    async with AsyncSessionLocal() as db:
        async with db.begin():
            if await db.get(ProcessedEvent, event_id) is not None:
                logger.info("Skipping duplicate event %s", event_id)
                return
            document = await db.scalar(
                select(Document).where(
                    Document.id == document_id,
                    Document.workspace_id == workspace_id,
                    Document.uploaded_by == requested_by,
                ).with_for_update()
            )
            if document is None:
                raise ValueError("Document event does not match an existing owned document.")
            if document.status == "ready":
                db.add(ProcessedEvent(event_id=event_id, document_id=document_id))
                logger.info("Document already ready; event recorded as processed")
                return

            document.status = "processing"
            document.error_message = None
            path = Path(settings.STORAGE_ROOT) / str(workspace_id) / document.storage_key
            if not path.is_file():
                raise FileNotFoundError("Stored document file is missing.")
            pages, page_count = extract_text(path, document.content_type)
            chunks = chunk_pages(pages)
            if not chunks:
                raise ValueError("No extractable text was found in this file.")
            vectors = await embed_texts([content for _, _, content in chunks])
            if len(vectors) != len(chunks):
                raise ValueError("Embedding count does not match chunk count.")
            await db.execute(delete(DocumentChunk).where(
                DocumentChunk.document_id == document_id,
                DocumentChunk.workspace_id == workspace_id,
            ))
            for (index, page, content), vector in zip(chunks, vectors):
                db.add(DocumentChunk(
                    document_id=document_id,
                    workspace_id=workspace_id,
                    chunk_index=index,
                    page_number=page,
                    content=content,
                    embedding=vector,
                ))
            document.page_count = page_count
            document.chunk_count = len(chunks)
            document.status = "ready"
            document.error_message = None
            db.add(ProcessedEvent(event_id=event_id, document_id=document_id))
    await add_metric("worker.documents.processed", 1)
    await cache_delete_pattern(f"documind:cache:documents:{workspace_id}:*")
    logger.info("Document ingestion completed", extra={
        "event_id": event_id, "document_id": str(document_id),
        "workspace_id": str(workspace_id), "chunks": len(chunks),
    })


async def set_document_failed(event: Any, error: str) -> None:
    # Propagate DB errors so the caller leaves the Kafka offset uncommitted.
    _event_id, document_id, workspace_id, requested_by = validate_event(event)
    async with AsyncSessionLocal() as db:
        async with db.begin():
            doc = await db.scalar(select(Document).where(
                Document.id == document_id,
                Document.workspace_id == workspace_id,
                Document.uploaded_by == requested_by,
            ).with_for_update())
            if doc is not None and doc.status != "ready":
                doc.status = "failed"
                doc.error_message = error[:1000]

async def dispatch_outbox_once(producer: AIOKafkaProducer) -> int:
    sent = 0
    async with AsyncSessionLocal() as db:
        async with db.begin():
            rows = (await db.scalars(
                select(OutboxEvent)
                .where(OutboxEvent.published_at.is_(None))
                .order_by(OutboxEvent.created_at)
                .limit(25)
                .with_for_update(skip_locked=True)
            )).all()
            for row in rows:
                try:
                    await producer.send_and_wait(
                        row.topic, row.payload,
                        key=str(row.aggregate_id).encode("utf-8"),
                    )
                    row.published_at = datetime.now(timezone.utc)
                    await add_metric("worker.outbox.published", 1)
                    row.attempts += 1
                    row.last_error = None
                    sent += 1
                    logger.info("Outbox event published: %s", row.event_id)
                except Exception as exc:
                    row.attempts += 1
                    await add_metric("worker.outbox.publish_failures", 1)
                    row.last_error = str(exc)[:1000]
                    logger.exception("Outbox publish failed: %s", row.event_id)
    return sent


async def outbox_loop(producer: AIOKafkaProducer, stop: asyncio.Event) -> None:
    idle_delay = 1.0
    while not stop.is_set():
        try:
            published = await dispatch_outbox_once(producer)
            if published:
                idle_delay = 1.0
                continue
            idle_delay = min(30.0, idle_delay * 2.0)
        except Exception:
            logger.exception("Outbox dispatcher iteration failed")
            idle_delay = min(30.0, idle_delay * 2.0)
        try:
            await asyncio.wait_for(stop.wait(), timeout=idle_delay)
        except asyncio.TimeoutError:
            pass


async def send_dlq(producer: AIOKafkaProducer, event: Any, error: str, attempts: int) -> None:
    original = event if isinstance(event, dict) else {"raw": str(event)[:1000]}
    key = str(original.get("document_id") or original.get("event_id") or "malformed")
    await producer.send_and_wait(settings.KAFKA_DOCUMENT_DLQ_TOPIC, {
        "original_event": original,
        "failure": error[:1000],
        "attempts": attempts,
        "failed_at": datetime.now(timezone.utc).isoformat(),
    }, key=key.encode("utf-8"))
    await add_metric("worker.dlq.sent", 1)


async def main() -> None:
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except (NotImplementedError, RuntimeError):
            pass

    consumer = AIOKafkaConsumer(
        settings.KAFKA_DOCUMENT_TOPIC,
        bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
        group_id=settings.KAFKA_CONSUMER_GROUP,
        enable_auto_commit=False,
        auto_offset_reset="earliest",
        value_deserializer=None,
        max_poll_interval_ms=900000,
        session_timeout_ms=30000,
    )
    producer = AIOKafkaProducer(
        bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
        value_serializer=lambda value: json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode("utf-8"),
        acks="all",
        enable_idempotence=True,
    )
    await producer.start()
    await consumer.start()
    outbox_task = asyncio.create_task(outbox_loop(producer, stop))
    logger.info("Document worker started")

    try:
        while not stop.is_set():
            batches = await consumer.getmany(timeout_ms=1000, max_records=1)
            try:
                assigned = consumer.assignment()
                if assigned:
                    ends = await consumer.end_offsets(assigned)
                    lag = 0
                    for partition, end_offset in ends.items():
                        current = await consumer.position(partition)
                        lag += max(0, int(end_offset) - int(current))
                    await set_metric("kafka.consumer_lag_records", lag)
            except Exception:
                logger.debug("Could not refresh Kafka consumer lag metric", exc_info=True)
            for _tp, messages in batches.items():
                for message in messages:
                    await add_metric("worker.consumer.messages_received", 1)
                    try:
                        raw_value = message.value
                        event = json.loads(raw_value.decode("utf-8"))
                    except Exception as decode_exc:
                        event = {"raw": (message.value or b"").decode("utf-8", errors="replace")[:1000]}
                        logger.error("Kafka message JSON decoding failed: %s", decode_exc)
                    event_validated = False
                    try:
                        validate_event(event)
                        event_validated = True
                        attempts = max(1, settings.KAFKA_MAX_RETRIES)
                        for attempt in range(1, attempts + 1):
                            try:
                                await process_document(event)
                                break
                            except Exception as exc:
                                await add_metric("worker.processing.attempt_failures", 1)
                                logger.exception("Processing attempt %s/%s failed", attempt, attempts)
                                permanent_failure = not is_retryable_error(exc)
                                if permanent_failure or attempt == attempts:
                                    await add_metric("worker.processing.terminal_failures", 1)
                                    await set_document_failed(event, str(exc))
                                    await send_dlq(producer, event, str(exc), attempt)
                                    break
                                delay = min(60.0, settings.KAFKA_RETRY_BASE_SECONDS * (2 ** (attempt - 1)))
                                await asyncio.sleep(max(0.1, delay))
                        # Only acknowledge after DB commit or confirmed DLQ publication.
                        await consumer.commit()
                    except Exception as exc:
                        if event_validated:
                            # Never acknowledge a valid event if failure-state persistence,
                            # DLQ publication, or offset commit failed. Kafka must redeliver it.
                            logger.exception(
                                "Validated message could not be finalized; "
                                "leaving offset uncommitted for redelivery"
                            )
                            try:
                                consumer.seek(_tp, message.offset)
                            except Exception:
                                logger.exception("Could not rewind failed message offset; stopping worker for safe redelivery")
                                stop.set()
                            await asyncio.sleep(2)
                        else:
                            # Malformed payloads have no safe document row to update.
                            # Commit only after the DLQ broker confirms publication.
                            logger.exception("Malformed message")
                            try:
                                await send_dlq(producer, event, str(exc), 0)
                                await consumer.commit()
                            except Exception:
                                logger.exception("DLQ unavailable; message will be redelivered")
                                try:
                                    consumer.seek(_tp, message.offset)
                                except Exception:
                                    logger.exception("Could not rewind malformed message offset; stopping worker")
                                    stop.set()
                                await asyncio.sleep(2)
    finally:
        stop.set()
        await outbox_task
        await consumer.stop()
        await producer.stop()
        await engine.dispose()
        logger.info("Document worker stopped")


if __name__ == "__main__":
    asyncio.run(main())