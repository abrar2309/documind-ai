import json
import logging
from typing import Any
from redis.asyncio import Redis
from redis.exceptions import RedisError
from app.core.config import settings
logger=logging.getLogger(__name__)
_client: Redis | None=None
def get_redis() -> Redis:
    global _client
    if _client is None:
        _client=Redis.from_url(settings.REDIS_URL,encoding="utf-8",decode_responses=True,socket_connect_timeout=settings.REDIS_CONNECT_TIMEOUT_SECONDS,socket_timeout=settings.REDIS_CONNECT_TIMEOUT_SECONDS,health_check_interval=30)
    return _client
async def redis_health() -> dict[str,str]:
    try:
        await get_redis().ping(); return {"status":"healthy"}
    except RedisError:
        logger.warning("Redis health check failed",exc_info=True); return {"status":"unavailable"}
async def close_redis() -> None:
    global _client
    if _client is not None:
        await _client.aclose(); _client=None
async def cache_get_json(key: str) -> Any | None:
    try:
        raw=await get_redis().get(key); return json.loads(raw) if raw is not None else None
    except (RedisError,ValueError,TypeError):
        logger.warning("Redis cache read failed",exc_info=True); return None
async def cache_set_json(key: str,value: Any,ttl_seconds: int=60) -> bool:
    try:
        await get_redis().setex(key,ttl_seconds,json.dumps(value,separators=(",",":"),default=str)); return True
    except (RedisError,TypeError,ValueError):
        logger.warning("Redis cache write failed",exc_info=True); return False
async def cache_delete_pattern(pattern: str) -> int:
    try:
        client=get_redis(); deleted=0
        async for key in client.scan_iter(match=pattern,count=200): deleted+=await client.delete(key)
        return deleted
    except RedisError:
        logger.warning("Redis cache invalidation failed",exc_info=True); return 0
