"""ORM models — import here so Alembic autogenerate discovers them all."""
from app.models.chat import Conversation, Message  # noqa: F401
from app.models.user import User, UserPreference  # noqa: F401
from app.models.video import Video, VideoChunk  # noqa: F401
