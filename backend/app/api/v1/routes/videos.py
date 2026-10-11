"""Video routes - refactored to use DI providers + Celery.

Routes are now ~3 lines each - all logic lives in `VideoService` and the
Celery task. Background processing is dispatched via `process_video.delay`,
which gives us retries, visibility timeout, and Flower monitoring.
"""
import uuid

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.core.logging import get_logger
from app.db.session import get_db
from app.dependencies import ProvideVideoService
from app.llm.gemini_client import get_llm_client
from app.llm.prompts import PromptBuilder
from app.models.user import User
from app.schemas.common import StatusMessage
from app.schemas.video import VideoListItem, VideoRead, VideoSummary
from app.services.video_service import VideoService
from app.utils.files import build_storage_path, save_upload, validate_video
from app.utils.text import truncate_to_tokens
from app.workers.tasks import process_video as celery_process_video

logger = get_logger(__name__)
router = APIRouter()


@router.post("/upload", response_model=VideoRead, status_code=status.HTTP_201_CREATED)
async def upload_video(
    title: str = Form(..., min_length=1, max_length=255),
    description: str | None = Form(default=None, max_length=4096),
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    svc: VideoService = Depends(ProvideVideoService),
) -> VideoRead:
    validate_video(file)
    dest = build_storage_path(str(user.id), file.filename or "video.mp4")
    size = await save_upload(file, dest)
    video = await svc.create(
        owner_id=user.id,
        title=title,
        description=description,
        filename=file.filename or dest.name,
        storage_path=str(dest),
        mime_type=file.content_type or "video/mp4",
        size_bytes=size,
    )
    celery_process_video.delay(str(video.id))
    return VideoRead.model_validate(video)


@router.get("", response_model=list[VideoListItem])
async def list_videos(
    user: User = Depends(get_current_user),
    svc: VideoService = Depends(ProvideVideoService),
) -> list[VideoListItem]:
    videos = await svc.list_for_user(user.id)
    return [VideoListItem.model_validate(v) for v in videos]


@router.get("/{video_id}", response_model=VideoRead)
async def get_video(
    video_id: uuid.UUID,
    user: User = Depends(get_current_user),
    svc: VideoService = Depends(ProvideVideoService),
) -> VideoRead:
    v = await svc.get(video_id, user.id)
    return VideoRead.model_validate(v)


@router.delete("/{video_id}", response_model=StatusMessage)
async def delete_video(
    video_id: uuid.UUID,
    user: User = Depends(get_current_user),
    svc: VideoService = Depends(ProvideVideoService),
) -> StatusMessage:
    await svc.soft_delete(video_id, user.id)
    return StatusMessage(message="Video deleted")


@router.post("/{video_id}/reprocess", response_model=StatusMessage)
async def reprocess_video(
    video_id: uuid.UUID,
    user: User = Depends(get_current_user),
    svc: VideoService = Depends(ProvideVideoService),
) -> StatusMessage:
    await svc.get(video_id, user.id)  # ownership check
    celery_process_video.delay(str(video_id))
    return StatusMessage(message="Reprocessing queued")


@router.post("/{video_id}/summary", response_model=VideoSummary)
async def summarize_video(
    video_id: uuid.UUID,
    user: User = Depends(get_current_user),
    svc: VideoService = Depends(ProvideVideoService),
    db: AsyncSession = Depends(get_db),
) -> VideoSummary:
    v = await svc.get(video_id, user.id)
    excerpt = truncate_to_tokens(v.transcript or "", max_tokens=8000)
    prompt = PromptBuilder().build_summary(excerpt)
    response = await get_llm_client().complete(prompt)
    bullets = [
        line.strip("-* ").strip()
        for line in response.text.splitlines()
        if line.lstrip().startswith(("-", "*"))
    ]
    v.full_summary = response.text
    await db.flush()
    return VideoSummary(video_id=v.id, summary=response.text, bullet_points=bullets)
