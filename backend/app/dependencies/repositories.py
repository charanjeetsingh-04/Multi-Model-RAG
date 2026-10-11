"""Repository providers — bind one repo per request to the DB session."""
from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.repositories.chat_repository import ConversationRepository, MessageRepository
from app.repositories.preference_repository import UserPreferenceRepository
from app.repositories.user_repository import UserRepository
from app.repositories.video_repository import VideoChunkRepository, VideoRepository


async def ProvideUserRepository(db: AsyncSession = Depends(get_db)) -> UserRepository:
    return UserRepository(db)


async def ProvideUserPreferenceRepository(db: AsyncSession = Depends(get_db)) -> UserPreferenceRepository:
    return UserPreferenceRepository(db)


async def ProvideVideoRepository(db: AsyncSession = Depends(get_db)) -> VideoRepository:
    return VideoRepository(db)


async def ProvideVideoChunkRepository(db: AsyncSession = Depends(get_db)) -> VideoChunkRepository:
    return VideoChunkRepository(db)


async def ProvideConversationRepository(db: AsyncSession = Depends(get_db)) -> ConversationRepository:
    return ConversationRepository(db)


async def ProvideMessageRepository(db: AsyncSession = Depends(get_db)) -> MessageRepository:
    return MessageRepository(db)
