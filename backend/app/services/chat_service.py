"""Chat service.

Latency optimizations vs v1:
  * `asyncio.gather` runs short-term memory + long-term memory + user profile
    + retrieval in parallel — cuts ~150-300ms off cold chats.
  * Retrieval results for the same query/scope are cached in Redis (30s TTL).
  * Token budget is tightened in `ContextBuilder` (≤4k by default).
  * Streaming path persists only the final message + citations.
"""
from __future__ import annotations

import asyncio
import time
import uuid
from typing import AsyncIterator

from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.llm.gemini_client import get_llm_client
from app.llm.prompts import PromptBuilder
from app.models.chat import Conversation, Message, MessageRole
from app.rag.context_builder import ContextBuilder
from app.rag.retriever import HybridRetriever
from app.repositories.chat_repository import ConversationRepository, MessageRepository
from app.repositories.video_repository import VideoChunkRepository
from app.services.memory_service import MemoryService

logger = get_logger(__name__)


class ChatService:
    def __init__(
        self,
        convs: ConversationRepository,
        msgs: MessageRepository,
        chunks: VideoChunkRepository,
        memory: MemoryService,
    ) -> None:
        self.convs = convs
        self.msgs = msgs
        self.chunks = chunks
        self.memory = memory
        self.retriever = HybridRetriever(chunks)
        self.context_builder = ContextBuilder()
        self.prompts = PromptBuilder()
        self.llm = get_llm_client()

    # ---- queries ------------------------------------------------------
    async def get_conversation(self, conv_id: uuid.UUID, user_id: uuid.UUID) -> Conversation:
        conv = await self.convs.get_for_user(conv_id, user_id)
        if not conv:
            raise NotFoundError(message="Conversation not found")
        return conv

    async def list_conversations(self, user_id: uuid.UUID) -> list[Conversation]:
        return await self.convs.list_for_user(user_id)

    async def list_messages(self, conv_id: uuid.UUID, user_id: uuid.UUID) -> list[Message]:
        await self.get_conversation(conv_id, user_id)
        return await self.msgs.list_for_conversation(conv_id)

    async def delete_conversation(self, conv_id: uuid.UUID, user_id: uuid.UUID) -> None:
        conv = await self.get_conversation(conv_id, user_id)
        await self.convs.delete(conv)
        await self.convs.flush()

    # ---- core chat path ----------------------------------------------
    async def respond(
        self,
        *,
        user_id: uuid.UUID,
        message: str,
        conversation_id: uuid.UUID | None,
        video_id: uuid.UUID | None,
        top_k: int | None,
    ) -> tuple[Conversation, Message, list[dict]]:
        conv, prepared = await self._prepare(
            user_id=user_id,
            message=message,
            conversation_id=conversation_id,
            video_id=video_id,
            top_k=top_k,
        )
        start = time.perf_counter()
        response = await self.llm.complete(prepared.prompt)
        latency = int((time.perf_counter() - start) * 1000)
        assistant = await self._save_assistant(
            conv=conv,
            text=response.text,
            citations=prepared.citations,
            tokens_in=response.tokens_in,
            tokens_out=response.tokens_out,
            latency=latency,
        )
        await self.memory.maybe_update_summary(conv.id)
        return conv, assistant, prepared.citations

    async def respond_stream(
        self,
        *,
        user_id: uuid.UUID,
        message: str,
        conversation_id: uuid.UUID | None,
        video_id: uuid.UUID | None,
        top_k: int | None,
    ) -> AsyncIterator[dict]:
        conv, prepared = await self._prepare(
            user_id=user_id,
            message=message,
            conversation_id=conversation_id,
            video_id=video_id,
            top_k=top_k,
        )
        yield {
            "type": "start",
            "conversation_id": str(conv.id),
            "citations": prepared.citations,
        }
        start = time.perf_counter()
        parts: list[str] = []
        try:
            async for delta in await self.llm.stream(prepared.prompt):
                parts.append(delta)
                yield {"type": "delta", "text": delta}
        except Exception as e:  # noqa: BLE001
            yield {"type": "error", "message": str(e)}
            return
        latency = int((time.perf_counter() - start) * 1000)
        assistant = await self._save_assistant(
            conv=conv,
            text="".join(parts),
            citations=prepared.citations,
            tokens_in=None,
            tokens_out=None,
            latency=latency,
        )
        await self.memory.maybe_update_summary(conv.id)
        yield {
            "type": "done",
            "message_id": str(assistant.id),
            "conversation_id": str(conv.id),
            "citations": prepared.citations,
            "latency_ms": latency,
        }

    # ---- internals ---------------------------------------------------
    async def _get_or_create_conversation(
        self,
        *,
        user_id: uuid.UUID,
        conversation_id: uuid.UUID | None,
        video_id: uuid.UUID | None,
        first_message: str,
    ) -> Conversation:
        if conversation_id:
            conv = await self.convs.get_for_user(conversation_id, user_id)
            if not conv:
                raise NotFoundError(message="Conversation not found")
            return conv
        title = (first_message[:60] + "…") if len(first_message) > 60 else first_message
        conv = Conversation(user_id=user_id, video_id=video_id, title=title)
        self.convs.add(conv)
        await self.convs.flush()
        return conv

    async def _prepare(self, *, user_id, message, conversation_id, video_id, top_k):
        from dataclasses import dataclass

        @dataclass
        class Prepared:
            prompt: object
            citations: list[dict]

        conv = await self._get_or_create_conversation(
            user_id=user_id,
            conversation_id=conversation_id,
            video_id=video_id,
            first_message=message,
        )

        # Persist the user turn so it's in DB before we look up short-term memory.
        user_msg = Message(conversation_id=conv.id, role=MessageRole.USER, content=message)
        self.msgs.add(user_msg)
        await self.convs.increment_message_count(conv.id, 1)
        await self.msgs.flush()

        # *** Latency win: run memory + retrieval in parallel ***
        short_term_t = asyncio.create_task(self.memory.get_short_term(conv.id))
        long_term_t = asyncio.create_task(self.memory.get_long_term(conv.id))
        profile_t = asyncio.create_task(self.memory.get_user_profile(user_id))
        retrieval_t = asyncio.create_task(
            self.retriever.retrieve(message, user_id=user_id, video_id=video_id or conv.video_id, top_k=top_k)
        )
        short_term, long_term, profile, retrieved = await asyncio.gather(
            short_term_t, long_term_t, profile_t, retrieval_t
        )

        context_block = self.context_builder.build(retrieved)
        history = [t for t in short_term if t["content"] != message][-10:]
        chat_prompt = self.prompts.build_chat(
            user_question=message,
            retrieved_context=context_block.text,
            history_turns=history,
            long_term_summary=long_term,
            user_profile=profile,
        )
        return conv, Prepared(prompt=chat_prompt, citations=context_block.citations)

    async def _save_assistant(
        self,
        *,
        conv: Conversation,
        text: str,
        citations: list[dict],
        tokens_in: int | None,
        tokens_out: int | None,
        latency: int,
    ) -> Message:
        msg = Message(
            conversation_id=conv.id,
            role=MessageRole.ASSISTANT,
            content=text,
            citations=citations,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            latency_ms=latency,
        )
        self.msgs.add(msg)
        await self.convs.increment_message_count(conv.id, 1)
        await self.msgs.flush()
        return msg
