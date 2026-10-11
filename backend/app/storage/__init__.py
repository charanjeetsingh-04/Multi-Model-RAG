"""Storage backends — local FS + S3 behind a common interface."""
from app.storage.base import StorageBackend
from app.storage.factory import get_storage

__all__ = ["StorageBackend", "get_storage"]
