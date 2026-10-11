"""Offline retrieval evaluation harness.

Given a JSONL file of {query, gold_chunk_ids[]}, computes recall@k and
nDCG@k, logs everything to MLflow. Run with:

    python -m scripts.eval_retrieval --dataset eval/queries.jsonl --user_id <UUID>
"""
from __future__ import annotations

import argparse
import asyncio
import json
import math
import uuid
from pathlib import Path

from app.db.session import AsyncSessionLocal
from app.monitoring.mlflow_tracker import log_metrics, log_params, run
from app.rag.retriever import HybridRetriever


def _ndcg_at_k(retrieved_ids: list[str], gold: set[str], k: int) -> float:
    dcg = 0.0
    for i, rid in enumerate(retrieved_ids[:k]):
        if rid in gold:
            dcg += 1.0 / math.log2(i + 2)
    ideal = sum(1.0 / math.log2(i + 2) for i in range(min(len(gold), k)))
    return dcg / ideal if ideal > 0 else 0.0


def _recall_at_k(retrieved_ids: list[str], gold: set[str], k: int) -> float:
    if not gold:
        return 0.0
    return len(set(retrieved_ids[:k]) & gold) / len(gold)


async def main(dataset: Path, user_id: uuid.UUID, k: int) -> None:
    with run("retrieval_eval", tags={"k": str(k)}):
        log_params({"top_k": k, "dataset": str(dataset)})
        async with AsyncSessionLocal() as db:
            retriever = HybridRetriever(db)
            recalls = []
            ndcgs = []
            with dataset.open() as fh:
                for line in fh:
                    row = json.loads(line)
                    hits = await retriever.retrieve(row["query"], user_id=user_id, top_k=k)
                    retrieved = [str(h.chunk_id) for h in hits]
                    gold = set(row["gold_chunk_ids"])
                    recalls.append(_recall_at_k(retrieved, gold, k))
                    ndcgs.append(_ndcg_at_k(retrieved, gold, k))
            log_metrics(
                {
                    "recall@k": sum(recalls) / max(1, len(recalls)),
                    "ndcg@k": sum(ndcgs) / max(1, len(ndcgs)),
                    "n_queries": len(recalls),
                }
            )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--user_id", type=uuid.UUID, required=True)
    parser.add_argument("--k", type=int, default=10)
    args = parser.parse_args()
    asyncio.run(main(args.dataset, args.user_id, args.k))
