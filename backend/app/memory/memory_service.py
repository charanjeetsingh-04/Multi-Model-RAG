"""Memory service — short-term, long-term, user preference orchestration.

Public surface:
  * get_short_term(conv_id) -> recent N turns for prompt history
  * get_long_term(conv_id)  -> rolling summary string
  * maybe_update_summary(conv_id) -> recompute summary if threshold hit
  * get_user_profile(user_id) -> compact dict for personalization
"""
from __future__ import annotations

import json
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.llm.gemini_client import get_llm_client
from app.llm.prompts import PromptBuilder
from app.memory.redis_cache import get_cache
from app.models.chat import Conversation, Message, MessageRole
from app.models.user import UserPreference

logger = get_logger(__name__)


class MemoryService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.cache = get_cache()
        self.llm = get_llm_client()
        self.prompts = PromptBuilder()

    # ----- short-term ----------------------------------------------------
    async def get_short_term(self, conversation_id: uuid.UUID) -> list[dict]:
        cache_key = f"shortmem:{conversation_id}"
        cached = await self.cache.get(cache_key)
        if cached:
            return cached

        result = await self.db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc())
            .limit(settings.SHORT_TERM_MEMORY_TURNS * 2)
        )
        msgs = list(result.scalars().all())[::-1]   # chronological
        turns = [{"role": m.role.value, "content": m.content} for m in msgs]
        await self.cache.set(cache_key, turns, ttl=600)
        return turns

    async def invalidate_short_term(self, conversation_id: uuid.UUID) -> None:
        await self.cache.delete(f"shortmem:{conversation_id}")

    # ----- long-term -----------------------------------------------------
    async def get_long_term(self, conversation_id: uuid.UUID) -> str | None:
        result = await self.db.execute(
            select(Conversation.summary).where(Conversation.id == conversation_id)
        )
        return result.scalar_one_or_none()

    async def maybe_update_summary(self, conversation_id: uuid.UUID) -> None:
        """Recompute summary if message_count crosses the threshold.

        We summarize *all* messages — cheap and reliable. For very long
        threads, a hierarchical strategy (summarize-of-summaries) would
        be the next step.
        """
        result = await self.db.execute(
            select(Conversation).where(Conversation.id == conversation_id)
        )
        conv = result.scalar_one_or_none()
        if not conv:
            return
        if conv.message_count == 0 or conv.message_count % settings.LONG_TERM_SUMMARY_THRESHOLD != 0:
            return

        msgs_res = await self.db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at)
        )
        msgs = list(msgs_res.scalars().all())
        transcript = "\n".join(f"{m.role.value.upper()}: {m.content}" for m in msgs)

        try:
            prompt = self.prompts.build_memory_summary(transcript)
            response = await self.llm.complete(prompt)
            conv.summary = response.text
            await self.db.flush()
            logger.info("conversation_summary_updated", conv=str(conversation_id))
        except Exception as e:  # noqa: BLE001
            logger.warning("summary_update_failed", error=str(e))

    # ----- user profile / preferences -----------------------------------
    async def get_user_profile(self, user_id: uuid.UUID) -> dict:
        result = await self.db.execute(
            select(UserPreference).where(UserPreference.user_id == user_id)
        )
        pref = result.scalar_one_or_none()
        if not pref:
            return {}
        profile = {
            "language": pref.language,
            "response_style": pref.preferred_response_style,
        }
        profile.update(pref.memory_facts or {})
        return profile

    async def update_user_memory(self, user_id: uuid.UUID, transcript: str) -> None:
        """Run extraction LLM call and merge facts into user_preferences."""
        result = await self.db.execute(
            select(UserPreference).where(UserPreference.user_id == user_id)
        )
        pref = result.scalar_one_or_none()
        if not pref:
            return

        try:
            prompt = self.prompts.build_preference_extraction(transcript)
            response = await self.llm.complete(prompt)
            new_facts = self._safe_json(response.text)
            if new_facts:
                pref.memory_facts = {**(pref.memory_facts or {}), **new_facts}
                await self.db.flush()
        except Exception as e:  # noqa: BLE001
            logger.warning("preference_extract_failed", error=str(e))

    @staticmethod
    def _safe_json(raw: str) -> dict | None:
        if not raw:
            return None
        raw = raw.strip().lstrip("`")
        # Strip ```json prefix sometimes returned
        if raw.startswith("json"):
            raw = raw[4:].lstrip()
        end = raw.rfind("}")
        if end != -1:
            raw = raw[: end + 1]
        try:
            data = json.loads(raw)
            return data if isinstance(data, dict) else None
        except Exception:
            return None
