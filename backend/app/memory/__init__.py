"""Compat shim — MemoryService moved to `app.services.memory_service`."""
from app.services.memory_service import MemoryService

__all__ = ["MemoryService"]
