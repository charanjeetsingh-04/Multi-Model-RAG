"""Service providers — assemble services from repos + singletons."""
from __future__ import annotations

from fastapi import Depends

from app.dependencies.repositories import (
    ProvideConversationRepository,
    ProvideMessageRepository,
    ProvideUserPreferenceRepository,
    ProvideUserRepository,
    ProvideVideoChunkRepository,
    ProvideVideoRepository,
)
from app.repositories.chat_repository import ConversationRepository, MessageRepository
from app.repositories.preference_repository import UserPreferenceRepository
from app.repositories.user_repository import UserRepository
from app.repositories.video_repository import VideoChunkRepository, VideoRepository
from app.services.chat_service import ChatService
from app.services.memory_service import MemoryService
from app.services.user_service import UserService
from app.services.video_service import VideoService


async def ProvideUserService(
    users: UserRepository = Depends(ProvideUserRepository),
    prefs: UserPreferenceRepository = Depends(ProvideUserPreferenceRepository),
) -> UserService:
    return UserService(users, prefs)


async def ProvideVideoService(
    videos: VideoRepository = Depends(ProvideVideoRepository),
    chunks: VideoChunkRepository = Depends(ProvideVideoChunkRepository),
) -> VideoService:
    return VideoService(videos, chunks)


async def ProvideMemoryService(
    convs: ConversationRepository = Depends(ProvideConversationRepository),
    msgs: MessageRepository = Depends(ProvideMessageRepository),
    prefs: UserPreferenceRepository = Depends(ProvideUserPreferenceRepository),
) -> MemoryService:
    return MemoryService(convs, msgs, prefs)


async def ProvideChatService(
    convs: ConversationRepository = Depends(ProvideConversationRepository),
    msgs: MessageRepository = Depends(ProvideMessageRepository),
    chunks: VideoChunkRepository = Depends(ProvideVideoChunkRepository),
    memory: MemoryService = Depends(ProvideMemoryService),
) -> ChatService:
    return ChatService(convs, msgs, chunks, memory)
