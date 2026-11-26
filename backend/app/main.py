from contextlib import asynccontextmanager
import time

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.router import api_router
from app.api.routes.ops import router as ops_router
from app.core.config import settings
from app.core.observability import (
    add_metric,
    make_request_id,
    reset_request_id,
    set_request_id,
)
from app.core.rate_limit import enforce_rate_limit
from app.core.redis_client import close_redis
from app.database.session import engine, get_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await close_redis()
    await engine.dispose()


production = settings.ENVIRONMENT.lower() == "production"
docs_url = None if production or not settings.EXPOSE_API_DOCS else "/docs"
redoc_url = None if production or not settings.EXPOSE_API_DOCS else "/redoc"
openapi_url = None if production or not settings.EXPOSE_API_DOCS else "/openapi.json"

app = FastAPI(
    title=settings.APP_NAME,
    description="Multi-tenant AI-powered document intelligence platform",
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url=docs_url,
    redoc_url=redoc_url,
    openapi_url=openapi_url,
)

allowed_origins = [
    origin.strip()
    for origin in settings.CORS_ALLOWED_ORIGINS.split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    expose_headers=["X-Request-ID", "Retry-After"],
)

trusted_hosts = [
    host.strip()
    for host in settings.TRUSTED_HOSTS.split(",")
    if host.strip()
]
app.include_router(api_router)
app.include_router(ops_router)


@app.middleware("http")
async def distributed_rate_limit_and_security_middleware(request: Request, call_next):
    request_id = make_request_id(request.headers.get("x-request-id"))
    token = set_request_id(request_id)
    started = time.perf_counter()
    status_code = 500
    try:
        request_host = (request.url.hostname or "").lower()
        # ALB target-group health probes use an IP-based Host header; exempt only
        # the unauthenticated liveness endpoint and enforce hosts for all app routes.
        invalid_host = (
            bool(trusted_hosts)
            and request_host not in trusted_hosts
            and request.url.path != "/health"
        )
        limited = (421, "Unrecognized host", {}) if invalid_host else await enforce_rate_limit(request)
        if limited is not None:
            status_code, detail, headers = limited
            response = JSONResponse(
                status_code=status_code,
                content={"detail": detail},
                headers=headers,
            )
        else:
            response = await call_next(request)
            status_code = response.status_code

        response.headers["X-Request-ID"] = request_id
        if settings.ENABLE_SECURITY_HEADERS:
            response.headers.setdefault("X-Content-Type-Options", "nosniff")
            response.headers.setdefault("X-Frame-Options", "DENY")
            response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
            response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
            response.headers.setdefault("Cache-Control", "no-store")
            response.headers.setdefault("Cross-Origin-Resource-Policy", "same-site")
            forwarded_proto = request.headers.get("x-forwarded-proto", "").split(",")[0].strip()
            if settings.ENABLE_HSTS and (
                request.url.scheme == "https" or forwarded_proto == "https"
            ):
                response.headers.setdefault(
                    "Strict-Transport-Security",
                    "max-age=31536000; includeSubDomains",
                )
        return response
    finally:
        elapsed_ms = (time.perf_counter() - started) * 1000
        await add_metric("http.requests.total", 1)
        await add_metric(f"http.responses.{status_code}", 1)
        await add_metric("http.request.duration_ms_total", elapsed_ms)
        reset_request_id(token)


@app.get("/")
async def root():
    return {"message": settings.APP_NAME, "status": "running"}


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.get("/health/db")
async def database_health(db: AsyncSession = Depends(get_db)):
    result = await db.execute(text("SELECT 1"))
    return {"database": "connected", "result": result.scalar_one()}
