"""Central error registry.

Every error the API can return is declared here once: a stable machine code,
an HTTP status, and a default message. Routes/services raise `AppError(code,
overrides...)`. The handler renders a `problem+json` envelope (RFC 7807).

Why centralize:
  * Frontend can branch on `code` without scraping `message` strings.
  * OpenAPI doc generation becomes mechanical (we list codes per route).
  * Adding a new error never touches the JSON shape.
"""
from __future__ import annotations

import enum
from dataclasses import dataclass


class ErrorCode(str, enum.Enum):
    INTERNAL = "internal_error"
    VALIDATION = "validation_error"
    NOT_FOUND = "not_found"
    UNAUTHORIZED = "unauthorized"
    FORBIDDEN = "forbidden"
    CONFLICT = "conflict"
    RATE_LIMITED = "rate_limited"
    EXTERNAL_SERVICE = "external_service_error"
    DEPENDENCY_UNAVAILABLE = "dependency_unavailable"
    PAYLOAD_TOO_LARGE = "payload_too_large"
    UNSUPPORTED_MEDIA = "unsupported_media_type"
    LLM_BLOCKED = "llm_blocked"
    LLM_TIMEOUT = "llm_timeout"


@dataclass(frozen=True)
class ErrorSpec:
    code: ErrorCode
    status: int
    title: str
    default_message: str


_REGISTRY: dict[ErrorCode, ErrorSpec] = {
    ErrorCode.INTERNAL: ErrorSpec(ErrorCode.INTERNAL, 500, "Internal Server Error", "Unexpected server error."),
    ErrorCode.VALIDATION: ErrorSpec(ErrorCode.VALIDATION, 422, "Validation Error", "Invalid request payload."),
    ErrorCode.NOT_FOUND: ErrorSpec(ErrorCode.NOT_FOUND, 404, "Not Found", "Resource not found."),
    ErrorCode.UNAUTHORIZED: ErrorSpec(ErrorCode.UNAUTHORIZED, 401, "Unauthorized", "Missing or invalid credentials."),
    ErrorCode.FORBIDDEN: ErrorSpec(ErrorCode.FORBIDDEN, 403, "Forbidden", "Insufficient privileges."),
    ErrorCode.CONFLICT: ErrorSpec(ErrorCode.CONFLICT, 409, "Conflict", "Resource state conflict."),
    ErrorCode.RATE_LIMITED: ErrorSpec(ErrorCode.RATE_LIMITED, 429, "Too Many Requests", "Rate limit exceeded."),
    ErrorCode.EXTERNAL_SERVICE: ErrorSpec(ErrorCode.EXTERNAL_SERVICE, 502, "Bad Gateway", "Upstream service failure."),
    ErrorCode.DEPENDENCY_UNAVAILABLE: ErrorSpec(ErrorCode.DEPENDENCY_UNAVAILABLE, 503, "Service Unavailable", "Required dependency is down."),
    ErrorCode.PAYLOAD_TOO_LARGE: ErrorSpec(ErrorCode.PAYLOAD_TOO_LARGE, 413, "Payload Too Large", "Upload exceeds allowed size."),
    ErrorCode.UNSUPPORTED_MEDIA: ErrorSpec(ErrorCode.UNSUPPORTED_MEDIA, 415, "Unsupported Media Type", "Content type not supported."),
    ErrorCode.LLM_BLOCKED: ErrorSpec(ErrorCode.LLM_BLOCKED, 400, "LLM Request Blocked", "Provider blocked the request (safety)."),
    ErrorCode.LLM_TIMEOUT: ErrorSpec(ErrorCode.LLM_TIMEOUT, 504, "LLM Timeout", "Provider call timed out."),
}


def spec_for(code: ErrorCode) -> ErrorSpec:
    return _REGISTRY[code]
