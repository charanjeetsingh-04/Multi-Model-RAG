"""Domain exception classes + global FastAPI handlers.

Renders RFC 7807 problem+json envelopes:

    {
      "type":     "about:blank",
      "title":    "Not Found",
      "status":   404,
      "code":     "not_found",
      "detail":   "Video not found",
      "instance": "/api/v1/videos/<uuid>",
      "request_id": "<uuid>",
      "errors":   [...]    # optional, e.g. for VALIDATION
    }
"""
from __future__ import annotations

from typing import Any

import structlog
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.errors import ErrorCode, spec_for
from app.monitoring.metrics import APP_ERRORS

logger = structlog.get_logger(__name__)
PROBLEM_MEDIA_TYPE = "application/problem+json"


class AppError(Exception):
    """Single exception class with a registry-driven code.

    Most call sites use the convenience subclasses below; you can still raise
    `AppError(ErrorCode.X, "message")` directly.
    """

    code: ErrorCode = ErrorCode.INTERNAL

    def __init__(
        self,
        code_or_message: ErrorCode | str | None = None,
        message: str | None = None,
        *,
        details: Any | None = None,
        status_override: int | None = None,
    ) -> None:
        # Accept either AppError(ErrorCode.X, "msg") or AppError("msg") so
        # legacy `raise UnauthorizedError("Invalid token")` keeps working.
        if isinstance(code_or_message, ErrorCode):
            self.code = code_or_message
            self.message = message or spec_for(self.code).default_message
        elif isinstance(code_or_message, str):
            # First positional is the message; class-level `code` stands.
            self.message = code_or_message
        else:
            self.message = message or spec_for(self.code).default_message
        spec = spec_for(self.code)
        self.title = spec.title
        self.status_code = status_override or spec.status
        self.details = details
        super().__init__(self.message)


# -- Compat shims (so existing services keep working) -----------------------
class NotFoundError(AppError):
    code = ErrorCode.NOT_FOUND


class UnauthorizedError(AppError):
    code = ErrorCode.UNAUTHORIZED


class ForbiddenError(AppError):
    code = ErrorCode.FORBIDDEN


class ValidationError(AppError):
    code = ErrorCode.VALIDATION


class ConflictError(AppError):
    code = ErrorCode.CONFLICT


class RateLimitError(AppError):
    code = ErrorCode.RATE_LIMITED


class ExternalServiceError(AppError):
    code = ErrorCode.EXTERNAL_SERVICE


class LLMBlockedError(AppError):
    code = ErrorCode.LLM_BLOCKED


class LLMTimeoutError(AppError):
    code = ErrorCode.LLM_TIMEOUT


# -- Envelope ---------------------------------------------------------------
def _problem(
    *,
    status_code: int,
    code: str,
    title: str,
    detail: str,
    request: Request,
    extra: dict[str, Any] | None = None,
) -> JSONResponse:
    body: dict[str, Any] = {
        "type": "about:blank",
        "title": title,
        "status": status_code,
        "code": code,
        "detail": detail,
        "instance": str(request.url.path),
        "request_id": getattr(request.state, "request_id", "-"),
    }
    if extra:
        body.update(extra)
    return JSONResponse(status_code=status_code, content=body, media_type=PROBLEM_MEDIA_TYPE)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app(request: Request, exc: AppError):
        APP_ERRORS.labels(code=exc.code.value).inc()
        logger.warning("app_error", code=exc.code.value, message=exc.message)
        extra: dict[str, Any] = {}
        if exc.details is not None:
            extra["errors"] = exc.details
        return _problem(
            status_code=exc.status_code,
            code=exc.code.value,
            title=exc.title,
            detail=exc.message,
            request=request,
            extra=extra,
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http(request: Request, exc: StarletteHTTPException):
        # Map common status codes to known codes for client convenience
        mapping = {401: ErrorCode.UNAUTHORIZED, 403: ErrorCode.FORBIDDEN, 404: ErrorCode.NOT_FOUND}
        code = mapping.get(exc.status_code, ErrorCode.INTERNAL)
        spec = spec_for(code)
        APP_ERRORS.labels(code=code.value).inc()
        return _problem(
            status_code=exc.status_code,
            code=code.value,
            title=spec.title,
            detail=str(exc.detail),
            request=request,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation(request: Request, exc: RequestValidationError):
        APP_ERRORS.labels(code=ErrorCode.VALIDATION.value).inc()
        return _problem(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code=ErrorCode.VALIDATION.value,
            title="Validation Error",
            detail="Invalid request payload.",
            request=request,
            extra={"errors": exc.errors()},
        )

    @app.exception_handler(Exception)
    async def handle_unhandled(request: Request, exc: Exception):
        APP_ERRORS.labels(code=ErrorCode.INTERNAL.value).inc()
        logger.exception("unhandled_exception")
        return _problem(
            status_code=500,
            code=ErrorCode.INTERNAL.value,
            title="Internal Server Error",
            detail="Unexpected server error.",
            request=request,
        )
