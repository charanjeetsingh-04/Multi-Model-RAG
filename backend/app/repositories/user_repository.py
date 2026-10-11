"""User repository — every user lookup goes through here.

Eager-loads `preferences` when needed (one extra join, saves an N+1).
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.user import User, UserPreference
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    model = User

    async def get_by_email(self, email: str, *, with_preferences: bool = False) -> User | None:
        stmt = select(User).where(User.email == email.lower())
        if with_preferences:
            stmt = stmt.options(selectinload(User.preferences))
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def get_by_username(self, username: str) -> User | None:
        stmt = select(User).where(User.username == username)
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def get_by_id(self, user_id: uuid.UUID, *, with_preferences: bool = False) -> User | None:
        stmt = select(User).where(User.id == user_id)
        if with_preferences:
            stmt = stmt.options(selectinload(User.preferences))
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def list_recent(self, limit: int = 200) -> list[User]:
        stmt = select(User).order_by(User.created_at.desc()).limit(limit)
        return list((await self.db.execute(stmt)).scalars().all())
