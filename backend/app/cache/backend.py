"""Cache backends.

* `RedisCache` — the real thing, used in dev + prod.
* `NullCache`  — no-op, used when REDIS_ENABLED=false or Redis is down.

Both implement the same protocol so the rest of the code never branches.
Values are stored as orjson (faster + handles datetime/UUID).
"""
from __future__ import annotations

import asyncio
from typing import Any, Protocol

import orjson
import redis.asyncio as redis_async
from prometheus_client import Counter

from app.core.config import settings
from app.core.logging import get_logger
from app.monitoring.metrics import CACHE_OPS

logger = get_logger(__name__)


class Cache(Protocol):
    async def get(self, key: str) -> Any | None: ...
    async def set(self, key: str, value: Any, ttl: int = 300) -> None: ...
    async def delete(self, key: str) -> None: ...
    async def delete_pattern(self, pattern: str) -> int: ...
    async def incr(self, key: str, ttl: int | None = None) -> int: ...
    async def ping(self) -> bool: ...


class NullCache:
    async def get(self, key: str) -> Any | None:  # noqa: D401
        CACHE_OPS.labels(op="miss").inc()
        return None

    async def set(self, key: str, value: Any, ttl: int = 300) -> None:
        return None

    async def delete(self, key: str) -> None:
        return None

    async def delete_pattern(self, pattern: str) -> int:
        return 0

    async def incr(self, key: str, ttl: int | None = None) -> int:
        return 0

    async def ping(self) -> bool:
        return False


class RedisCache:
    def __init__(self, url: str, *, namespace: str = "vrag") -> None:
        # `decode_responses=False` — we manage bytes so we can store orjson.
        self._client = redis_async.from_url(url, decode_responses=False)
        self.namespace = namespace

    def _k(self, key: str) -> str:
        return f"{self.namespace}:{key}"

    async def get(self, key: str) -> Any | None:
        try:
            raw = await self._client.get(self._k(key))
            if raw is None:
                CACHE_OPS.labels(op="miss").inc()
                return None
            CACHE_OPS.labels(op="hit").inc()
            return orjson.loads(raw)
        except Exception as e:  # noqa: BLE001
            logger.warning("cache_get_failed", key=key, error=str(e))
            CACHE_OPS.labels(op="miss").inc()
            return None

    async def set(self, key: str, value: Any, ttl: int = 300) -> None:
        try:
            await self._client.set(self._k(key), orjson.dumps(value, default=str), ex=ttl)
            CACHE_OPS.labels(op="set").inc()
        except Exception as e:  # noqa: BLE001
            logger.warning("cache_set_failed", key=key, error=str(e))

    async def delete(self, key: str) -> None:
        try:
            await self._client.delete(self._k(key))
            CACHE_OPS.labels(op="invalidate").inc()
        except Exception as e:  # noqa: BLE001
            logger.warning("cache_del_failed", key=key, error=str(e))

    async def delete_pattern(self, pattern: str) -> int:
        """SCAN-based prefix invalidation (KEYS is O(N) blocking — never use it)."""
        deleted = 0
        try:
            async for found in self._client.scan_iter(self._k(pattern)):
                await self._client.delete(found)
                deleted += 1
            CACHE_OPS.labels(op="invalidate").inc()
        except Exception as e:  # noqa: BLE001
            logger.warning("cache_del_pattern_failed", pattern=pattern, error=str(e))
        return deleted

    async def incr(self, key: str, ttl: int | None = None) -> int:
        try:
            full = self._k(key)
            pipe = self._client.pipeline()
            pipe.incr(full)
            if ttl:
                pipe.expire(full, ttl)
            result = await pipe.execute()
            return int(result[0])
        except Exception as e:  # noqa: BLE001
            logger.warning("cache_incr_failed", key=key, error=str(e))
            return 0

    async def ping(self) -> bool:
        try:
            return bool(await self._client.ping())
        except Exception:
            return False


# ---- singleton -----------------------------------------------------------
_cache: Cache | None = None


def get_cache() -> Cache:
    global _cache
    if _cache is not None:
        return _cache
    if not settings.REDIS_ENABLED:
        _cache = NullCache()
    else:
        try:
            _cache = RedisCache(settings.REDIS_URL, namespace=settings.APP_NAME)
        except Exception as e:  # noqa: BLE001
            logger.warning("redis_unavailable_fallback_null", error=str(e))
            _cache = NullCache()
    return _cache
