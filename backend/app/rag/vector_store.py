"""Pluggable vector store.

Two implementations:
  * FAISSVectorStore — single index file on disk, ID-mapped for safe deletes.
  * ChromaVectorStore — persistent collection on disk, richer metadata
    filters (handy when the dataset grows past a single index).

Both expose the same interface so retrievers don't care which is active.
"""
from __future__ import annotations

import json
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Sequence

import numpy as np

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class VectorRecord:
    id: str                              # our chunk UUID as string
    score: float
    metadata: dict = field(default_factory=dict)


class VectorStore(ABC):
    dim: int

    @abstractmethod
    def add(self, ids: Sequence[str], vectors: np.ndarray, metadatas: Sequence[dict]) -> None: ...

    @abstractmethod
    def search(
        self,
        query_vector: np.ndarray,
        top_k: int,
        filter_metadata: dict | None = None,
    ) -> list[VectorRecord]: ...

    @abstractmethod
    def delete(self, ids: Sequence[str]) -> None: ...

    @abstractmethod
    def persist(self) -> None: ...

    @abstractmethod
    def count(self) -> int: ...


# --------------------------------------------------------------------------
# FAISS implementation
# --------------------------------------------------------------------------
class FAISSVectorStore(VectorStore):
    """FAISS IndexIDMap2 wrapping a flat inner-product index.

    Why IndexIDMap2: lets us tag each vector with a deterministic int64 ID
    (hash of chunk UUID) so deletes are clean. Metadata + reverse lookup
    are kept in a sidecar JSON file because FAISS itself stores no metadata.
    """

    def __init__(self, path: Path, dim: int) -> None:
        import faiss  # noqa: PLC0415

        self.path = path
        self.dim = dim
        self._lock = threading.RLock()
        path.mkdir(parents=True, exist_ok=True)
        self.index_file = path / "index.faiss"
        self.meta_file = path / "meta.json"

        base = faiss.IndexFlatIP(dim)
        self._index = faiss.IndexIDMap2(base)
        self._id_to_meta: dict[str, dict] = {}
        self._int_to_uuid: dict[int, str] = {}

        if self.index_file.exists() and self.meta_file.exists():
            try:
                self._index = faiss.read_index(str(self.index_file))
                state = json.loads(self.meta_file.read_text("utf-8"))
                self._id_to_meta = state.get("id_to_meta", {})
                self._int_to_uuid = {int(k): v for k, v in state.get("int_to_uuid", {}).items()}
                logger.info("faiss_loaded", n=self._index.ntotal, path=str(path))
            except Exception as e:  # noqa: BLE001
                logger.warning("faiss_load_failed_reinit", error=str(e))

    @staticmethod
    def _to_int64(uuid_str: str) -> int:
        # Hash uuid → stable signed int64 (FAISS requires int64 IDs)
        import hashlib
        h = hashlib.blake2b(uuid_str.encode("utf-8"), digest_size=8).digest()
        return int.from_bytes(h, "big", signed=True)

    def add(self, ids: Sequence[str], vectors: np.ndarray, metadatas: Sequence[dict]) -> None:
        if len(ids) == 0:
            return
        if vectors.shape[1] != self.dim:
            raise ValueError(f"Vector dim {vectors.shape[1]} != index dim {self.dim}")

        int_ids = np.asarray([self._to_int64(i) for i in ids], dtype=np.int64)
        with self._lock:
            self._index.add_with_ids(vectors.astype(np.float32), int_ids)
            for uid, int_id, meta in zip(ids, int_ids.tolist(), metadatas):
                self._id_to_meta[uid] = meta
                self._int_to_uuid[int_id] = uid

    def search(
        self,
        query_vector: np.ndarray,
        top_k: int,
        filter_metadata: dict | None = None,
    ) -> list[VectorRecord]:
        if self._index.ntotal == 0:
            return []
        q = query_vector.reshape(1, -1).astype(np.float32)
        # Over-fetch when filtering metadata so post-filter still yields top_k.
        fetch = top_k * 4 if filter_metadata else top_k
        fetch = min(fetch, self._index.ntotal)
        scores, ids = self._index.search(q, fetch)

        out: list[VectorRecord] = []
        for score, int_id in zip(scores[0].tolist(), ids[0].tolist()):
            if int_id == -1:
                continue
            uid = self._int_to_uuid.get(int_id)
            if not uid:
                continue
            meta = self._id_to_meta.get(uid, {})
            if filter_metadata and not _match(meta, filter_metadata):
                continue
            out.append(VectorRecord(id=uid, score=float(score), metadata=meta))
            if len(out) >= top_k:
                break
        return out

    def delete(self, ids: Sequence[str]) -> None:
        if not ids:
            return
        import faiss  # noqa: PLC0415

        int_ids = np.asarray([self._to_int64(i) for i in ids], dtype=np.int64)
        with self._lock:
            self._index.remove_ids(faiss.IDSelectorArray(int_ids))
            for uid, int_id in zip(ids, int_ids.tolist()):
                self._id_to_meta.pop(uid, None)
                self._int_to_uuid.pop(int_id, None)

    def persist(self) -> None:
        import faiss  # noqa: PLC0415

        with self._lock:
            faiss.write_index(self._index, str(self.index_file))
            self.meta_file.write_text(
                json.dumps(
                    {
                        "id_to_meta": self._id_to_meta,
                        "int_to_uuid": {str(k): v for k, v in self._int_to_uuid.items()},
                    }
                ),
                encoding="utf-8",
            )

    def count(self) -> int:
        return int(self._index.ntotal)


def _match(meta: dict, filter_meta: dict) -> bool:
    for k, v in filter_meta.items():
        if isinstance(v, list):
            if meta.get(k) not in v:
                return False
        elif meta.get(k) != v:
            return False
    return True


# --------------------------------------------------------------------------
# Chroma implementation (optional)
# --------------------------------------------------------------------------
class ChromaVectorStore(VectorStore):
    def __init__(self, path: Path, dim: int) -> None:
        import chromadb  # noqa: PLC0415

        self.path = path
        self.dim = dim
        path.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=str(path))
        self._coll = self._client.get_or_create_collection(
            name="video_chunks",
            metadata={"hnsw:space": "cosine"},
        )

    def add(self, ids, vectors, metadatas) -> None:
        if len(ids) == 0:
            return
        self._coll.add(ids=list(ids), embeddings=vectors.tolist(), metadatas=list(metadatas))

    def search(self, query_vector, top_k, filter_metadata=None) -> list[VectorRecord]:
        where = filter_metadata or None
        res = self._coll.query(
            query_embeddings=[query_vector.tolist()],
            n_results=top_k,
            where=where,
        )
        out: list[VectorRecord] = []
        for uid, score, meta in zip(res["ids"][0], res["distances"][0], res["metadatas"][0]):
            out.append(VectorRecord(id=uid, score=1.0 - float(score), metadata=meta or {}))
        return out

    def delete(self, ids) -> None:
        if ids:
            self._coll.delete(ids=list(ids))

    def persist(self) -> None:
        # Chroma's PersistentClient writes-through automatically.
        return None

    def count(self) -> int:
        return self._coll.count()


@lru_cache(maxsize=1)
def get_vector_store() -> VectorStore:
    if settings.VECTOR_STORE_BACKEND == "chroma":
        return ChromaVectorStore(settings.VECTOR_STORE_DIR, settings.EMBEDDING_DIM)
    return FAISSVectorStore(settings.VECTOR_STORE_DIR, settings.EMBEDDING_DIM)
