"""Conversation + Message repositories.

`list_recent_messages` uses ORDER BY DESC + reverse to scan an index instead
of forcing a sort over all rows — important once a conversation grows past
a few thousand messages.
"""
from __future__ import annotations

import uuid
from typing import Sequence

from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from app.models.chat import Conversation, Message
from app.repositories.base import BaseRepository


class ConversationRepository(BaseRepository[Conversation]):
    model = Conversation

    async def get_for_user(
        self,
        conv_id: uuid.UUID,
        user_id: uuid.UUID,
        *,
        with_messages: bool = False,
    ) -> Conversation | None:
        stmt = select(Conversation).where(
            Conversation.id == conv_id, Conversation.user_id == user_id
        )
        if with_messages:
            stmt = stmt.options(selectinload(Conversation.messages))
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def list_for_user(self, user_id: uuid.UUID, *, limit: int = 100) -> list[Conversation]:
        stmt = (
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(Conversation.updated_at.desc())
            .limit(limit)
        )
        return list((await self.db.execute(stmt)).scalars().all())

    async def increment_message_count(self, conv_id: uuid.UUID, delta: int = 1) -> None:
        await self.db.execute(
            update(Conversation)
            .where(Conversation.id == conv_id)
            .values(message_count=Conversation.message_count + delta)
        )

    async def set_summary(self, conv_id: uuid.UUID, summary: str) -> None:
        await self.db.execute(
            update(Conversation).where(Conversation.id == conv_id).values(summary=summary)
        )


class MessageRepository(BaseRepository[Message]):
    model = Message

    async def list_for_conversation(self, conv_id: uuid.UUID) -> list[Message]:
        stmt = (
            select(Message)
            .where(Message.conversation_id == conv_id)
            .order_by(Message.created_at)
        )
        return list((await self.db.execute(stmt)).scalars().all())

    async def list_recent(self, conv_id: uuid.UUID, *, limit: int) -> list[Message]:
        """Last `limit` messages in chronological order."""
        stmt = (
            select(Message)
            .where(Message.conversation_id == conv_id)
            .order_by(Message.created_at.desc())
            .limit(limit)
        )
        rows = list((await self.db.execute(stmt)).scalars().all())
        return rows[::-1]
