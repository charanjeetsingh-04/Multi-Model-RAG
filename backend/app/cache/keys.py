"""Single source of truth for cache key shapes.

Each method is namespace-scoped so cache busts hit the right prefix only.
Examples:
    CacheKeys.user(user_id)              -> "user:<uuid>"
    CacheKeys.user_pattern(user_id)      -> "user:<uuid>:*"
    CacheKeys.short_term(conv_id)        -> "conv:<uuid>:shortmem"
    CacheKeys.profile(user_id)           -> "user:<uuid>:profile"
    CacheKeys.embedding(content_hash)    -> "emb:<sha256>"
"""
from __future__ import annotations

import hashlib
import uuid


class CacheKeys:
    # --- user ---
    @staticmethod
    def user(user_id: uuid.UUID | str) -> str:
        return f"user:{user_id}"

    @staticmethod
    def user_pattern(user_id: uuid.UUID | str) -> str:
        return f"user:{user_id}:*"

    @staticmethod
    def profile(user_id: uuid.UUID | str) -> str:
        return f"user:{user_id}:profile"

    @staticmethod
    def preferences(user_id: uuid.UUID | str) -> str:
        return f"user:{user_id}:prefs"

    # --- conversation ---
    @staticmethod
    def short_term(conv_id: uuid.UUID | str) -> str:
        return f"conv:{conv_id}:shortmem"

    @staticmethod
    def long_term(conv_id: uuid.UUID | str) -> str:
        return f"conv:{conv_id}:longmem"

    @staticmethod
    def conv_pattern(conv_id: uuid.UUID | str) -> str:
        return f"conv:{conv_id}:*"

    # --- embeddings (deterministic by content) ---
    @staticmethod
    def embedding(content: str, model: str) -> str:
        h = hashlib.sha256(f"{model}::{content}".encode("utf-8")).hexdigest()[:32]
        return f"emb:{h}"

    # --- retrieval (cache results of identical queries) ---
    @staticmethod
    def retrieval(user_id: uuid.UUID | str, video_id: uuid.UUID | str | None, query: str, top_k: int) -> str:
        h = hashlib.sha256(query.strip().lower().encode("utf-8")).hexdigest()[:16]
        scope = video_id or "all"
        return f"retr:{user_id}:{scope}:{top_k}:{h}"

    # --- LLM responses (small idempotency cache for retries) ---
    @staticmethod
    def llm_response(prompt_fingerprint: str) -> str:
        return f"llm:resp:{prompt_fingerprint}"
