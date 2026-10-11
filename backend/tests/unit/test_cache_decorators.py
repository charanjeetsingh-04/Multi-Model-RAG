"""Cache decorator behavior."""
from __future__ import annotations

import pytest

from app.cache import cached, invalidates
from app.cache.backend import NullCache


class _StubCache:
    def __init__(self):
        self.store = {}
        self.hits = 0
        self.misses = 0
        self.deletes = 0
        self.deleted_patterns: list[str] = []

    async def get(self, key):
        v = self.store.get(key)
        if v is None:
            self.misses += 1
            return None
        self.hits += 1
        return v

    async def set(self, key, value, ttl=300):
        self.store[key] = value

    async def delete(self, key):
        self.deletes += 1
        self.store.pop(key, None)

    async def delete_pattern(self, pattern):
        self.deleted_patterns.append(pattern)
        return 0


@pytest.mark.asyncio
async def test_cached_decorator(monkeypatch):
    from app.cache import backend as bm

    stub = _StubCache()
    monkeypatch.setattr(bm, "_cache", stub)

    calls = {"n": 0}

    @cached(lambda k: f"x:{k}", ttl=10)
    async def expensive(k):
        calls["n"] += 1
        return {"value": k * 2}

    a = await expensive(3)
    b = await expensive(3)
    assert a == b == {"value": 6}
    assert calls["n"] == 1   # second call served from cache
    assert stub.hits == 1


@pytest.mark.asyncio
async def test_invalidates_pattern(monkeypatch):
    from app.cache import backend as bm

    stub = _StubCache()
    monkeypatch.setattr(bm, "_cache", stub)

    @invalidates(lambda k: f"y:{k}:*")
    async def mutate(k):
        return k

    await mutate("abc")
    assert stub.deleted_patterns == ["y:abc:*"]
