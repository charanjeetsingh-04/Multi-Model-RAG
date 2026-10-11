"""Video API schemas."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.video import VideoStatus


class VideoCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=4096)


class VideoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    owner_id: uuid.UUID
    title: str
    description: str | None
    filename: str
    mime_type: str
    file_size_bytes: int
    duration_seconds: float | None
    language: str | None
    status: VideoStatus
    processing_error: str | None
    processed_at: datetime | None
    created_at: datetime
    extra_metadata: dict[str, Any]


class VideoListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    title: str
    status: VideoStatus
    duration_seconds: float | None
    created_at: datetime


class VideoSummary(BaseModel):
    video_id: uuid.UUID
    summary: str
    bullet_points: list[str] = Field(default_factory=list)


class ChunkRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    chunk_index: int
    text: str
    start_time: float | None
    end_time: float | None
