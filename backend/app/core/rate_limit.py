import logging
import time
from fastapi import Request
from redis.exceptions import RedisError
from app.core.config import settings
from app.core.redis_client import get_redis

logger = logging.getLogger(__name__)
SCRIPT = "local n=redis.call('INCR',KEYS[1]); if n==1 then redis.call('EXPIRE',KEYS[1],ARGV[1]) end; return {n,redis.call('TTL',KEYS[1])}"


async def enforce_rate_limit(request: Request) -> tuple[int, str, dict[str, str]] | None:
    # Operational probes are deliberately exempt so monitoring remains usable.
    if request.url.path in ("/", "/health", "/health/db", "/health/redis", "/ops/metrics"):
        return None

    peer = request.client.host if request.client else "unknown"
    window = max(1, settings.RATE_LIMIT_WINDOW_SECONDS)
    bucket = int(time.time()) // window
    key = f"documind:rl:v1:{peer}:{bucket}"
    try:
        result = await get_redis().eval(SCRIPT, 1, key, window + 2)
        if int(result[0]) > settings.RATE_LIMIT_REQUESTS:
            retry_after = str(max(1, int(result[1])))
            return (429, "Rate limit exceeded. Please retry shortly.", {"Retry-After": retry_after})
    except RedisError:
        logger.exception("Distributed rate limiter could not reach Redis")
        if not settings.RATE_LIMIT_FAIL_OPEN:
            return (503, "Rate limiting service unavailable", {})
    return None