"""Embedding model wrapper with Redis content-hash cache.

Why cache: many user queries are repeats ("summarize", "what was the conclusion").
Each cache hit avoids ~30-80ms of CPU work on the embedding model.

Cache layer is opt-in per call (`use_cache=True` on `embed_query`). Batch
embeddings during ingest are not cached — they're one-shot and saving the
cache writes would cost more than the lookups save.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from functools import lru_cache
from typing import Sequence

import numpy as np

from app.cache import CacheKeys, get_cache
from app.core.config import settings
from app.core.logging import get_logger
from app.monitoring.metrics import EMBED_CACHE

logger = get_logger(__name__)


class Embedder(ABC):
    dimension: int
    model_name: str

    @abstractmethod
    def embed_query(self, text: str) -> np.ndarray: ...

    @abstractmethod
    def embed_batch(self, texts: Sequence[str]) -> np.ndarray: ...

    async def embed_query_cached(self, text: str) -> np.ndarray:
        """Async wrapper that consults Redis before running the model."""
        cache = get_cache()
        key = CacheKeys.embedding(text, self.model_name)
        hit = await cache.get(key)
        if hit is not None:
            EMBED_CACHE.labels(result="hit").inc()
            return np.asarray(hit, dtype=np.float32)
        EMBED_CACHE.labels(result="miss").inc()
        vec = self.embed_query(text)
        await cache.set(key, vec.tolist(), ttl=86400)  # 24h
        return vec


class SentenceTransformerEmbedder(Embedder):
    def __init__(self, model_name: str, device: str, batch_size: int) -> None:
        from sentence_transformers import SentenceTransformer  # noqa: PLC0415

        logger.info("loading_embedder", model=model_name, device=device)
        self._model = SentenceTransformer(model_name, device=device)
        self.batch_size = batch_size
        self.model_name = model_name
        self.dimension = int(self._model.get_sentence_embedding_dimension())

    def embed_query(self, text: str) -> np.ndarray:
        vec = self._model.encode([text], normalize_embeddings=True, show_progress_bar=False)
        return np.asarray(vec[0], dtype=np.float32)

    def embed_batch(self, texts: Sequence[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dimension), dtype=np.float32)
        vecs = self._model.encode(
            list(texts),
            batch_size=self.batch_size,
            normalize_embeddings=True,
            show_progress_bar=False,
            convert_to_numpy=True,
        )
        return np.asarray(vecs, dtype=np.float32)


@lru_cache(maxsize=1)
def get_embedder() -> Embedder:
    return SentenceTransformerEmbedder(
        settings.EMBEDDING_MODEL,
        settings.EMBEDDING_DEVICE,
        settings.EMBEDDING_BATCH_SIZE,
    )
