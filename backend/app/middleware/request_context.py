"""Per-request context: request_id, trace headers, structured access logs.

API-gateway awareness:
  * `X-Request-ID`        — honored if present (gateway-correlation).
  * `X-Forwarded-For`     — honored for rate-limit IP key.
  * `traceparent`         — W3C trace context, picked up by OTel automatically.

This middleware deliberately does NOT trust `X-Forwarded-User` for auth —
JWT validation still runs. Gateway is a hop, not a source of truth.
"""
from __future__ import annotations

import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = structlog.get_logger("access")


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id

        forwarded_for = request.headers.get("X-Forwarded-For")
        client_ip = (forwarded_for or "").split(",")[0].strip() or (request.client.host if request.client else "-")

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            client_ip=client_ip,
        )

        start = time.perf_counter()
        try:
            response: Response = await call_next(request)
        except Exception:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            logger.exception("request_failed", duration_ms=duration_ms)
            raise

        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time-ms"] = str(duration_ms)
        # Hint to gateways: this response was generated freshly
        response.headers.setdefault("Cache-Control", "no-store")

        logger.info(
            "request_completed",
            status_code=response.status_code,
            duration_ms=duration_ms,
        )
        return response
