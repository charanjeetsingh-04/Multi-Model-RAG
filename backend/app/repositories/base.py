"""Generic async base repository.

Concrete repos extend this and add their own query methods. We deliberately
avoid a "magic" find-by-anything API — explicit query methods are easier to
optimize (index hints, prefetching, partitioning).
"""
from __future__ import annotations

import uuid
from typing import Any, Generic, Sequence, Type, TypeVar

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Base

TModel = TypeVar("TModel", bound=Base)


class BaseRepository(Generic[TModel]):
    model: Type[TModel]

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ---------- read --------------------------------------------------
    async def get(self, entity_id: uuid.UUID) -> TModel | None:
        return await self.db.get(self.model, entity_id)

    async def get_many(self, ids: Sequence[uuid.UUID]) -> list[TModel]:
        if not ids:
            return []
        result = await self.db.execute(
            select(self.model).where(self.model.id.in_(list(ids)))  # type: ignore[attr-defined]
        )
        return list(result.scalars().all())

    async def count(self, **filters: Any) -> int:
        stmt = select(func.count()).select_from(self.model)
        for k, v in filters.items():
            stmt = stmt.where(getattr(self.model, k) == v)
        return int((await self.db.execute(stmt)).scalar_one())

    async def exists(self, **filters: Any) -> bool:
        return (await self.count(**filters)) > 0

    # ---------- write -------------------------------------------------
    def add(self, entity: TModel) -> TModel:
        """Stages an insert. Caller commits via the unit-of-work / session."""
        self.db.add(entity)
        return entity

    def add_all(self, entities: Sequence[TModel]) -> None:
        self.db.add_all(list(entities))

    async def delete(self, entity: TModel) -> None:
        await self.db.delete(entity)

    async def delete_where(self, **filters: Any) -> int:
        stmt = delete(self.model)
        for k, v in filters.items():
            stmt = stmt.where(getattr(self.model, k) == v)
        result = await self.db.execute(stmt)
        return int(result.rowcount or 0)

    async def flush(self) -> None:
        await self.db.flush()
