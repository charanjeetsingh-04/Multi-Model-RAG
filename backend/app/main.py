"""FastAPI application factory (v2).

Wires:
  * structured logging (with OTel correlation)
  * OTel instrumentation (no-op when endpoint not set)
  * RFC 7807 exception handlers
  * Prometheus instrumentation at /metrics
  * Gateway-aware request-id middleware
"""
from __future__ import annotations

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from prometheus_fastapi_instrumentator import Instrumentator
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging
from app.core.observability import setup_observability
from app.db.session import engine
from app.middleware.rate_limit import limiter
from app.middleware.request_context import RequestContextMiddleware

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    settings.ensure_dirs()
    logger.info(
        "app_starting",
        app=settings.APP_NAME,
        env=settings.APP_ENV,
        version=settings.APP_VERSION,
    )

    # Warm singletons; never raise — cold path will rebuild them on first use.
    from app.cache import get_cache  # noqa: PLC0415
    from app.embeddings.embedder import get_embedder  # noqa: PLC0415
    from app.rag.vector_store import get_vector_store  # noqa: PLC0415

    try:
        get_embedder()
        get_vector_store()
        get_cache()
    except Exception as e:  # noqa: BLE001
        logger.warning("warmup_failed", error=str(e))

    yield

    logger.info("app_shutdown")
    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        debug=settings.APP_DEBUG,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        # Behind a gateway, set root_path via env (UVICORN_ROOT_PATH or --root-path).
    )

    # --- Middleware (outermost first) ---
    app.add_middleware(GZipMiddleware, minimum_size=1024)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "X-Response-Time-ms"],
    )
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(SlowAPIMiddleware)
    app.state.limiter = limiter

    # --- Exception handlers ---
    register_exception_handlers(app)

    @app.exception_handler(RateLimitExceeded)
    async def _rl_handler(request, exc):  # noqa: ANN001
        from fastapi.responses import JSONResponse

        return JSONResponse(
            status_code=429,
            content={
                "type": "about:blank",
                "title": "Too Many Requests",
                "status": 429,
                "code": "rate_limited",
                "detail": f"Rate limit exceeded: {exc.detail}",
                "request_id": getattr(request.state, "request_id", "-"),
            },
            media_type="application/problem+json",
        )

    # --- Observability ---
    setup_observability(app)

    # --- Routes ---
    app.include_router(api_router, prefix="/api/v1")

    @app.get("/", tags=["meta"])
    async def root():
        return {
            "name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "env": settings.APP_ENV,
            "docs": "/docs",
        }

    Instrumentator().instrument(app).expose(app, endpoint="/metrics", tags=["meta"])
    return app


app = create_app()
