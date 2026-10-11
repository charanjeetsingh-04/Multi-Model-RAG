"""Lightweight Redis-list queue (no extra dependencies beyond redis-py).

Production hardening notes:
  * For at-least-once semantics, use a sorted-set + visibility timeout.
  * For richer features (retries with backoff, dead-letter), swap in RQ or
    Celery. The producer/consumer interface stays the same.
"""
from __future__ import annotations

import json
from typing import Any

import redis.asyncio as redis_async

from app.core.config import settings

VIDEO_PROCESS_QUEUE = "queue:video:process"


class TaskQueue:
    def __init__(self, url: str | None = None) -> None:
        self._client = redis_async.from_url(url or settings.REDIS_URL, decode_responses=True)

    async def enqueue(self, queue: str, payload: dict[str, Any]) -> None:
        await self._client.rpush(queue, json.dumps(payload, default=str))

    async def dequeue(self, queue: str, timeout: int = 5) -> dict[str, Any] | None:
        result = await self._client.blpop(queue, timeout=timeout)
        if not result:
            return None
        _, raw = result
        return json.loads(raw)


_queue: TaskQueue | None = None


def get_queue() -> TaskQueue:
    global _queue
    if _queue is None:
        _queue = TaskQueue()
    return _queue
