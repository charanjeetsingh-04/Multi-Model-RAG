"""Local filesystem backend."""
from __future__ import annotations

from pathlib import Path

import aiofiles.os

from app.storage.base import StorageBackend


class LocalStorage(StorageBackend):
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def _resolve(self, key: str) -> Path:
        # Keys here are already absolute paths produced by `build_storage_path`
        return Path(key)

    async def exists(self, key: str) -> bool:
        return await aiofiles.os.path.exists(self._resolve(key))

    async def get_local_path(self, key: str) -> Path:
        return self._resolve(key)

    async def delete(self, key: str) -> None:
        p = self._resolve(key)
        if await aiofiles.os.path.exists(p):
            await aiofiles.os.remove(p)

    def public_url(self, key: str) -> str | None:
        return None  # local backend isn't web-served by default
