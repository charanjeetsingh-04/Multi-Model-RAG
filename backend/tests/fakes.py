"""Tiny in-memory fakes for repositories.

Used in service unit tests. They implement just enough of the repo surface
to exercise behavior without spinning up Postgres.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any


class _Store:
    def __init__(self) -> None:
        self.items: dict[uuid.UUID, Any] = {}

    def add(self, entity):
        eid = getattr(entity, "id", None) or uuid.uuid4()
        if not getattr(entity, "id", None):
            entity.id = eid
        if not getattr(entity, "created_at", None):
            entity.created_at = datetime.now(timezone.utc)
        entity.updated_at = datetime.now(timezone.utc)
        self.items[eid] = entity
        return entity


class FakeUserRepository:
    def __init__(self):
        self._store = _Store()

    def add(self, e): return self._store.add(e)
    async def flush(self): return None

    async def get_by_id(self, uid, with_preferences=False):
        return self._store.items.get(uid)

    async def get_by_email(self, email, with_preferences=False):
        for u in self._store.items.values():
            if u.email == email.lower():
                return u
        return None

    async def get_by_username(self, username):
        for u in self._store.items.values():
            if u.username == username:
                return u
        return None

    async def list_recent(self, limit=200):
        return list(self._store.items.values())[:limit]


class FakeUserPreferenceRepository:
    def __init__(self):
        self._store = _Store()

    def add(self, e): return self._store.add(e)
    async def flush(self): return None

    async def get_by_user(self, user_id):
        for p in self._store.items.values():
            if p.user_id == user_id:
                return p
        return None


class FakeConversationRepository:
    def __init__(self):
        self._store = _Store()

    def add(self, e): return self._store.add(e)
    async def flush(self): return None
    async def delete(self, e): self._store.items.pop(e.id, None)

    async def get(self, cid): return self._store.items.get(cid)

    async def get_for_user(self, cid, user_id, with_messages=False):
        c = self._store.items.get(cid)
        return c if c and c.user_id == user_id else None

    async def list_for_user(self, user_id, limit=100):
        return [c for c in self._store.items.values() if c.user_id == user_id][:limit]

    async def increment_message_count(self, cid, delta=1):
        c = self._store.items.get(cid)
        if c:
            c.message_count += delta

    async def set_summary(self, cid, summary):
        c = self._store.items.get(cid)
        if c:
            c.summary = summary


class FakeMessageRepository:
    def __init__(self):
        self._store = _Store()

    def add(self, e): return self._store.add(e)
    async def flush(self): return None

    async def list_for_conversation(self, cid):
        return sorted(
            [m for m in self._store.items.values() if m.conversation_id == cid],
            key=lambda m: m.created_at,
        )

    async def list_recent(self, cid, limit):
        items = sorted(
            [m for m in self._store.items.values() if m.conversation_id == cid],
            key=lambda m: m.created_at,
            reverse=True,
        )[:limit]
        return items[::-1]
