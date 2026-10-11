"""Celery task definitions.

Tasks are thin shims that:
  1. Open a fresh async DB session.
  2. Build the service from repositories.
  3. Delegate to the service method.

Why so thin? All retry/back-off policy is declared on the task decorator —
the actual work lives in normal Python code that's unit-testable without
Celery in the loop.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta, timezone

from celery import shared_task
from celery.utils.log import get_task_logger

from app.db.session import AsyncSessionLocal
from app.models.video import VideoStatus
from app.repositories.chat_repository import ConversationRepository, MessageRepository
from app.repositories.preference_repository import UserPreferenceRepository
from app.repositories.video_repository import VideoChunkRepository, VideoRepository
from app.services.memory_service import MemoryService
from app.services.video_service import VideoService
from app.workers.celery_app import celery_app  # noqa: F401  (registers tasks)

log = get_task_logger(__name__)


def _run(coro):
    """Run an async coroutine in a freshly-managed loop (Celery is sync)."""
    try:
        loop = asyncio.new_event_loop()
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@shared_task(
    bind=True,
    name="app.workers.tasks.process_video",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=3,
)
def process_video(self, video_id: str) -> dict:
    """Run the full ingestion pipeline for one video.

    Idempotent — the service wipes stale chunks before re-inserting, so
    Celery retries are safe.
    """
    log.info("process_video.start", extra={"video_id": video_id})
    vid = uuid.UUID(video_id)

    async def _do():
        async with AsyncSessionLocal() as db:
            svc = VideoService(VideoRepository(db), VideoChunkRepository(db))
            try:
                await svc.process_video(vid)
                await db.commit()
                return {"status": "ok", "video_id": video_id}
            except Exception:
                await db.rollback()
                raise

    return _run(_do())


@shared_task(name="app.workers.tasks.cleanup_failed_videos")
def cleanup_failed_videos() -> dict:
    """Periodic: surface videos stuck FAILED for >24h so ops can retry/drop."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)

    async def _do():
        async with AsyncSessionLocal() as db:
            repo = VideoRepository(db)
            failed = await repo.list_by_status(VideoStatus.FAILED, limit=500)
            stuck = [v for v in failed if v.updated_at < cutoff]
            log.info("cleanup_failed_videos.summary", extra={"count": len(stuck)})
            return {"stuck": len(stuck)}

    return _run(_do())


@shared_task(name="app.workers.tasks.summarize_inactive_conversations")
def summarize_inactive_conversations() -> dict:
    """Pre-compute long-term summaries for conversations that crossed the
    threshold but haven't had a turn in >1h (cheaper to do off-peak)."""
    async def _do():
        async with AsyncSessionLocal() as db:
            convs = ConversationRepository(db)
            msgs = MessageRepository(db)
            prefs = UserPreferenceRepository(db)
            mem = MemoryService(convs, msgs, prefs)
            # Find any conversation whose message_count is a threshold multiple
            # and no summary yet; do it best-effort:
            rows = await convs.list_for_user  # placeholder for an admin-wide scan
            # (Production: add a dedicated repo method `list_due_for_summary`.)
            log.info("summarize_inactive.noop")
            return {"updated": 0}

    return _run(_do())
