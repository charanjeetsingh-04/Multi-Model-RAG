"""Conversation + Message models.

A `Conversation` is the persistence root for a chat thread. Each user message
+ each assistant response becomes a `Message`. We store retrieval citations
(chunk IDs + similarity scores) on assistant messages so the UI can render
"Source: 02:31–02:48" tags and so we can audit/rerank later.
"""
from __future__ import annotations

import enum
import uuid
from typing import TYPE_CHECKING, List

from sqlalchemy import Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPkMixin

if TYPE_CHECKING:
    from app.models.user import User


class MessageRole(str, enum.Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class Conversation(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "conversations"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    video_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("videos.id", ondelete="SET NULL"), index=True
    )
    title: Mapped[str] = mapped_column(String(255), default="New conversation")
    summary: Mapped[str | None] = mapped_column(Text)  # long-term memory summary
    message_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    extra_metadata: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    user: Mapped["User"] = relationship(back_populates="conversations")
    messages: Mapped[List["Message"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
    )


class Message(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "messages"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    role: Mapped[MessageRole] = mapped_column(
        Enum(MessageRole, name="message_role", native_enum=False), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # Retrieval citations: [{"chunk_id": "...", "video_id": "...", "score": 0.83, "start": 12.4}]
    citations: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    tokens_in: Mapped[int | None] = mapped_column(Integer)
    tokens_out: Mapped[int | None] = mapped_column(Integer)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    extra_metadata: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")
