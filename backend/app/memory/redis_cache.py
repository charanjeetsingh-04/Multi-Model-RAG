"""Optional Redis layer for short-term memory.

When REDIS_ENABLED=false (e.g. local quick-start), this becomes a no-op stub —
callers can use the same API. Useful so prod deploys benefit from cache hits
without dev needing Redis running.
"""
from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

import redis.asyncio as redis_async

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class _NullCache:
    async def get(self, key: str) -> Any | None:
        return None

    async def set(self, key: str, value: Any, ttl: int = 3600) -> None:
        return None

    async def delete(self, key: str) -> None:
        return None


class RedisCache:
    def __init__(self, url: str) -> None:
        self._client = redis_async.from_url(url, decode_responses=True)

    async def get(self, key: str) -> Any | None:
        try:
            raw = await self._client.get(key)
            return json.loads(raw) if raw else None
        except Exception as e:  # noqa: BLE001
            logger.warning("redis_get_failed", key=key, error=str(e))
            return None

    async def set(self, key: str, value: Any, ttl: int = 3600) -> None:
        try:
            await self._client.set(key, json.dumps(value, default=str), ex=ttl)
        except Exception as e:  # noqa: BLE001
            logger.warning("redis_set_failed", key=key, error=str(e))

    async def delete(self, key: str) -> None:
        try:
            await self._client.delete(key)
        except Exception as e:  # noqa: BLE001
            logger.warning("redis_del_failed", key=key, error=str(e))


@lru_cache(maxsize=1)
def get_cache() -> RedisCache | _NullCache:
    if not settings.REDIS_ENABLED:
        return _NullCache()
    try:
        return RedisCache(settings.REDIS_URL)
    except Exception as e:  # noqa: BLE001
        logger.warning("redis_unavailable_fallback_null", error=str(e))
        return _NullCache()
