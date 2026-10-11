# Architecture

## Layers

```
                                  ┌────────────┐
                                  │   Client   │
                                  └─────┬──────┘
                        REST / SSE      │
                                  ┌─────▼──────┐
                                  │  FastAPI   │   middleware → routes → services
                                  └─────┬──────┘
                  ┌───────────────────┼─────────────────────┐
       Services   │                   │                     │
                  ▼                   ▼                     ▼
            UserService          VideoService           ChatService
                                     │                      │
                                     ▼                      ▼
                          ┌──────────────────┐     ┌──────────────────┐
                          │  ingestion stages │     │  Memory + RAG    │
                          │  (audio, STT,     │     │  (Retriever,     │
                          │   chunk, embed,   │     │   ContextBuilder │
                          │   index)          │     │   Gemini)        │
                          └──────────────────┘     └──────────────────┘
                                     │                      │
                                     ▼                      ▼
                             ┌──────────────┐        ┌─────────────┐
                             │ Vector Store │        │   PG / Redis│
                             └──────────────┘        └─────────────┘
```

## Why Clean Architecture here

Every layer talks only to the layer below — and only via abstractions:

* `Embedder` ABC: today MiniLM, tomorrow a managed embeddings API.
* `VectorStore` ABC: FAISS for single-box, Chroma for multi-tenant local, easy to add Pinecone.
* `StorageBackend` ABC: local FS now, S3 toggleable via env.
* `LLMClient` (Gemini): swap to Claude/OpenAI without touching `ChatService`.

Result: you can rewire any piece without rewriting routes or business logic.

## Request lifecycle (chat)

1. `RequestContextMiddleware` mints a `request_id`, binds it to `structlog.contextvars`.
2. Rate-limit middleware checks token bucket (`user.id` or IP).
3. `get_current_user` decodes JWT, hydrates `User`.
4. `ChatService.respond_stream()`:
   * `MemoryService` pulls short-term turns (Postgres → Redis cache).
   * `HybridRetriever` runs dense (FAISS) + sparse (BM25), fuses with RRF, optionally reranks.
   * `ContextBuilder` assembles passages + memory + question within a token budget.
   * `PromptBuilder` produces the Gemini-shaped contents list.
   * `GeminiClient.stream()` yields deltas via `asyncio.to_thread`.
   * Each delta is forwarded to the client as an SSE event.
5. After the stream completes, the assistant message + citations + latency are persisted, the long-term summary is recomputed if a threshold was crossed, and the short-term cache is invalidated.

## Video ingestion pipeline

`VideoService.process_video()` walks every stage and persists the `status`
after each. Failures save the error message, surface it in the UI, and allow
a retry via `POST /videos/{id}/reprocess`.

```
UPLOADED → EXTRACTING_AUDIO → TRANSCRIBING → CHUNKING
       → EMBEDDING → INDEXING → READY
```

## Data model

* `User` 1-1 `UserPreference` (long-term memory facts + style preferences).
* `User` 1-n `Video` 1-n `VideoChunk`.
* `User` 1-n `Conversation` 1-n `Message`.
* `Conversation` 0..1 `Video` (chat may be scoped to one video or all videos).

## Observability

* `/metrics`: Prometheus (auto-instrumented by `prometheus-fastapi-instrumentator`).
* `app.monitoring.metrics` adds LLM/retrieval custom counters and histograms.
* `app.monitoring.mlflow_tracker` for offline eval runs.
* Structured JSON logs with `request_id` in every line.

## Security

* JWTs are signed with `SECRET_KEY` (rotate via env + redeploy).
* All write routes require `get_current_user`.
* Per-user ownership enforced in services (e.g. `Video.owner_id == user.id`).
* Vector store filters on `user_id` metadata so the retriever cannot return another user's chunks.
