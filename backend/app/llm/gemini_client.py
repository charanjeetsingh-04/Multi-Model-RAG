"""Gemini 2.5 Flash client.

v2 additions:
  * `count_tokens()` — exposed for budget enforcement before sending a prompt.
  * 60-second idempotency cache keyed on prompt fingerprint, so a client
    retry doesn't double-bill tokens.
  * Maps Gemini block/timeout exceptions to typed `LLMBlocked` / `LLMTimeout`.
"""
from __future__ import annotations

import asyncio
import hashlib
import time
from dataclasses import dataclass
from functools import lru_cache
from typing import AsyncIterator

import google.generativeai as genai
import orjson
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.cache import CacheKeys, get_cache
from app.core.config import settings
from app.core.exceptions import ExternalServiceError, LLMBlockedError, LLMTimeoutError
from app.core.logging import get_logger
from app.llm.prompts import ChatPrompt
from app.monitoring.metrics import LLM_LATENCY, LLM_REQUESTS, LLM_TOKENS

logger = get_logger(__name__)


@dataclass
class LLMResponse:
    text: str
    tokens_in: int | None = None
    tokens_out: int | None = None
    latency_ms: int = 0


def _fingerprint(prompt: ChatPrompt) -> str:
    payload = orjson.dumps({"sys": prompt.system, "contents": prompt.contents})
    return hashlib.sha256(payload).hexdigest()[:32]


class GeminiClient:
    def __init__(self, api_key: str, model_name: str) -> None:
        if not api_key:
            raise ExternalServiceError(message="GEMINI_API_KEY is not configured")
        genai.configure(api_key=api_key)
        self.model_name = model_name
        self._generation_config = genai.types.GenerationConfig(
            temperature=settings.GEMINI_TEMPERATURE,
            top_p=settings.GEMINI_TOP_P,
            max_output_tokens=settings.GEMINI_MAX_OUTPUT_TOKENS,
        )

    def _model(self, system_instruction: str | None) -> genai.GenerativeModel:
        return genai.GenerativeModel(
            model_name=self.model_name,
            generation_config=self._generation_config,
            system_instruction=system_instruction,
        )

    async def count_tokens(self, prompt: ChatPrompt) -> int:
        model = self._model(prompt.system)
        try:
            result = await asyncio.to_thread(model.count_tokens, prompt.contents)
            return int(result.total_tokens)
        except Exception as e:  # noqa: BLE001
            logger.warning("token_count_failed", error=str(e))
            return -1

    async def complete(self, prompt: ChatPrompt) -> LLMResponse:
        cache = get_cache()
        fp = _fingerprint(prompt)
        cache_key = CacheKeys.llm_response(fp)
        cached = await cache.get(cache_key)
        if cached:
            LLM_REQUESTS.labels(model=self.model_name, status="cache_hit").inc()
            return LLMResponse(**cached)

        start = time.perf_counter()

        async def _attempt() -> LLMResponse:
            model = self._model(prompt.system)
            resp = await asyncio.to_thread(model.generate_content, prompt.contents)
            text = (resp.text or "").strip()
            usage = getattr(resp, "usage_metadata", None)
            return LLMResponse(
                text=text,
                tokens_in=getattr(usage, "prompt_token_count", None) if usage else None,
                tokens_out=getattr(usage, "candidates_token_count", None) if usage else None,
                latency_ms=int((time.perf_counter() - start) * 1000),
            )

        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(3),
                wait=wait_exponential(multiplier=0.5, min=1, max=8),
                retry=retry_if_exception_type(Exception),
                reraise=True,
            ):
                with attempt:
                    response = await _attempt()
                    LLM_REQUESTS.labels(model=self.model_name, status="ok").inc()
                    LLM_LATENCY.labels(model=self.model_name).observe(response.latency_ms / 1000.0)
                    if response.tokens_in:
                        LLM_TOKENS.labels(model=self.model_name, kind="in").inc(response.tokens_in)
                    if response.tokens_out:
                        LLM_TOKENS.labels(model=self.model_name, kind="out").inc(response.tokens_out)
                    await cache.set(
                        cache_key,
                        {
                            "text": response.text,
                            "tokens_in": response.tokens_in,
                            "tokens_out": response.tokens_out,
                            "latency_ms": response.latency_ms,
                        },
                        ttl=60,
                    )
                    return response
        except asyncio.TimeoutError as e:
            LLM_REQUESTS.labels(model=self.model_name, status="timeout").inc()
            raise LLMTimeoutError(message="Gemini timed out") from e
        except Exception as e:  # noqa: BLE001
            LLM_REQUESTS.labels(model=self.model_name, status="error").inc()
            msg = str(e).lower()
            if "blocked" in msg or "safety" in msg:
                raise LLMBlockedError(message="Gemini blocked the request") from e
            logger.exception("gemini_failed")
            raise ExternalServiceError(message=f"Gemini call failed: {e}") from e
        raise ExternalServiceError(message="Gemini call failed without retry decision")

    async def stream(self, prompt: ChatPrompt) -> AsyncIterator[str]:
        start = time.perf_counter()
        model = self._model(prompt.system)

        def _open_stream():
            return model.generate_content(prompt.contents, stream=True)

        try:
            response_iter = await asyncio.to_thread(_open_stream)
        except Exception as e:  # noqa: BLE001
            raise ExternalServiceError(message=f"Gemini stream open failed: {e}") from e

        async def _aiter() -> AsyncIterator[str]:
            try:
                while True:
                    chunk = await asyncio.to_thread(_safe_next, response_iter)
                    if chunk is _SENTINEL:
                        break
                    if chunk is None:
                        continue
                    text = getattr(chunk, "text", "") or ""
                    if text:
                        yield text
                LLM_LATENCY.labels(model=self.model_name).observe(time.perf_counter() - start)
            except Exception as e:  # noqa: BLE001
                logger.exception("gemini_stream_error")
                raise ExternalServiceError(message=f"Gemini stream error: {e}") from e

        return _aiter()


_SENTINEL = object()


def _safe_next(gen):
    try:
        return next(gen)
    except StopIteration:
        return _SENTINEL


@lru_cache(maxsize=1)
def get_llm_client() -> GeminiClient:
    return GeminiClient(settings.GEMINI_API_KEY, settings.GEMINI_MODEL)
