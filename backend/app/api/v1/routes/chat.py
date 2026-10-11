"""Chat routes - refactored to use DI providers.

Streaming endpoint still uses its own DB session so the stream can outlive
the FastAPI request lifecycle.
"""
import json
import uuid

from fastapi import APIRouter, Depends, Request
from sse_starlette.sse import EventSourceResponse

from app.auth.dependencies import get_current_user
from app.core.logging import get_logger
from app.db.session import AsyncSessionLocal
from app.dependencies import ProvideChatService, ProvideMemoryService
from app.middleware.rate_limit import limiter
from app.models.user import User
from app.repositories.chat_repository import ConversationRepository, MessageRepository
from app.repositories.preference_repository import UserPreferenceRepository
from app.repositories.video_repository import VideoChunkRepository
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    ConversationDetail,
    ConversationRead,
    MessageRead,
)
from app.schemas.common import StatusMessage
from app.services.chat_service import ChatService
from app.services.memory_service import MemoryService

logger = get_logger(__name__)
router = APIRouter()


@router.get("/conversations", response_model=list[ConversationRead])
async def list_conversations(
    user: User = Depends(get_current_user),
    svc: ChatService = Depends(ProvideChatService),
) -> list[ConversationRead]:
    convs = await svc.list_conversations(user.id)
    return [ConversationRead.model_validate(c) for c in convs]


@router.get("/conversations/{conv_id}", response_model=ConversationDetail)
async def get_conversation(
    conv_id: uuid.UUID,
    user: User = Depends(get_current_user),
    svc: ChatService = Depends(ProvideChatService),
) -> ConversationDetail:
    conv = await svc.get_conversation(conv_id, user.id)
    msgs = await svc.list_messages(conv_id, user.id)
    detail = ConversationDetail.model_validate(conv)
    detail.messages = [MessageRead.model_validate(m) for m in msgs]
    return detail


@router.delete("/conversations/{conv_id}", response_model=StatusMessage)
async def delete_conversation(
    conv_id: uuid.UUID,
    user: User = Depends(get_current_user),
    svc: ChatService = Depends(ProvideChatService),
) -> StatusMessage:
    await svc.delete_conversation(conv_id, user.id)
    return StatusMessage(message="Conversation deleted")


@router.post("", response_model=ChatResponse)
@limiter.limit("60/minute")
async def chat(
    request: Request,
    payload: ChatRequest,
    user: User = Depends(get_current_user),
    svc: ChatService = Depends(ProvideChatService),
) -> ChatResponse:
    conv, message, citations = await svc.respond(
        user_id=user.id,
        message=payload.message,
        conversation_id=payload.conversation_id,
        video_id=payload.video_id,
        top_k=payload.top_k,
    )
    return ChatResponse(
        conversation_id=conv.id,
        message=MessageRead.model_validate(message),
        citations=citations,  # type: ignore[arg-type]
    )


@router.post("/stream")
@limiter.limit("60/minute")
async def chat_stream(
    request: Request,
    payload: ChatRequest,
    user: User = Depends(get_current_user),
) -> EventSourceResponse:
    """SSE endpoint with its own DB session for the duration of the stream."""

    async def event_generator():
        async with AsyncSessionLocal() as db:
            convs = ConversationRepository(db)
            msgs = MessageRepository(db)
            chunks = VideoChunkRepository(db)
            prefs = UserPreferenceRepository(db)
            memory = MemoryService(convs, msgs, prefs)
            svc = ChatService(convs, msgs, chunks, memory)
            try:
                async for event in svc.respond_stream(
                    user_id=user.id,
                    message=payload.message,
                    conversation_id=payload.conversation_id,
                    video_id=payload.video_id,
                    top_k=payload.top_k,
                ):
                    yield {"event": event.get("type", "message"), "data": json.dumps(event)}
                await db.commit()
            except Exception as e:  # noqa: BLE001
                await db.rollback()
                logger.exception("chat_stream_error")
                yield {"event": "error", "data": json.dumps({"message": str(e)})}

    return EventSourceResponse(event_generator())
