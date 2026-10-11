"""Hybrid retriever — dense + sparse + RRF + optional rerank.

v2 optimizations:
  * Takes a `VideoChunkRepository` (not a raw session).
  * Embeds the query through `embed_query_cached` (Redis hit avoids CPU).
  * Dense (vector store) + BM25 (over PG-loaded chunks) run concurrently in
    threads — saves ~40-80ms on multi-chunk libraries.
  * Identical (user, video, query) retrievals are cached in Redis for 30s.
  * Reranker is loaded lazily and cached.
"""
from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from typing import Sequence

import numpy as np
from rank_bm25 import BM25Okapi

from app.cache import CacheKeys, get_cache
from app.core.config import settings
from app.core.logging import get_logger
from app.embeddings.embedder import get_embedder
from app.models.video import VideoChunk
from app.monitoring.metrics import RETRIEVAL_LATENCY
from app.rag.vector_store import VectorRecord, get_vector_store
from app.repositories.video_repository import VideoChunkRepository

logger = get_logger(__name__)


@dataclass
class RetrievedChunk:
    chunk_id: uuid.UUID
    video_id: uuid.UUID
    text: str
    score: float
    start_time: float | None
    end_time: float | None
    metadata: dict = field(default_factory=dict)


class HybridRetriever:
    def __init__(self, chunks: VideoChunkRepository) -> None:
        self.chunks = chunks
        self.embedder = get_embedder()
        self.vector_store = get_vector_store()
        self._reranker = None

    async def retrieve(
        self,
        query: str,
        *,
        user_id: uuid.UUID,
        video_id: uuid.UUID | None = None,
        top_k: int | None = None,
    ) -> list[RetrievedChunk]:
        top_k = top_k or settings.RETRIEVAL_TOP_K
        query = (query or "").strip()
        if not query:
            return []

        # Short-circuit: cached recent retrieval for this exact query+scope
        cache = get_cache()
        cache_key = CacheKeys.retrieval(user_id, video_id, query, top_k)
        cached_hit = await cache.get(cache_key)
        if cached_hit:
            return [_from_cache(d) for d in cached_hit]

        t0 = time.perf_counter()
        # Run query embedding + chunk listing concurrently.
        q_vec_task = asyncio.create_task(self.embedder.embed_query_cached(query))
        candidates_task = asyncio.create_task(self.chunks.list_ready_for_owner(user_id, video_id=video_id))
        q_vec, candidates = await asyncio.gather(q_vec_task, candidates_task)

        if not candidates:
            RETRIEVAL_LATENCY.observe(time.perf_counter() - t0)
            return []

        # Dense + sparse in parallel.
        filter_meta = {"user_id": str(user_id)}
        if video_id is not None:
            filter_meta["video_id"] = str(video_id)
        dense_task = asyncio.to_thread(self.vector_store.search, q_vec, top_k * 2, filter_meta)
        sparse_task = asyncio.to_thread(self._bm25_search, query, candidates, top_k * 2)
        dense_hits, bm25_hits = await asyncio.gather(dense_task, sparse_task)

        fused = self._rrf_fuse(dense_hits, bm25_hits)

        chunk_map = {str(c.id): c for c in candidates}
        results: list[RetrievedChunk] = []
        for chunk_id_str, score in fused[: top_k * 2]:
            chunk = chunk_map.get(chunk_id_str)
            if not chunk:
                continue
            results.append(
                RetrievedChunk(
                    chunk_id=chunk.id,
                    video_id=chunk.video_id,
                    text=chunk.text,
                    score=score,
                    start_time=chunk.start_time,
                    end_time=chunk.end_time,
                    metadata=chunk.extra_metadata or {},
                )
            )

        if settings.USE_RERANKER and len(results) > 1:
            results = await asyncio.to_thread(
                self._rerank, query, results, settings.RERANK_TOP_K or top_k
            )
        else:
            results = results[:top_k]

        RETRIEVAL_LATENCY.observe(time.perf_counter() - t0)
        logger.info(
            "retrieval_done",
            query_len=len(query),
            dense=len(dense_hits),
            sparse=len(bm25_hits),
            returned=len(results),
            ms=int((time.perf_counter() - t0) * 1000),
        )
        # Cache (lightweight payload) for 30s.
        await cache.set(cache_key, [_to_cache(r) for r in results], ttl=30)
        return results

    # ---- internals -----------------------------------------------------
    def _bm25_search(
        self, query: str, chunks: Sequence[VideoChunk], top_k: int
    ) -> list[VectorRecord]:
        if not settings.USE_HYBRID_SEARCH or not chunks:
            return []
        tokenized = [c.text.lower().split() for c in chunks]
        bm25 = BM25Okapi(tokenized)
        scores = bm25.get_scores(query.lower().split())
        order = np.argsort(scores)[::-1][:top_k]
        return [
            VectorRecord(id=str(chunks[i].id), score=float(scores[i]))
            for i in order
            if scores[i] > 0
        ]

    @staticmethod
    def _rrf_fuse(
        dense: list[VectorRecord],
        sparse: list[VectorRecord],
        k: int = 60,
    ) -> list[tuple[str, float]]:
        scores: dict[str, float] = {}
        for rank, rec in enumerate(dense):
            scores[rec.id] = scores.get(rec.id, 0.0) + 1.0 / (k + rank)
        for rank, rec in enumerate(sparse):
            scores[rec.id] = scores.get(rec.id, 0.0) + 1.0 / (k + rank)
        return sorted(scores.items(), key=lambda x: x[1], reverse=True)

    def _get_reranker(self):
        if self._reranker is None:
            from sentence_transformers import CrossEncoder  # noqa: PLC0415

            self._reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
        return self._reranker

    def _rerank(
        self,
        query: str,
        candidates: list[RetrievedChunk],
        top_k: int,
    ) -> list[RetrievedChunk]:
        try:
            model = self._get_reranker()
            pairs = [(query, c.text) for c in candidates]
            scores = model.predict(pairs)
            for c, s in zip(candidates, scores):
                c.score = float(s)
            return sorted(candidates, key=lambda x: x.score, reverse=True)[:top_k]
        except Exception as e:  # noqa: BLE001
            logger.warning("rerank_failed_fallback", error=str(e))
            return candidates[:top_k]


def _to_cache(r: RetrievedChunk) -> dict:
    return {
        "chunk_id": str(r.chunk_id),
        "video_id": str(r.video_id),
        "text": r.text,
        "score": r.score,
        "start_time": r.start_time,
        "end_time": r.end_time,
        "metadata": r.metadata,
    }


def _from_cache(d: dict) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=uuid.UUID(d["chunk_id"]),
        video_id=uuid.UUID(d["video_id"]),
        text=d["text"],
        score=d["score"],
        start_time=d.get("start_time"),
        end_time=d.get("end_time"),
        metadata=d.get("metadata") or {},
    )
