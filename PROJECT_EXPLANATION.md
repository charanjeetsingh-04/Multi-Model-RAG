# Multi-Modal Video RAG Assistant — Deep Project Explanation

This document explains **what every part of the codebase does and why**. If
the [README](./README.md) is the elevator pitch and [HOW_TO_RUN](./HOW_TO_RUN.md)
is the operator manual, this is the architect's tour.

---

## 1. What the system does (in one paragraph)

A user uploads a video. The backend extracts its audio with FFmpeg,
transcribes it with Whisper, splits the transcript into time-stamped
semantic chunks, embeds each chunk with a sentence-transformer, and stores
the vectors in FAISS (or Chroma). When the user chats, we retrieve the
relevant chunks with a hybrid (dense + BM25 + RRF + cross-encoder) pipeline,
inject them into a prompt for **Gemini 2.5 Flash**, and stream the answer
back via Server-Sent Events with timestamped citations. Across turns, we
maintain three layers of memory (short-term recent turns, long-term LLM
summary, durable user preferences) so the model behaves like it knows the user.

---

## 2. Big-picture architecture

```
                Browser (Next.js 14 + TS + Tailwind)
                          │  REST + SSE
                          ▼
       ┌────────────────────────────────────────────┐
       │  API Gateway / Ingress (NGINX / Kong)        │
       │  TLS · WAF · X-Request-ID · rate-limit       │
       └────────────────────────────────────────────┘
                          │
                          ▼
   ┌──────────────────────────────────────────────────────┐
   │  FastAPI Backend (Python 3.11, async, stateless)      │
   │                                                       │
   │   middleware ─── routes ─── DI providers              │
   │                    │              │                    │
   │              services ◄────── repositories ──► PG     │
   │                    │                                   │
   │   ┌────────────────┴───────────────────────────────┐   │
   │   │   RAG stack                                     │   │
   │   │   audio ▸ STT ▸ chunk ▸ embed ▸ vector store   │   │
   │   │   retrieve(hybrid) ▸ rerank ▸ context build    │   │
   │   │   Gemini stream ──► SSE back to client          │   │
   │   └─────────────────────────────────────────────────┘   │
   │                                                          │
   │   cache (Redis) · OTel · Prometheus /metrics            │
   └──────────────────────────────────────────────────────┘
                  │
                  ▼  Celery (Redis broker)
   ┌────────────────────────────────────────┐
   │  Worker pods                            │
   │  • ingest queue (Whisper, FFmpeg)       │
   │  • maintenance queue (summaries, GC)    │
   │  Beat scheduler for periodic jobs       │
   └────────────────────────────────────────┘

   External: PostgreSQL · Redis · MLflow · (optional) S3
```

---

## 3. Folder layout (annotated)

```
project-root/
├── backend/                        # FastAPI + AI pipeline
│   ├── app/
│   │   ├── main.py                 # app factory, lifespan, middleware
│   │   ├── api/v1/                 # HTTP routes (thin)
│   │   ├── core/                   # config, logging, errors, observability
│   │   ├── auth/                   # JWT + bcrypt + FastAPI deps
│   │   ├── db/                     # SQLAlchemy session + Base
│   │   ├── models/                 # ORM (User, Video, Chunk, Conv, Msg)
│   │   ├── schemas/                # Pydantic DTOs (request/response)
│   │   ├── repositories/           # Data access (NEW v2)
│   │   ├── dependencies/           # DI providers (NEW v2)
│   │   ├── services/               # Orchestration (depend on repos)
│   │   ├── domain/                 # Pure dataclasses (NEW v2)
│   │   ├── cache/                  # Redis + @cached/@invalidates (NEW v2)
│   │   ├── rag/                    # audio, STT, chunk, vector store, retriever
│   │   ├── embeddings/             # Embedder ABC + MiniLM
│   │   ├── llm/                    # Gemini client + prompt templates
│   │   ├── memory/                 # legacy shim → services/memory_service
│   │   ├── storage/                # local + S3 behind one ABC
│   │   ├── middleware/             # request-id, rate limit
│   │   ├── monitoring/             # Prometheus + MLflow helpers
│   │   ├── workers/                # Celery app + tasks
│   │   └── utils/                  # text + file helpers
│   ├── alembic/                    # migrations (0001 schema, 0002 indexes)
│   ├── tests/                      # unit (fakes) + integration (marked)
│   ├── requirements.txt
│   ├── alembic.ini
│   ├── pytest.ini
│   └── pyproject.toml
├── frontend/                       # Next.js 14 App Router
│   ├── app/                        # pages (landing, login, dashboard, chat, …)
│   ├── components/                 # ui primitives + chat + layout
│   ├── hooks/useChatStream.ts      # SSE streaming
│   ├── lib/api.ts                  # fetch wrapper with token refresh
│   └── lib/store.ts                # zustand auth + theme stores
├── docker/                         # Dockerfiles per service
├── docker-compose.yml              # local stack: PG, Redis, MLflow, BE, worker, beat, flower, FE
├── k8s/                            # Kustomize base + staging/prod overlays
├── docs/                           # ARCHITECTURE_V2, PERFORMANCE, SCALING, COST, …
├── scripts/                        # create_admin, eval_retrieval, setup.{ps1,sh}
└── README.md / HOW_TO_RUN.md / PROJECT_EXPLANATION.md
```

---

## 4. Walkthrough by directory

### `backend/app/core/` — cross-cutting concerns

* **`config.py`** — single source of truth. `Settings` extends Pydantic's
  `BaseSettings`, so every env var gets validated *at startup*. The process
  refuses to boot if a required value is missing or malformed. Settings is
  a singleton via `get_settings()`.
* **`logging.py`** — bootstraps `structlog`. In prod we emit one-line JSON
  (great for Loki/Datadog). In dev we render colored text. Every record
  carries `request_id` (bound by middleware) and `trace_id` (auto-picked
  from OpenTelemetry if available).
* **`errors.py`** — the `ErrorCode` enum + `ErrorSpec` registry. Adding a
  new error to the API is a one-line edit here.
* **`exceptions.py`** — `AppError` + a family of typed subclasses
  (`NotFoundError`, `ConflictError`, etc.). `register_exception_handlers`
  produces an RFC 7807 `application/problem+json` envelope on every error,
  so clients can branch on `code` rather than scraping `message` strings.
* **`observability.py`** — wires OpenTelemetry. Auto-instruments FastAPI,
  SQLAlchemy, Redis, httpx. Activates only when `OTEL_EXPORTER_OTLP_ENDPOINT`
  is set, so local dev pays zero cost.

### `backend/app/db/` — persistence wiring

* **`base.py`** — `Base = DeclarativeBase` + reusable `UUIDPkMixin` and
  `TimestampMixin` so models stay tiny.
* **`session.py`** — async engine + `async_sessionmaker`. `get_db()` is the
  FastAPI dependency every route uses; it commits on success, rolls back on
  exception. Pool tuned for typical chat traffic (`pool_size=10`,
  `max_overflow=20`, `pool_pre_ping=True`).

### `backend/app/models/` — ORM

* **`user.py`** — `User` + 1-1 `UserPreference` (long-term facts and style).
* **`video.py`** — `Video` + 1-n `VideoChunk`. `VideoStatus` enum drives the
  ingestion state machine (UPLOADED → EXTRACTING_AUDIO → … → READY/FAILED).
  `deleted_at` enables soft delete (audit trail + simple recovery).
* **`chat.py`** — `Conversation` 1-n `Message`. Assistant messages carry
  `citations: JSONB` so we can audit answers and the UI can render sources.

UUID primary keys everywhere — avoids leaking row counts and supports
distributed inserts. JSONB for free-form metadata so we never need a new
migration to add a field.

### `backend/app/schemas/` — API DTOs

Pydantic v2 models. Strictly separated from ORM models so:
* the wire format can change without touching the DB,
* `model_config = ConfigDict(from_attributes=True)` does the ORM→DTO mapping in one line,
* sensitive columns (`hashed_password`) never accidentally leak.

### `backend/app/repositories/` — single point of DB access (v2)

* **`base.py`** — generic `BaseRepository[T]` with safe primitives
  (`get`, `get_many`, `count`, `exists`, `add`, `delete`, `flush`). No
  "find by anything" magic — every concrete query is named and easy to
  optimize.
* **`user_repository.py`** — `get_by_email`, `get_by_username`,
  `list_recent`. Eager-loads `preferences` when needed.
* **`video_repository.py`** — owns the hot library + retrieval queries.
  `list_ready_for_owner` is the only place that builds the chunk-join
  query, so indexes can be tuned in one place.
* **`chat_repository.py`** — `list_recent` (LIMIT + DESC then reverse so PG
  scans an index instead of sorting) is the chat history hot path.

Services never write SQL. This is the biggest single change in v2 — it
makes service unit tests possible without spinning up Postgres.

### `backend/app/dependencies/` — DI providers (v2)

Plain async functions decorated with FastAPI's `Depends`. They wire
sessions → repositories → services. Routes get fully-typed services with
nothing inline:

```python
async def upload_video(svc: VideoService = Depends(ProvideVideoService)): ...
```

Why no big DI library? FastAPI's `Depends` already does what we need; a
heavy DI container would add ceremony without buying anything.

### `backend/app/services/` — orchestration

* **`user_service.py`** — register, login, refresh, token issuance.
* **`video_service.py`** — the entire ingestion pipeline. Each stage marks
  the row's `status` so the UI can show progress; failures save the error
  and allow `POST /videos/{id}/reprocess`.
* **`memory_service.py`** — short-term (recent N turns from PG), long-term
  (LLM-generated summary refreshed every K messages), and per-user
  preferences. Profile lookups are `@cached` for 120s.
* **`chat_service.py`** — the high-value file. `_prepare` runs *four*
  things concurrently with `asyncio.gather` (short-term + long-term +
  profile + retrieval) — biggest latency win in the refactor. Persists
  user turn → builds prompt → calls Gemini (sync or streaming) → persists
  assistant turn → updates summary if threshold crossed.

### `backend/app/rag/` — the RAG stack

* **`audio.py`** — `AudioExtractor` wraps FFmpeg via `ffmpeg-python`.
  Outputs mono 16 kHz PCM (the only thing modern STT expects). Probe call
  separately retrieves duration.
* **`transcription.py`** — `Transcriber` wraps `faster-whisper` (CTranslate2
  backend, 4× faster than openai-whisper, similar WER). VAD is on to drop
  silences; segments retain start/end times.
* **`chunking.py`** — two strategies behind a common shape:
  - `RecursiveChunker` (LangChain's `RecursiveCharacterTextSplitter` with
    sentence/word fallbacks). We re-attach timestamps by mapping each
    chunk's character span back to the source segments.
  - `SemanticChunker` (embedding-similarity drift detection). Heavier but
    produces topically-coherent chunks.
* **`vector_store.py`** — `VectorStore` ABC + two impls:
  - **FAISS** — `IndexFlatIP` wrapped in `IndexIDMap2` so we can delete by
    UUID. A sidecar `meta.json` stores per-vector metadata (FAISS itself
    has no metadata support). Metadata filtering is post-search; we
    over-fetch and filter to still return `top_k`.
  - **Chroma** — persistent local store with native metadata filters.
* **`retriever.py`** — the hybrid retriever:
  1. embed query (cached in Redis by content hash);
  2. dense search (FAISS) + sparse search (BM25) in *parallel* threads;
  3. Reciprocal Rank Fusion (RRF — robust, no tuning);
  4. optional cross-encoder rerank (`ms-marco-MiniLM-L-6-v2`);
  5. cache the result for 30s (handles UI double-clicks for free).
* **`context_builder.py`** — assembles passages within a 2,500-token budget.
  Each passage is tagged `[#N@mm:ss]` so the model can cite by number and
  we can map citations back to chunks/timestamps in the response.

### `backend/app/embeddings/` — text → vector

* **`embedder.py`** — `Embedder` ABC with `SentenceTransformerEmbedder`
  (MiniLM-L6-v2, 384-dim) as the default. `embed_query_cached` is the
  optimization — Redis content-hash cache (24 h TTL) avoids the MiniLM
  forward pass for repeat queries.

### `backend/app/llm/` — Gemini integration

* **`gemini_client.py`** — wraps the official `google-generativeai` SDK.
  Exposes `complete()` (with tenacity retry + token counts) and `stream()`
  (async iterator of deltas). 60s idempotency cache keyed on prompt
  fingerprint absorbs accidental retries (NGINX timeout, frontend retry).
  Errors are mapped to typed `LLMBlockedError` / `LLMTimeoutError`.
* **`prompts.py`** — all prompts live here (versionable + diff-able). The
  chat system prompt is deliberately terse — every token saved here
  multiplies across every chat call.

### `backend/app/memory/` — legacy shim → `services/memory_service.py`.

Old imports still work; new code uses `app.services.memory_service`.

### `backend/app/cache/` — Redis + decorators (v2)

* **`backend.py`** — `Cache` protocol, `RedisCache` (orjson values, SCAN
  for prefix deletes — never KEYS), `NullCache` fallback when REDIS_ENABLED
  is false. `get_cache()` is a process-wide singleton.
* **`keys.py`** — `CacheKeys` registry; every key shape in the app is
  defined here. Catches typo'd keys at lint time and makes mass
  invalidation trivial (`delete_pattern("user:UUID:*")`).
* **`decorators.py`** — `@cached(key_builder, ttl)` and `@invalidates(...)`.
  Key builders are functions of the wrapped method's args, so cache logic
  stays next to the method it serves.

### `backend/app/auth/` — JWT + bcrypt

* **`security.py`** — bcrypt hash/verify, `create_access_token`,
  `create_refresh_token`, `decode_token(expected_type=...)`. The `type`
  claim prevents a refresh token from being used as an access token.
* **`dependencies.py`** — `get_current_user` (parses bearer, loads user)
  and `require_admin` (composed on top).

### `backend/app/middleware/` — cross-cutting

* **`request_context.py`** — assigns a `request_id`, honors gateway
  headers (`X-Request-ID`, `X-Forwarded-For`), binds the ID to structlog
  contextvars, and logs request completion with duration.
* **`rate_limit.py`** — `slowapi` limiter; keys by user.id when
  authenticated, else IP. Configurable via `RATE_LIMIT_PER_MINUTE`.

### `backend/app/api/v1/` — HTTP routes

Routes are deliberately tiny — they parse input, call a service via DI,
serialize the result. All business logic lives in services.

* **`auth.py`** — register, login, refresh, me.
* **`videos.py`** — upload (streams multipart to disk), list, get,
  reprocess (Celery `.delay`), summary (uses Gemini directly), delete
  (soft + vector cleanup).
* **`chat.py`** — `/chat` (sync JSON response) and `/chat/stream` (SSE).
  The streaming endpoint manages its own DB session because the stream
  outlives the FastAPI request lifecycle.
* **`users.py`** — preferences GET/PATCH, memory inspection,
  recommendations.
* **`admin.py`** — stats counts, users list, failed-videos list. Guarded
  by `require_admin`.
* **`health.py`** — `/live` (process up) + `/ready` (DB + embedder up).
  K8s probes hit `/live` for liveness and `/ready` for readiness.

### `backend/app/workers/` — async pipeline

* **`celery_app.py`** — Celery wiring. Important config:
  - `task_acks_late=True` — only ack after success, so a crashed worker
    re-runs the task.
  - `task_reject_on_worker_lost=True` — same idea for hard kills.
  - `worker_prefetch_multiplier=1` — don't hog heavy tasks.
  - per-queue routing: `ingest` (heavy, capacity-constrained),
    `maintenance` (periodic), `default`.
  - Beat schedule for cleanup + nightly summary jobs.
* **`tasks.py`** — `process_video` (Celery shim that delegates to
  `VideoService.process_video`), `cleanup_failed_videos`,
  `summarize_inactive_conversations`. Retries are `retry_backoff=True`
  exponential up to 3.
* **`video_worker.py`** — legacy launcher that just execs the Celery CLI.

### `backend/app/storage/` — files on disk or in S3

* **`base.py`** — `StorageBackend` ABC.
* **`local.py`** — straightforward async filesystem ops.
* **`s3.py`** — boto3-based; `get_local_path` downloads to a temp file so
  FFmpeg/Whisper can read it.
* **`factory.py`** — picks the backend based on `STORAGE_BACKEND`.

### `backend/app/monitoring/` — Prometheus + MLflow

* **`metrics.py`** — custom counters and histograms layered on top of
  FastAPI's default instrumentor: `llm_requests_total`, `llm_latency_seconds`,
  `llm_tokens_total`, `retrieval_latency_seconds`, `video_processing_total`,
  `app_errors_total`, `cache_ops_total`, `embedding_cache_total`,
  `task_queue_latency_seconds`. All exposed at `/metrics`.
* **`mlflow_tracker.py`** — small helpers for tracking *offline*
  experiment runs (chunk size sweeps, embedding model swaps).

### `backend/alembic/` — schema migrations

* `0001_initial_schema.py` — all tables + the primary indexes that
  match the ORM definitions.
* `0002_perf_indexes.py` — composite indexes targeting the four hottest
  queries (library list, admin failed-videos panel, chat history scan,
  conversation sidebar).

### `backend/tests/` — testing

* **`conftest.py`** — global fixtures; muzzles the real cache with
  `NullCache` so tests don't talk to Redis.
* **`fakes.py`** — in-memory fakes for repositories, so service unit
  tests run with zero infra.
* **`unit/`** — service + cache + error tests.
* **`integration/`** — marked with `@pytest.mark.integration`; needs
  Postgres + Redis. Run with `pytest -m integration`.

---

## 5. Frontend

Next.js 14 App Router + TypeScript + Tailwind + Shadcn-style primitives.

* **`app/layout.tsx`** — root layout, theme provider, top navbar, Sonner toaster.
* **`app/page.tsx`** — landing.
* **`app/login/` / `app/register/`** — auth forms hitting `/auth/*`.
* **`app/dashboard/`** — overview cards + recent videos.
* **`app/upload/`** — react-dropzone + manual `XHR` for progress.
* **`app/library/`** — polled list (5 s) so status flips from "indexing"
  to "ready" without a refresh.
* **`app/chat/`** — split-pane chat. Uses `useChatStream` (custom hook in
  `hooks/`) which POSTs to `/chat/stream` and parses SSE events via
  `fetch` + ReadableStream — needed because native EventSource can't carry
  Authorization headers.
* **`components/chat/message-bubble.tsx`** — markdown + citations + a
  `▍` cursor while streaming.
* **`lib/api.ts`** — fetch wrapper that injects the access token, retries
  once on 401 by refreshing.
* **`lib/store.ts`** — zustand stores for auth + theme.

---

## 6. Request lifecycles, end-to-end

### a) Video upload

```
POST /api/v1/videos/upload (multipart)
  │
  ├─ RequestContextMiddleware ── request_id bound
  ├─ Rate-limit (slowapi)
  ├─ JWT decode (get_current_user)
  ├─ validate_video (MIME + size)
  ├─ build_storage_path + save_upload (streaming write)
  ├─ VideoService.create — row in PG, status=UPLOADED
  └─ celery_process_video.delay(video_id)
              │
              ▼ Celery worker pod
   VideoService.process_video:
     status=EXTRACTING_AUDIO ─► ffmpeg → mono 16k WAV
     status=TRANSCRIBING     ─► faster-whisper (segments + lang + duration)
     status=CHUNKING         ─► RecursiveChunker (timestamp-aware)
     status=EMBEDDING        ─► MiniLM batch embed
     status=INDEXING         ─► FAISS add + meta.json persist
     status=READY            ─► processed_at = now()
```

### b) Chat (streaming)

```
POST /api/v1/chat/stream  →  SSE response
  │
  ├─ RequestContextMiddleware
  ├─ JWT decode
  ├─ Open dedicated DB session for the duration of the stream
  ├─ ChatService.respond_stream
  │     │
  │     ├─ _get_or_create_conversation
  │     ├─ persist user message
  │     │
  │     ├─ asyncio.gather:                   ← parallel I/O
  │     │     ├─ memory.get_short_term     (PG SELECT)
  │     │     ├─ memory.get_long_term      (PG SELECT)
  │     │     ├─ memory.get_user_profile   (Redis cache + PG)
  │     │     └─ retriever.retrieve
  │     │           ├─ embed_query_cached  (Redis 24h)
  │     │           ├─ vector_store.search (FAISS)  ┐ parallel
  │     │           ├─ BM25 over PG chunks          ┘
  │     │           ├─ RRF fuse
  │     │           └─ cross-encoder rerank
  │     │
  │     ├─ ContextBuilder.build  (2500-token budget, timestamped passages)
  │     ├─ PromptBuilder.build_chat
  │     │
  │     ├─ Gemini.stream → yield {"type":"delta","text":"..."} per token
  │     │                  (60s idempotency cache on prompt fingerprint)
  │     │
  │     ├─ persist assistant message + citations + latency
  │     └─ maybe_update_summary (if message_count crossed threshold)
  │
  └─ EventSourceResponse to client
```

---

## 7. Data model (quick reference)

```
users (id, email, username, hashed_password, is_admin, …)
   │                    └── 1-1 user_preferences
   │                         (theme, language, response_style,
   │                          memory_facts JSONB, notes)
   ├── 1-n videos (id, owner_id, title, status, deleted_at, transcript, …)
   │            └── 1-n video_chunks (chunk_index, text, start_time,
   │                                  end_time, vector_id)
   └── 1-n conversations (title, summary, message_count, video_id?)
                  └── 1-n messages (role, content, citations JSONB,
                                    tokens_in, tokens_out, latency_ms)
```

Vector store mirrors `video_chunks.id` so deletes stay in sync.

---

## 8. Security

* JWT access tokens (60 min) + refresh tokens (14 d); `type` claim prevents
  cross-use.
* Bcrypt password hashing via passlib (cost 12).
* Ownership enforced in every service: `videos.get_owned(id, owner_id)`,
  `convs.get_for_user(id, user_id)`. There is no path that lets a user
  read another user's data.
* Vector store records carry `user_id` metadata; the retriever filters on
  it before returning hits.
* Upload validation: allowed MIME types + 500 MB cap by default.
* CORS allowlist via `CORS_ORIGINS`.
* Rate limiting per user (60/min by default; configurable).
* Containers run as non-root user 1000.
* RFC 7807 error envelope avoids leaking stack traces; full traces go to
  logs only.

---

## 9. Observability

| Signal | Where |
|--------|-------|
| Metrics | `/metrics` (Prometheus) — request rate, LLM tokens/latency, retrieval latency, cache hit ratio, video pipeline outcomes, app error counts. |
| Logs | stdout in JSON (prod) or pretty colors (dev). Every line carries `request_id`, `trace_id`, `service`, `env`, `version`. |
| Traces | OpenTelemetry (FastAPI + SQLA + Redis + httpx). Set `OTEL_EXPORTER_OTLP_ENDPOINT` to ship to Tempo/Honeycomb/Datadog/Jaeger. |
| Health probes | `/api/v1/health/live` (liveness) and `/api/v1/health/ready` (DB + embedder). |
| Experiment tracking | MLflow at `:5000` — used by `scripts/eval_retrieval.py`. |
| Worker UI | Flower at `:5555` — task history, retries, queue depth. |

---

## 10. Costs and cost-control levers

LLM calls dominate at scale. Quick references:

* `RETRIEVAL_TOP_K` — fewer passages → fewer prompt tokens.
* `ContextBuilder(max_tokens=...)` — hard ceiling per call.
* `GEMINI_MAX_OUTPUT_TOKENS` — caps the answer length.
* `SHORT_TERM_MEMORY_TURNS` and the prompt history limit (default 6).
* Idempotency cache (60 s) on identical prompts.
* Embedding cache (24 h) on identical text.

Full playbook in [docs/COST.md](./docs/COST.md).

---

## 11. Scaling

| Tier | Setup |
|------|-------|
| 1 — single box | Docker Compose; CPU Whisper; FAISS on disk |
| 2 — small cluster | K8s; backend HPA(CPU); worker HPA(CPU)→KEDA(queue); RWX volumes |
| 3 — large | pgvector or managed vector DB; GPU node pool for Whisper; multi-region PG; sharded by user |

Details in [docs/SCALING.md](./docs/SCALING.md).

---

## 12. Where to look next

* **First time?** → [HOW_TO_RUN.md](./HOW_TO_RUN.md)
* **Want the v2 architecture diff?** → [docs/ARCHITECTURE_V2.md](./docs/ARCHITECTURE_V2.md)
* **Optimizing latency?** → [docs/PERFORMANCE.md](./docs/PERFORMANCE.md)
* **Scaling?** → [docs/SCALING.md](./docs/SCALING.md)
* **Cost?** → [docs/COST.md](./docs/COST.md)
* **API contract?** → [docs/api.md](./docs/api.md) or `http://localhost:8000/docs`

Welcome aboard — the codebase is deliberately small enough to fit in one
head if you read it in this order: `core/` → `models/` → `repositories/` →
`services/` → `rag/` → `api/v1/routes/`.
