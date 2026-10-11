"""@cached and @invalidates — for service methods.

Usage:

    @cached(lambda self, user_id: CacheKeys.profile(user_id), ttl=120)
    async def get_user_profile(self, user_id):
        ...

    @invalidates(lambda self, conv_id: CacheKeys.conv_pattern(conv_id))
    async def append_message(self, conv_id, ...):
        ...

The key-builder is a function of the same args as the wrapped method, so the
cache key is co-located with the method that owns it.
"""
from __future__ import annotations

import functools
from typing import Any, Awaitable, Callable

from app.cache.backend import get_cache

KeyBuilder = Callable[..., str]


def cached(key_builder: KeyBuilder, ttl: int = 300):
    def decorator(fn: Callable[..., Awaitable[Any]]):
        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            cache = get_cache()
            key = key_builder(*args, **kwargs)
            hit = await cache.get(key)
            if hit is not None:
                return hit
            value = await fn(*args, **kwargs)
            if value is not None:
                await cache.set(key, value, ttl=ttl)
            return value

        return wrapper

    return decorator


def invalidates(*key_builders: KeyBuilder):
    """Run the method, then bust every key produced. Patterns ending in `*`
    use SCAN-based prefix delete."""

    def decorator(fn: Callable[..., Awaitable[Any]]):
        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            result = await fn(*args, **kwargs)
            cache = get_cache()
            for builder in key_builders:
                key = builder(*args, **kwargs)
                if key.endswith("*"):
                    await cache.delete_pattern(key)
                else:
                    await cache.delete(key)
            return result

        return wrapper

    return decorator
