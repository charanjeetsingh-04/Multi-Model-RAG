"""User service — auth + profile operations.

Pure orchestration; ORM access goes through `UserRepository` /
`UserPreferenceRepository`. All writes flush via the repo (which is just
delegating to the session) — the route's `get_db` dependency commits the
unit-of-work on success.
"""
from __future__ import annotations

import uuid

from app.auth.security import (
    REFRESH_TOKEN_TYPE,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.cache import CacheKeys, invalidates
from app.core.config import settings
from app.core.exceptions import ConflictError, NotFoundError, UnauthorizedError
from app.models.user import User, UserPreference
from app.repositories.preference_repository import UserPreferenceRepository
from app.repositories.user_repository import UserRepository
from app.schemas.user import TokenPair, UserCreate


class UserService:
    def __init__(
        self,
        users: UserRepository,
        prefs: UserPreferenceRepository,
    ) -> None:
        self.users = users
        self.prefs = prefs

    async def get_by_id(self, user_id: uuid.UUID) -> User:
        user = await self.users.get_by_id(user_id)
        if not user:
            raise NotFoundError(message="User not found")
        return user

    async def register(self, payload: UserCreate) -> User:
        if await self.users.get_by_email(payload.email):
            raise ConflictError(message="Email already registered")
        if await self.users.get_by_username(payload.username):
            raise ConflictError(message="Username already taken")

        user = User(
            email=payload.email.lower(),
            username=payload.username,
            full_name=payload.full_name,
            hashed_password=hash_password(payload.password),
        )
        self.users.add(user)
        await self.users.flush()
        self.prefs.add(UserPreference(user_id=user.id))
        await self.prefs.flush()
        return user

    async def authenticate(self, email: str, password: str) -> User:
        user = await self.users.get_by_email(email)
        if not user or not verify_password(password, user.hashed_password):
            raise UnauthorizedError(message="Invalid email or password")
        if not user.is_active:
            raise UnauthorizedError(message="Account is inactive")
        return user

    def issue_tokens(self, user: User) -> TokenPair:
        access = create_access_token(
            str(user.id),
            extra={"username": user.username, "is_admin": user.is_admin},
        )
        refresh = create_refresh_token(str(user.id))
        return TokenPair(
            access_token=access,
            refresh_token=refresh,
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    async def refresh_tokens(self, refresh_token: str) -> TokenPair:
        payload = decode_token(refresh_token, expected_type=REFRESH_TOKEN_TYPE)
        user = await self.get_by_id(uuid.UUID(payload["sub"]))
        return self.issue_tokens(user)

    @invalidates(lambda self, user_id, _patch: CacheKeys.user_pattern(user_id))
    async def update_preferences(self, user_id: uuid.UUID, patch: dict) -> UserPreference:
        pref = await self.prefs.get_by_user(user_id)
        if not pref:
            raise NotFoundError(message="User preferences not found")
        for k, v in patch.items():
            if v is not None:
                setattr(pref, k, v)
        await self.prefs.flush()
        return pref

    async def get_preferences(self, user_id: uuid.UUID) -> UserPreference:
        pref = await self.prefs.get_by_user(user_id)
        if not pref:
            raise NotFoundError(message="User preferences not found")
        return pref
