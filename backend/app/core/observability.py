"""OpenTelemetry bootstrap.

* Auto-instruments FastAPI, SQLAlchemy, Redis, httpx.
* Exporter is OTLP if `OTEL_EXPORTER_OTLP_ENDPOINT` is set, otherwise no-op
  (silent, zero-cost, perfect for local dev).
* Trace ID is bound to structlog contextvars so logs and spans correlate.

Importable as `setup_observability(app)`; missing OTel libs degrade
gracefully — the rest of the app keeps working.
"""
from __future__ import annotations

import os

import structlog
from fastapi import FastAPI

logger = structlog.get_logger(__name__)


def setup_observability(app: FastAPI) -> None:
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    if not endpoint:
        logger.info("otel_disabled", reason="OTEL_EXPORTER_OTLP_ENDPOINT not set")
        return

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        from opentelemetry.instrumentation.redis import RedisInstrumentor
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        resource = Resource.create(
            {
                "service.name": os.getenv("OTEL_SERVICE_NAME", "video-rag-backend"),
                "service.version": os.getenv("APP_VERSION", "1.0.0"),
                "deployment.environment": os.getenv("APP_ENV", "development"),
            }
        )
        provider = TracerProvider(resource=resource)
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
        trace.set_tracer_provider(provider)

        FastAPIInstrumentor.instrument_app(app, excluded_urls="/metrics,/api/v1/health/live")
        SQLAlchemyInstrumentor().instrument(enable_commenter=True)
        RedisInstrumentor().instrument()
        HTTPXClientInstrumentor().instrument()
        logger.info("otel_enabled", endpoint=endpoint)
    except Exception as e:  # noqa: BLE001
        logger.warning("otel_setup_failed", error=str(e))
