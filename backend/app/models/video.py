"""Video and VideoChunk models.

`Video` is the high-level record (file metadata + processing status).
`VideoChunk` is one segment of the transcript that was embedded and stored
in the vector store. We keep chunk text + start/end times in PG so that
citations can show timestamps and we can rebuild the index without
re-transcribing.
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List

from sqlalchemy import (
    BigInteger,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPkMixin

if TYPE_CHECKING:
    from app.models.user import User


class VideoStatus(str, enum.Enum):
    """Lifecycle states for the async processing pipeline."""

    UPLOADED = "uploaded"
    EXTRACTING_AUDIO = "extracting_audio"
    TRANSCRIBING = "transcribing"
    CHUNKING = "chunking"
    EMBEDDING = "embedding"
    INDEXING = "indexing"
    READY = "ready"
    FAILED = "failed"


class Video(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "videos"

    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(128), default="video/mp4")
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, default=0)

    duration_seconds: Mapped[float | None] = mapped_column(Float)
    language: Mapped[str | None] = mapped_column(String(8))

    transcript: Mapped[str | None] = mapped_column(Text)
    full_summary: Mapped[str | None] = mapped_column(Text)
    extra_metadata: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    status: Mapped[VideoStatus] = mapped_column(
        Enum(VideoStatus, name="video_status", native_enum=False),
        default=VideoStatus.UPLOADED,
        index=True,
        nullable=False,
    )
    processing_error: Mapped[str | None] = mapped_column(Text)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    # Relationships
    owner: Mapped["User"] = relationship(back_populates="videos")
    chunks: Mapped[List["VideoChunk"]] = relationship(
        back_populates="video", cascade="all, delete-orphan", order_by="VideoChunk.chunk_index"
    )


class VideoChunk(Base, UUIDPkMixin, TimestampMixin):
    """One semantic chunk of a video's transcript.

    `vector_id` is the integer or UUID identifier inside the external vector
    store (FAISS / Chroma). Storing it lets us delete the right vector when
    the video is deleted.
    """

    __tablename__ = "video_chunks"
    __table_args__ = (
        Index("ix_chunks_video_idx", "video_id", "chunk_index"),
    )

    video_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("videos.id", ondelete="CASCADE"), index=True, nullable=False
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    start_time: Mapped[float | None] = mapped_column(Float)
    end_time: Mapped[float | None] = mapped_column(Float)
    token_count: Mapped[int | None] = mapped_column(Integer)
    vector_id: Mapped[str | None] = mapped_column(String(64), index=True)
    extra_metadata: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    video: Mapped["Video"] = relationship(back_populates="chunks")
