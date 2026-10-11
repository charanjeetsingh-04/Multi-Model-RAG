"""Prompt templates — kept terse to save tokens.

Token-saving choices vs v1:
  * Shorter system prompt (no examples — Gemini follows the spec).
  * Compact passage format `[#1@00:12-00:48] text`.
  * History is truncated to last 6 turns by default in PromptBuilder.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

SYSTEM_PROMPT_CHAT = (
    "You answer questions about user-supplied videos using ONLY the retrieved "
    "passages and prior conversation. Cite every fact with the passage tag "
    "(e.g. [#2]). If the passages do not contain the answer, say you don't know. "
    "Default to 3-5 concise sentences. Mention timestamps when helpful."
)

SYSTEM_PROMPT_SUMMARY = (
    "Produce a 2-3 sentence overview, then 5-8 bullets each ending with the "
    "timestamp (mm:ss). Output strict markdown."
)

SYSTEM_PROMPT_QUERY_EXPAND = (
    "Rewrite the user's question into 3 short alternative search queries that "
    "preserve intent. One query per line, no numbering."
)

SYSTEM_PROMPT_MEMORY_SUMMARY = (
    "Summarize this conversation as long-term memory. Capture goals, key "
    "entities, expressed preferences, and conclusions. Under 200 words."
)

SYSTEM_PROMPT_PREFERENCE_EXTRACT = (
    "Extract durable user preferences as a single JSON object. Only durable "
    "facts (language, topic interests, response style). No commentary."
)


@dataclass
class ChatPrompt:
    system: str
    contents: list[dict]


class PromptBuilder:
    def build_chat(
        self,
        *,
        user_question: str,
        retrieved_context: str,
        history_turns: Sequence[dict] = (),
        long_term_summary: str | None = None,
        user_profile: dict | None = None,
        history_limit: int = 6,
    ) -> ChatPrompt:
        parts: list[str] = []
        if long_term_summary:
            parts.append(f"## Memory\n{long_term_summary}")
        if user_profile:
            compact = ", ".join(f"{k}={v}" for k, v in user_profile.items() if v is not None)
            if compact:
                parts.append(f"## User\n{compact}")
        if retrieved_context:
            parts.append(f"## Passages\n{retrieved_context}")
        else:
            parts.append("## Passages\n(none — say you don't know if not general knowledge)")
        parts.append(f"## Q\n{user_question}")

        contents: list[dict] = []
        for turn in list(history_turns)[-history_limit:]:
            role = "user" if turn["role"] == "user" else "model"
            contents.append({"role": role, "parts": [{"text": turn["content"]}]})
        contents.append({"role": "user", "parts": [{"text": "\n\n".join(parts)}]})
        return ChatPrompt(system=SYSTEM_PROMPT_CHAT, contents=contents)

    def build_summary(self, transcript_excerpt: str) -> ChatPrompt:
        return ChatPrompt(
            system=SYSTEM_PROMPT_SUMMARY,
            contents=[{"role": "user", "parts": [{"text": transcript_excerpt}]}],
        )

    def build_query_expansion(self, query: str) -> ChatPrompt:
        return ChatPrompt(
            system=SYSTEM_PROMPT_QUERY_EXPAND,
            contents=[{"role": "user", "parts": [{"text": query}]}],
        )

    def build_memory_summary(self, transcript: str) -> ChatPrompt:
        return ChatPrompt(
            system=SYSTEM_PROMPT_MEMORY_SUMMARY,
            contents=[{"role": "user", "parts": [{"text": transcript}]}],
        )

    def build_preference_extraction(self, transcript: str) -> ChatPrompt:
        return ChatPrompt(
            system=SYSTEM_PROMPT_PREFERENCE_EXTRACT,
            contents=[{"role": "user", "parts": [{"text": transcript}]}],
        )
