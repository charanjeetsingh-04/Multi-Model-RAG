"""Admin-only routes â€” DI-based."""
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_admin
from app.db.session import get_db
from app.models.chat import Conversation, Message
from app.models.user import User
from app.models.video import Video, VideoChunk, VideoStatus
from app.rag.vector_store import get_vector_store
from app.repositories.user_repository import UserRepository
from app.repositories.video_repository import VideoRepository

router = APIRouter()


@router.get("/stats")
async def stats(
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    users_total = (await db.execute(select(func.count(User.id)))).scalar_one()
    videos_total = (
        await db.execute(select(func.count(Video.id)).where(Video.deleted_at.is_(None)))
    ).scalar_one()
    videos_ready = (
        await db.execute(
            select(func.count(Video.id)).where(
                Video.status == VideoStatus.READY, Video.deleted_at.is_(None)
            )
        )
    ).scalar_one()
    chunks_total = (await db.execute(select(func.count(VideoChunk.id)))).scalar_one()
    convs_total = (await db.execute(select(func.count(Conversation.id)))).scalar_one()
    msgs_total = (await db.execute(select(func.count(Message.id)))).scalar_one()
    return {
        "users": users_total,
        "videos": {"total": videos_total, "ready": videos_ready},
        "chunks": chunks_total,
        "conversations": convs_total,
        "messages": msgs_total,
        "vector_store_size": get_vector_store().count(),
    }


@router.get("/users")
async def list_users(
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    users = await UserRepository(db).list_recent(limit=200)
    return [
        {
            "id": str(u.id),
            "email": u.email,
            "username": u.username,
            "is_admin": u.is_admin,
            "is_active": u.is_active,
            "created_at": u.created_at.isoformat(),
        }
        for u in users
    ]


@router.get("/failed-videos")
async def failed_videos(
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    videos = await VideoRepository(db).list_by_status(VideoStatus.FAILED, limit=100)
    return [
        {
            "id": str(v.id),
            "owner_id": str(v.owner_id),
            "title": v.title,
            "error": v.processing_error,
            "updated_at": v.updated_at.isoformat(),
        }
        for v in videos
    ]
