"""Storage interface — kept small so swapping is trivial."""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class StorageBackend(ABC):
    @abstractmethod
    async def exists(self, key: str) -> bool: ...

    @abstractmethod
    async def get_local_path(self, key: str) -> Path:
        """Return a real filesystem path (downloads if remote)."""

    @abstractmethod
    async def delete(self, key: str) -> None: ...

    @abstractmethod
    def public_url(self, key: str) -> str | None:
        """Return a URL the frontend can hit, or None if not exposed."""
