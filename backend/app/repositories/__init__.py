"""Repository layer — only point of access to the database.

Services receive repository instances via DI and never import SQLAlchemy
directly. This:
  * decouples business logic from the ORM (swap to a different store later),
  * lets unit tests substitute fakes without spinning up Postgres,
  * concentrates query optimization in one place.
"""
from app.repositories.base import BaseRepository
from app.repositories.chat_repository import (
    ConversationRepository,
    MessageRepository,
)
from app.repositories.preference_repository import UserPreferenceRepository
from app.repositories.user_repository import UserRepository
from app.repositories.video_repository import VideoChunkRepository, VideoRepository

__all__ = [
    "BaseRepository",
    "ConversationRepository",
    "MessageRepository",
    "UserPreferenceRepository",
    "UserRepository",
    "VideoChunkRepository",
    "VideoRepository",
]
