"""Rate limiting via slowapi (Flask-Limiter port for Starlette).

Key strategy: prefer authenticated user-id, fall back to client IP. This way a
single shared NAT doesn't starve legitimate logged-in users.
"""
from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request

from app.core.config import settings


def _key_func(request: Request) -> str:
    user = getattr(request.state, "user", None)
    if user is not None and getattr(user, "id", None):
        return f"user:{user.id}"
    return f"ip:{get_remote_address(request)}"


limiter = Limiter(
    key_func=_key_func,
    default_limits=[f"{settings.RATE_LIMIT_PER_MINUTE}/minute"],
    headers_enabled=True,
)
