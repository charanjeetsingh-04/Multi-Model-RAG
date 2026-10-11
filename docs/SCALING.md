# Scaling strategy

This is the playbook for scaling each component independently. Every
service is stateless except Postgres, Redis, and the storage layer — those
are the only places to worry about state.

## Tier 1 — single-box (1–100 users)

Docker Compose as shipped. CPU only. Whisper `base` model. FAISS on disk.

* Backend: 2 Uvicorn workers, `--workers 2`.
* Celery: 1 worker, concurrency=2.
* Postgres + Redis as local containers.

Verify health: `curl :8000/api/v1/health/ready`.

## Tier 2 — small cluster (100–10k users)

Kubernetes; manifests in [k8s/](../k8s/).

| Component | Scale lever                                    | Min/Max |
|-----------|-----------------------------------------------|---------|
| backend   | HPA on CPU 70% + memory 80%                    | 3 / 20  |
| worker    | HPA on CPU/memory (swap to **KEDA** on Redis queue length) | 2 / 30  |
| frontend  | HPA on CPU 70%                                 | 2 / 10  |
| postgres  | RDS / Cloud SQL, single primary, read replica  | n/a     |
| redis     | Managed (ElastiCache / Memorystore) cluster    | n/a     |

### Worker scaling specifics

Whisper inference is CPU/RAM heavy. Three knobs:
1. `--concurrency` per pod (start at 2; raise only after watching memory).
2. `--max-tasks-per-child` (we set 50) — prevents memory creep when many
   different video lengths run on one process.
3. Replicas (HPA / KEDA).

For GPU acceleration: switch `WHISPER_DEVICE=cuda`, build a CUDA-base
image, taint a GPU node pool, set node selectors on the worker Deployment.

### Stickiness

We have **no sticky sessions**. Every request can land on any backend pod
because:
* JWT is the auth source of truth.
* Conversation state lives in PG.
* Vector store is on a RWX volume (or remote).
* Cache is shared Redis.

The only stickiness we'd ever add is for SSE — and current load balancers
handle SSE without it because the stream is a single long-lived connection
to one pod.

## Tier 3 — large (10k–1M users)

The shape changes:

| Bottleneck         | Mitigation                                                              |
|--------------------|-------------------------------------------------------------------------|
| FAISS single-box   | Migrate vectors to **pgvector** (cheap, transactional) or **Pinecone / Weaviate / Qdrant Cloud** (better at >5M vectors). The `VectorStore` ABC makes this a one-class swap. |
| Postgres writes    | Sharding by `user_id`; use Citus or split into read/write fleets       |
| Embedding compute  | Switch to **managed embeddings API** (Gemini / Voyage / Cohere) for spikes; keep MiniLM as fallback |
| Whisper queue      | GPU node pool with KEDA scaler on Redis stream length                  |
| Storage            | S3 with multi-region replication; `STORAGE_BACKEND=s3` already supported |
| Rate limits        | Slowapi → **Redis-based limiter** (per-org quotas) or push to gateway   |
| LLM cost           | See [COST.md](./COST.md)                                               |

## Multi-region

* **Read-local, write-global** for Postgres (Aurora Global or Cloud SQL replicas).
* Pin user → region via JWT claim; preserve in cookie.
* Vectors per region (FAISS on RWX) — eventual consistency is fine because
  vectors are append-only per video.
* Redis per region (sessions, caches don't cross regions).

## Failure modes & isolation

* Gemini outage → `LLMTimeoutError` / `LLMBlockedError` surface to client;
  retries with backoff cap at 3. Frontend shows toast, conversation
  preserves the user turn.
* Redis outage → `NullCache` fallback in `get_cache()`. Latency rises, but
  no requests fail.
* FAISS file corruption → `FAISSVectorStore` rebuilds index in memory on
  load failure. Pipeline can be re-run via `POST /videos/{id}/reprocess`.
* Postgres outage → readiness probe fails; HPA stops scaling up; gateway
  returns 503 with `dependency_unavailable` code.

## When to introduce KEDA

Stop using CPU/memory HPA on workers once your queue depth becomes the
real signal. Drop in the KEDA `redis` ScaledObject pointing at
`queue:ingest` length. Target: queue length per replica ≤ 5.
