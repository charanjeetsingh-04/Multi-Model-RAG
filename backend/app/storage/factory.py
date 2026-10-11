"""Storage factory — single source of truth for which backend is active."""
from __future__ import annotations

from functools import lru_cache

from app.core.config import settings
from app.storage.base import StorageBackend
from app.storage.local import LocalStorage


@lru_cache(maxsize=1)
def get_storage() -> StorageBackend:
    if settings.STORAGE_BACKEND == "s3":
        from app.storage.s3 import S3Storage  # lazy import — boto only on demand

        return S3Storage()
    return LocalStorage(settings.UPLOAD_DIR)
