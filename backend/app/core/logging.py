"""Structured logging via structlog.

Every record carries:
  * timestamp (iso)
  * level
  * request_id (contextvars, set by RequestContextMiddleware)
  * trace_id  (auto-merged from OTel if available)
  * service / env / version

In production we emit single-line JSON for log shippers. In development we
render with colors.
"""
from __future__ import annotations

import logging
import os
import sys
from typing import Any

import structlog

from app.core.config import settings


def _otel_processor(_logger, _method_name, event_dict):
    """Best-effort inject OTel trace_id/span_id (skipped if OTel not installed)."""
    try:
        from opentelemetry import trace

        span = trace.get_current_span()
        ctx = span.get_span_context() if span else None
        if ctx and ctx.is_valid:
            event_dict.setdefault("trace_id", format(ctx.trace_id, "032x"))
            event_dict.setdefault("span_id", format(ctx.span_id, "016x"))
    except Exception:
        pass
    return event_dict


def _service_metadata(_logger, _method_name, event_dict):
    event_dict.setdefault("service", os.getenv("OTEL_SERVICE_NAME", settings.APP_NAME))
    event_dict.setdefault("env", settings.APP_ENV)
    event_dict.setdefault("version", settings.APP_VERSION)
    return event_dict


def configure_logging() -> None:
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=log_level)

    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        _service_metadata,
        _otel_processor,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    renderer: Any = (
        structlog.processors.JSONRenderer()
        if settings.LOG_FORMAT == "json"
        else structlog.dev.ConsoleRenderer(colors=True)
    )

    structlog.configure(
        processors=shared_processors + [renderer],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    for noisy in ("uvicorn.access", "httpx", "httpcore", "asyncio", "botocore", "boto3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
