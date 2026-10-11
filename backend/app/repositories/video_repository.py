"""Video + VideoChunk repositories.

`list_ready_chunks_for_user` is the hot path for hybrid retrieval — we keep
it here so the index hint / partitioning strategy lives next to the query.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Sequence

from sqlalchemy import and_, delete, select, update
from sqlalchemy.orm import selectinload

from app.models.video import Video, VideoChunk, VideoStatus
from app.repositories.base import BaseRepository


class VideoRepository(BaseRepository[Video]):
    model = Video

    async def get_owned(self, video_id: uuid.UUID, owner_id: uuid.UUID) -> Video | None:
        stmt = select(Video).where(
            and_(
                Video.id == video_id,
                Video.owner_id == owner_id,
                Video.deleted_at.is_(None),
            )
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def list_for_owner(self, owner_id: uuid.UUID, *, limit: int = 200) -> list[Video]:
        stmt = (
            select(Video)
            .where(Video.owner_id == owner_id, Video.deleted_at.is_(None))
            .order_by(Video.created_at.desc())
            .limit(limit)
        )
        return list((await self.db.execute(stmt)).scalars().all())

    async def list_by_status(self, status: VideoStatus, *, limit: int = 100) -> list[Video]:
        stmt = (
            select(Video)
            .where(Video.status == status, Video.deleted_at.is_(None))
            .order_by(Video.updated_at.desc())
            .limit(limit)
        )
        return list((await self.db.execute(stmt)).scalars().all())

    async def mark_status(
        self,
        video_id: uuid.UUID,
        status: VideoStatus,
        *,
        error: str | None = None,
        processed_at: datetime | None = None,
    ) -> None:
        values: dict = {"status": status}
        if error is not None:
            values["processing_error"] = error[:1000]
        if processed_at is not None:
            values["processed_at"] = processed_at
        await self.db.execute(update(Video).where(Video.id == video_id).values(**values))

    async def soft_delete(self, video_id: uuid.UUID) -> None:
        await self.db.execute(
            update(Video)
            .where(Video.id == video_id)
            .values(deleted_at=datetime.utcnow())
        )


class VideoChunkRepository(BaseRepository[VideoChunk]):
    model = VideoChunk

    async def list_for_video(self, video_id: uuid.UUID) -> list[VideoChunk]:
        stmt = (
            select(VideoChunk)
            .where(VideoChunk.video_id == video_id)
            .order_by(VideoChunk.chunk_index)
        )
        return list((await self.db.execute(stmt)).scalars().all())

    async def list_ready_for_owner(
        self,
        owner_id: uuid.UUID,
        *,
        video_id: uuid.UUID | None = None,
    ) -> list[VideoChunk]:
        """Hot retrieval path. Filters to READY videos owned by `owner_id`."""
        stmt = (
            select(VideoChunk)
            .join(Video, Video.id == VideoChunk.video_id)
            .where(
                Video.owner_id == owner_id,
                Video.status == VideoStatus.READY,
                Video.deleted_at.is_(None),
            )
        )
        if video_id is not None:
            stmt = stmt.where(VideoChunk.video_id == video_id)
        return list((await self.db.execute(stmt)).scalars().all())

    async def get_chunk_ids_for_video(self, video_id: uuid.UUID) -> list[uuid.UUID]:
        stmt = select(VideoChunk.id).where(VideoChunk.video_id == video_id)
        return [row[0] for row in (await self.db.execute(stmt)).all()]

    async def delete_for_video(self, video_id: uuid.UUID) -> int:
        result = await self.db.execute(
            delete(VideoChunk).where(VideoChunk.video_id == video_id)
        )
        return int(result.rowcount or 0)

    async def bulk_insert(self, chunks: Sequence[VideoChunk]) -> None:
        self.db.add_all(list(chunks))
        await self.db.flush()
