# Cost optimization strategy

We split costs into four buckets: **LLM**, **STT (Whisper)**, **compute**,
**storage/data**. Each has its own knobs.

## 1) LLM (Gemini 2.5 Flash)

Largest variable cost at scale. v2 already includes:

* **Token-tight prompts.** System prompt shrunk; passage block uses
  `[#N@mm:ss] text` (no JSON or labels).
* **Context budget cap.** `ContextBuilder(max_tokens=2500)` — strict ceiling
  per call regardless of `top_k`.
* **History cap.** `history_limit=6` turns. Older context lives in the
  long-term summary, not in the prompt.
* **Idempotency cache.** 60s cache on identical prompts (catches retries).
* **LRU on responses for FAQ-style queries.** Configurable per route.

Extra knobs:

| Knob                                       | Saving             | Tradeoff |
|--------------------------------------------|--------------------|----------|
| Lower `GEMINI_MAX_OUTPUT_TOKENS` (2048→1024) | ~50% on outputs   | Truncation on long answers |
| Lower `RETRIEVAL_TOP_K` from 8 → 4         | ~25% on inputs    | Slight recall hit |
| Use **prompt prefix caching** server-side (Gemini supports this on long stable system prompts) | 30–60% on inputs | Implementation effort |
| Route summarization to a cheaper model (e.g. Gemini Flash Lite) | High              | Engineering |
| Daily quota per user via Redis counter     | Caps tail abuse   | UX consideration |

## 2) Speech-to-text (Whisper)

Big variable cost when run on cloud CPU/GPU.

* Use `int8` quantization (default) — 4× faster on CPU, near-identical WER.
* Match model size to language quality requirements; English-only =
  `WHISPER_MODEL_SIZE=base.en`.
* Long videos: run **VAD** (already enabled) so silences are skipped.
* Pre-emptively reject duplicate uploads by content hash (saved to
  `extra_metadata`).
* GPU economics break even around ~5,000 minutes/day; below that, CPU
  spot instances win.

## 3) Compute (K8s nodes)

* **Spot/preemptible** node pool for `celery-worker` (idempotent tasks).
* Right-size requests: backend pods are usually CPU-bound on retrieval and
  IO-bound on LLM call → start at `cpu: 500m`, `memory: 1Gi`, scale via HPA.
* Workers: `cpu: 1`, `memory: 2Gi` per replica; `--max-tasks-per-child=50`
  to keep memory flat.
* Frontend: Next.js standalone is tiny. `100m/256Mi` is plenty.

## 4) Storage & data egress

* `STORAGE_BACKEND=s3` (or GCS/Azure) once you cross a few TB. Lifecycle
  rules move uploads older than 90 days to Glacier/Coldline.
* **Vectors:** FAISS on RWX volume is free but doesn't scale past ~10M
  vectors comfortably. Move to `pgvector` (same DB you already pay for) or
  managed Pinecone/Qdrant.
* **Postgres backups:** point-in-time recovery + daily snapshots. Don't
  store transcripts twice — `Video.transcript` and chunks are
  reconstructable from the source video; keep only chunks indexed.
* **Redis:** keep `maxmemory-policy=allkeys-lru` so cost grows with hits,
  not size.

## Quotas + visibility

* Daily LLM tokens per user → Redis counter (`llm:tokens:{user}:{date}`).
* Surface to user in `/users/recommendations` so they self-throttle.
* Per-org soft caps via admin panel.
* Prometheus alert: `sum(rate(llm_tokens_total[5m])) by (kind) > X`.

## Order-of-magnitude pricing (illustrative)

For 1,000 daily active users with ~10 chat turns each:

| Bucket   | Monthly est.       | Notes |
|----------|--------------------|-------|
| Gemini   | $200–600           | Flash, tight prompts, ~1k tokens/turn |
| Whisper  | ~$50 CPU spot      | New video uploads ~100/day, base model |
| K8s      | $300–500           | 3-pod backend, 2-pod workers, small Postgres + Redis |
| Storage  | $20–80             | S3 + small vector store |
| **Total**| **~$600–1.2k/mo**  | Headroom for ~5× on the same shape |

(Treat as a planning hint. Actuals depend on provider pricing + regional egress.)
