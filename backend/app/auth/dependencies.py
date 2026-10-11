"""FastAPI auth dependencies.

Routes do `user = Depends(get_current_user)` and don't have to think about
token parsing. `require_admin` builds on top — handy for the admin panel.
"""
from __future__ import annotations

import uuid

from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import ACCESS_TOKEN_TYPE, decode_token
from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.db.session import get_db
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


async def get_current_user(
    request: Request,
    token: str | None = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not token:
        raise UnauthorizedError("Missing authentication token")

    payload = decode_token(token, expected_type=ACCESS_TOKEN_TYPE)
    sub = payload.get("sub")
    if not sub:
        raise UnauthorizedError("Token missing subject")

    try:
        user_id = uuid.UUID(sub)
    except ValueError as e:
        raise UnauthorizedError("Invalid user id in token") from e

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise UnauthorizedError("User not found or inactive")

    request.state.user = user  # so rate-limiter can key on user.id
    return user


async def require_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise ForbiddenError("Admin privileges required")
    return user
