"""FastAPI dependency providers.

We deliberately stick with `Depends(...)` over a heavy DI container — it's
already a fully-typed DI graph, and routes stay readable.

Conventions:
  * `Provide*Repository` returns a repo bound to the request's DB session.
  * `Provide*Service`    returns a service wired with its repos and the cache.
  * Singletons (embedder, LLM client) live in their own modules.
"""
from app.dependencies.repositories import (
    ProvideConversationRepository,
    ProvideMessageRepository,
    ProvideUserPreferenceRepository,
    ProvideUserRepository,
    ProvideVideoChunkRepository,
    ProvideVideoRepository,
)
from app.dependencies.services import (
    ProvideChatService,
    ProvideMemoryService,
    ProvideUserService,
    ProvideVideoService,
)

__all__ = [
    "ProvideConversationRepository",
    "ProvideMessageRepository",
    "ProvideUserPreferenceRepository",
    "ProvideUserRepository",
    "ProvideVideoChunkRepository",
    "ProvideVideoRepository",
    "ProvideChatService",
    "ProvideMemoryService",
    "ProvideUserService",
    "ProvideVideoService",
]
