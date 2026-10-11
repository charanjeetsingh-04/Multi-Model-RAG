import numpy as np
import pytest

from app.rag.vector_store import FAISSVectorStore


@pytest.fixture
def store(tmp_path):
    return FAISSVectorStore(tmp_path, dim=8)


def test_add_and_search(store):
    rng = np.random.default_rng(0)
    vecs = rng.normal(size=(3, 8)).astype(np.float32)
    vecs /= np.linalg.norm(vecs, axis=1, keepdims=True)
    ids = [f"id-{i}" for i in range(3)]
    metas = [{"video_id": "v", "user_id": "u"} for _ in range(3)]
    store.add(ids, vecs, metas)

    q = vecs[1]
    hits = store.search(q, top_k=2)
    assert hits
    assert hits[0].id == "id-1"


def test_metadata_filter(store):
    rng = np.random.default_rng(1)
    vecs = rng.normal(size=(4, 8)).astype(np.float32)
    vecs /= np.linalg.norm(vecs, axis=1, keepdims=True)
    ids = [f"id-{i}" for i in range(4)]
    metas = [{"video_id": str(i % 2), "user_id": "u"} for i in range(4)]
    store.add(ids, vecs, metas)

    hits = store.search(vecs[0], top_k=4, filter_metadata={"video_id": "0"})
    assert all(h.metadata["video_id"] == "0" for h in hits)


def test_delete(store):
    rng = np.random.default_rng(2)
    vecs = rng.normal(size=(2, 8)).astype(np.float32)
    vecs /= np.linalg.norm(vecs, axis=1, keepdims=True)
    store.add(["a", "b"], vecs, [{}, {}])
    assert store.count() == 2
    store.delete(["a"])
    assert store.count() == 1
