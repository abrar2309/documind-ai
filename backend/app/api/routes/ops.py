import time
from fastapi import APIRouter
from app.core.redis_client import redis_health
from app.core.observability import metrics_snapshot
router=APIRouter(tags=["Operations"])
_started=time.time()
@router.get("/health/redis")
async def health_redis(): return await redis_health()
@router.get("/ops/metrics")
async def metrics():
    return {"service":"documind-backend","uptime_seconds":round(time.time()-_started,2),"metrics_scope":"application counters; not Prometheus format","counters": await metrics_snapshot()}
