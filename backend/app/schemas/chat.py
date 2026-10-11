"""Chat API schemas."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.chat import MessageRole


class Citation(BaseModel):
    chunk_id: uuid.UUID
    video_id: uuid.UUID
    score: float
    start_time: float | None = None
    end_time: float | None = None
    snippet: str | None = None


class ChatRequest(BaseModel):
    """A turn from the user.

    `conversation_id` is optional — omit it to start a new conversation. If a
    `video_id` is provided we scope retrieval to that single video; otherwise
    we search across the user's entire library.
    """
    message: str = Field(min_length=1, max_length=8000)
    conversation_id: uuid.UUID | None = None
    video_id: uuid.UUID | None = None
    stream: bool = True
    top_k: int | None = Field(default=None, ge=1, le=20)


class MessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    conversation_id: uuid.UUID
    role: MessageRole
    content: str
    citations: list[dict[str, Any]]
    tokens_in: int | None
    tokens_out: int | None
    latency_ms: int | None
    created_at: datetime


class ChatResponse(BaseModel):
    """Non-streaming chat response."""
    conversation_id: uuid.UUID
    message: MessageRead
    citations: list[Citation] = Field(default_factory=list)


class ConversationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    user_id: uuid.UUID
    video_id: uuid.UUID | None
    title: str
    summary: str | None
    message_count: int
    created_at: datetime
    updated_at: datetime


class ConversationDetail(ConversationRead):
    messages: list[MessageRead] = Field(default_factory=list)
