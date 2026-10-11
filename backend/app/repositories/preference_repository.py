"""User preferences repository."""
from __future__ import annotations

import uuid

from sqlalchemy import select

from app.models.user import UserPreference
from app.repositories.base import BaseRepository


class UserPreferenceRepository(BaseRepository[UserPreference]):
    model = UserPreference

    async def get_by_user(self, user_id: uuid.UUID) -> UserPreference | None:
        stmt = select(UserPreference).where(UserPreference.user_id == user_id)
        return (await self.db.execute(stmt)).scalar_one_or_none()
