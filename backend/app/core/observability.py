
import logging
import re
import uuid
from contextvars import ContextVar
from typing import Any
from redis.exceptions import RedisError
from app.core.redis_client import get_redis

logger = logging.getLogger(__name__)
METRICS_KEY = "documind:ops:metrics:v1"
_request_id: ContextVar[str] = ContextVar("documind_request_id", default="")

def current_request_id() -> str:
    return _request_id.get()

def set_request_id(value: str):
    return _request_id.set(value)

def reset_request_id(token) -> None:
    _request_id.reset(token)

def make_request_id(incoming: str | None) -> str:
    candidate = (incoming or "").strip()
    if candidate and len(candidate) <= 64 and re.fullmatch(r"[A-Za-z0-9._-]+", candidate):
        return candidate
    return uuid.uuid4().hex

async def add_metric(name: str, amount: float = 1) -> None:
    try:
        client = get_redis()
        await client.hincrbyfloat(METRICS_KEY, name, amount)
        await client.expire(METRICS_KEY, 60 * 60 * 24 * 30)
    except RedisError:
        logger.warning("Could not record operational metric %s", name, exc_info=True)

async def record_llm_usage(provider: str, operation: str, latency_ms: float,
                           input_tokens: int | None = None, output_tokens: int | None = None,
                           estimated_cost_usd: float | None = None) -> None:
    prefix = f"llm.{provider}.{operation}"
    await add_metric(f"{prefix}.calls", 1)
    await add_metric(f"{prefix}.latency_ms_total", max(0, latency_ms))
    if input_tokens is not None: await add_metric(f"{prefix}.input_tokens", max(0, input_tokens))
    if output_tokens is not None: await add_metric(f"{prefix}.output_tokens", max(0, output_tokens))
    if estimated_cost_usd is not None: await add_metric(f"{prefix}.estimated_cost_usd", max(0, estimated_cost_usd))

async def set_metric(name: str, value: float) -> None:
    try:
        client = get_redis()
        await client.hset(METRICS_KEY, name, value)
        await client.expire(METRICS_KEY, 60 * 60 * 24 * 30)
    except RedisError:
        logger.warning("Could not set operational metric %s", name, exc_info=True)

async def metrics_snapshot() -> dict[str, Any]:
    try:
        values = await get_redis().hgetall(METRICS_KEY)
        return {key: float(value) for key, value in values.items()}
    except RedisError:
        logger.warning("Could not read operational metrics", exc_info=True)
        return {"status": "unavailable"}
