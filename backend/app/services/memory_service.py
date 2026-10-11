"""Memory service — short-term, long-term, user profile.

Optimizations vs v1:
  * Short-term turns are paginated via repository (`list_recent`) → bounded query.
  * Profile lookups are @cached (Redis) with TTL — frequently called per turn.
  * Long-term summary regeneration runs only when the message count crosses a
    threshold; we now check that via `count` rather than re-reading the row.
"""
from __future__ import annotations

import json
import uuid

from app.cache import CacheKeys, cached
from app.core.config import settings
from app.core.logging import get_logger
from app.llm.gemini_client import get_llm_client
from app.llm.prompts import PromptBuilder
from app.repositories.chat_repository import ConversationRepository, MessageRepository
from app.repositories.preference_repository import UserPreferenceRepository

logger = get_logger(__name__)


class MemoryService:
    def __init__(
        self,
        convs: ConversationRepository,
        msgs: MessageRepository,
        prefs: UserPreferenceRepository,
    ) -> None:
        self.convs = convs
        self.msgs = msgs
        self.prefs = prefs
        self.llm = get_llm_client()
        self.prompts = PromptBuilder()

    # ---- short-term ----------------------------------------------------
    async def get_short_term(self, conversation_id: uuid.UUID) -> list[dict]:
        rows = await self.msgs.list_recent(conversation_id, limit=settings.SHORT_TERM_MEMORY_TURNS * 2)
        return [{"role": m.role.value, "content": m.content} for m in rows]

    # ---- long-term -----------------------------------------------------
    async def get_long_term(self, conversation_id: uuid.UUID) -> str | None:
        conv = await self.convs.get(conversation_id)
        return conv.summary if conv else None

    async def maybe_update_summary(self, conversation_id: uuid.UUID) -> None:
        conv = await self.convs.get(conversation_id)
        if not conv:
            return
        if conv.message_count == 0 or conv.message_count % settings.LONG_TERM_SUMMARY_THRESHOLD != 0:
            return
        msgs = await self.msgs.list_for_conversation(conversation_id)
        transcript = "\n".join(f"{m.role.value.upper()}: {m.content}" for m in msgs)
        try:
            prompt = self.prompts.build_memory_summary(transcript)
            response = await self.llm.complete(prompt)
            await self.convs.set_summary(conversation_id, response.text)
            logger.info("conversation_summary_updated", conv=str(conversation_id))
        except Exception as e:  # noqa: BLE001
            logger.warning("summary_update_failed", error=str(e))

    # ---- user profile / preferences -----------------------------------
    @cached(lambda self, user_id: CacheKeys.profile(user_id), ttl=120)
    async def get_user_profile(self, user_id: uuid.UUID) -> dict:
        pref = await self.prefs.get_by_user(user_id)
        if not pref:
            return {}
        profile = {"language": pref.language, "response_style": pref.preferred_response_style}
        profile.update(pref.memory_facts or {})
        return profile

    async def update_user_memory(self, user_id: uuid.UUID, transcript: str) -> None:
        pref = await self.prefs.get_by_user(user_id)
        if not pref:
            return
        try:
            prompt = self.prompts.build_preference_extraction(transcript)
            response = await self.llm.complete(prompt)
            facts = self._safe_json(response.text)
            if facts:
                pref.memory_facts = {**(pref.memory_facts or {}), **facts}
                await self.prefs.flush()
        except Exception as e:  # noqa: BLE001
            logger.warning("preference_extract_failed", error=str(e))

    @staticmethod
    def _safe_json(raw: str) -> dict | None:
        if not raw:
            return None
        raw = raw.strip().lstrip("`")
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
