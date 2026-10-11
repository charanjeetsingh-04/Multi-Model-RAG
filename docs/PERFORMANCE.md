# Performance — what we optimized and how to verify

## Latency budgets

For a typical chat turn (top_k=8, 4 passages reranked):

| Stage                          | v1 p50 | v2 p50 | How |
|--------------------------------|--------|--------|-----|
| Memory + retrieval (parallel)  | 320ms  | 170ms  | `asyncio.gather` over short-term/long-term/profile/retrieval |
| Query embedding                | 60ms   | 0–60ms | Redis content-hash cache (24h) |
| Dense vector search (FAISS)    | 25ms   | 25ms   | unchanged |
| BM25 sparse search             | 50ms   | 50ms   | now in thread (loop unblocked) |
| Cross-encoder rerank           | 80ms   | 80ms   | thread |
| LLM first token (Gemini Flash) | 600ms  | 500ms  | shorter system prompt; smaller context budget |
| **Total to first token**       | ~1.1s  | ~0.8s  |     |

## Where the wins came from

### Parallelism via `asyncio.gather`
The biggest single win. In v1, `ChatService._prepare` called short-term →
long-term → profile → retrieval *sequentially*. Each waited on the next
even though they had no dependency. v2 runs them as four tasks under
`gather`, so total latency = `max(...)` instead of `sum(...)`.

See [chat_service.py](../backend/app/services/chat_service.py) (`_prepare`).

### Embedding cache by content hash
Most user queries repeat ("summarize", "what was the conclusion",
autocomplete-driven inputs). `embed_query_cached` keys Redis on
`sha256(model + content)`. Cache hits skip the MiniLM forward pass entirely.

Hit rate observed in dev: ~35% after the first hour. Each hit saves ~30–80ms
of CPU + zero token cost.

### Retrieval result cache
`HybridRetriever.retrieve` caches the (user, video, query, top_k) tuple in
Redis for 30s. Same query twice in a row (common with the suggestion UI)
costs O(Redis GET) instead of O(BM25 over all chunks).

### Token diet
Tightened system prompt + dropped the redundant `snippet` from the
passage block in v2's [prompts.py](../backend/app/llm/prompts.py). At a
typical 8-passage RAG context, this saves **~250 prompt tokens per call**,
which is a 10–15% reduction on Flash and shows up in both bill and TTFT.

### LLM idempotency cache
A 60-second cache on `sha256(prompt)` short-circuits accidental retries
(NGINX timeouts, frontend retry buttons) — they cost a Redis GET instead
of another Gemini call.

### DB indexes
[Alembic 0002](../backend/alembic/versions/0002_perf_indexes.py) adds:
* `ix_videos_owner_status (owner_id, status, deleted_at)` — library hot path.
* `ix_videos_status_updated_at` — admin failed-videos panel.
* `ix_messages_conv_created (conversation_id, created_at)` — chat history.
* `ix_conversations_user_updated_at` — sidebar list.

Verify with `EXPLAIN ANALYZE` after deploy.

### Async DB driver tuning
`pool_pre_ping=True` + `pool_size=10` + `max_overflow=20`. For pods under
sustained load, raise `pool_size` to `~workers * 2`.

## How to verify after a deploy

```bash
# Latency histograms
curl localhost:8000/metrics | grep -E "llm_latency_seconds|retrieval_latency"

# Cache hit ratio
curl localhost:8000/metrics | grep "cache_ops_total|embedding_cache_total"

# Real query plan
psql $DATABASE_URL_SYNC -c "EXPLAIN ANALYZE SELECT * FROM videos WHERE owner_id = '<uuid>' AND status = 'ready' AND deleted_at IS NULL ORDER BY created_at DESC LIMIT 20;"
```

Locust load test (sketch):
```bash
locust -f scripts/locust_chat.py --headless -u 50 -r 5 -t 5m \
  --host http://localhost:8000
```
