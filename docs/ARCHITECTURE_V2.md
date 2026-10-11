# Architecture v2 — Enterprise Refactor

This doc describes the architecture after the v2 refactor. It's the
authoritative diagram going forward; the original [architecture.md](./architecture.md)
remains for historical context.

## What changed (and why)

| Before (v1)                          | After (v2)                                                | Why |
|--------------------------------------|-----------------------------------------------------------|------|
| Services held `AsyncSession` + raw `select()` | Services hold typed **Repositories** | Testable without Postgres; queries optimized in one place |
| Routes instantiated services inline  | **DI providers** (`Provide*` functions) wire everything | Compose graph is explicit; easy to mock |
| Errors were ad-hoc classes           | **Error registry** + RFC 7807 `problem+json` envelope    | Frontends can branch on `code`; OpenAPI gets uniform errors |
| Cache was a single Redis wrapper     | **Cache module** with `@cached`/`@invalidates` + key registry | Multi-level caching across services with one API |
| BackgroundTasks for ingest           | **Celery** (Redis broker) with retries + Beat            | Retries with back-off, dead-letter, scheduled jobs |
| No tracing                           | **OpenTelemetry** auto-instrumented (FastAPI/SQLA/Redis/httpx) | Distributed traces propagate through gateways |
| Memory tied to request session       | Memory service uses **repos + Redis cache**              | Lower per-turn latency; replayable across instances |
| Retrieval was serial                 | `asyncio.gather` runs **dense + sparse + memory + profile in parallel** | ~150–300ms saved per chat turn |
| Embeddings recomputed every call     | **Content-hash embedding cache** (Redis, 24h)            | Repeat queries become near-free |
| No K8s                               | **Kustomize base + staging/production overlays** with HPA, PDB, NetworkPolicy, Ingress | Production-ready deploys |

## Layered view

```
┌────────────────────────────────────────────────────────────────┐
│                       API Gateway (NGINX / Kong / Envoy)        │
│  TLS · WAF · X-Request-ID · X-Forwarded-User · rate-limit       │
└──────────────────────────────┬─────────────────────────────────┘
                               │
                ┌──────────────▼──────────────┐
                │   FastAPI (stateless, HPA)   │
                │   ▸ Middleware              │
                │   ▸ Routes (thin)           │
                │   ▸ DI providers            │
                └─────┬───────────────┬────────┘
                      │               │
        ┌─────────────▼──┐      ┌─────▼───────────┐
        │   Services     │      │     Cache       │
        │  (chat,video,  │      │  (Redis NS=app, │
        │   user,memory) │      │   @cached/inv.) │
        └─────┬─────────┬┘      └─────────────────┘
              │         │
        ┌─────▼────┐  ┌─▼──────────────┐
        │ Repos    │  │ External       │
        │ (SQLA)   │  │  • Gemini      │
        └─────┬────┘  │  • Whisper     │
              │       │  • FFmpeg      │
        ┌─────▼─────┐ │  • VectorStore │
        │ Postgres  │ └────────────────┘
        └───────────┘

        ┌────────────────────────────────────────────┐
        │  Celery workers (HPA, KEDA-ready)           │
        │  • ingest queue (Whisper + embed)           │
        │  • maintenance queue (summaries, cleanup)   │
        │  Beat → periodic jobs                        │
        └────────────────────────────────────────────┘
```

## Key principles

1. **Stateless services.** Backend pods carry zero session state. Anything
   stateful (cache, queue, DB, blobs, vectors) lives behind a network
   boundary.
2. **One write path per aggregate.** Repos own SQL; services own
   business rules; routes own HTTP shape. Crossing a layer is a smell.
3. **Default to async.** Anything blocking goes into `asyncio.to_thread`
   so the loop never stalls. Concurrency comes from `gather`, not threads.
4. **Cache everything safe-to-stale.** The user profile, the long-term
   summary, embeddings for stable text — all cached. Conversation state is
   NOT cached: it's already in PG and has to be the source of truth.
5. **Boundaries are typed.** Repos return ORM rows; services return domain
   dataclasses; routes return Pydantic schemas. Mappers are explicit.
6. **Observability is a feature.** Every error has a code; every span has a
   service.name; every log line has a request_id and trace_id.

## Request lifecycle: chat (streaming)

```
client
  POST /api/v1/chat/stream   ──► gateway sets X-Request-ID
                                    │
       FastAPI                        │
       RequestContextMiddleware  ─── binds request_id + trace_id
       JWT validation            ─── get_current_user
       SSE handler                   │
       ChatService.respond_stream    │
            ├─ asyncio.gather:
            │    ├─ MemoryService.get_short_term   ─── PG (repo)
            │    ├─ MemoryService.get_long_term    ─── PG (repo)
            │    ├─ MemoryService.get_user_profile ─── @cached (Redis)
            │    └─ HybridRetriever.retrieve
            │         ├─ embed_query_cached    ─── Redis (24h)
            │         ├─ vector_store.search   ─── FAISS / Chroma
            │         ├─ chunks.list_ready_for_owner  ─── PG (repo)
            │         ├─ bm25_search           (parallel via to_thread)
            │         ├─ rrf fuse
            │         └─ cross-encoder rerank   (parallel via to_thread)
            ├─ ContextBuilder.build  (token budget 2500)
            ├─ PromptBuilder.build_chat
            ├─ GeminiClient.stream
            │    └─ idempotency cache check (60s)
            └─ persist Message + citations + latency

stream of `event: delta / data: {...}` over SSE → client
```

End-to-end p50 latency target: **< 800 ms** to first token, **< 2 s** to last
token for typical 4-passage RAG. See [PERFORMANCE.md](./PERFORMANCE.md).
