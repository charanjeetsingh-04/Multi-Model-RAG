# Multi-Modal Video RAG AI Assistant

A production-ready, full-stack system for chatting with your videos using
**Retrieval-Augmented Generation** powered by **Gemini 2.5 Flash**.

Upload a video → it's transcribed → chunked → embedded → indexed → and you
can chat with it (with citations that link back to exact timestamps).

---

## ✨ Features

- **End-to-end pipeline**: video → audio (FFmpeg) → transcript (Whisper) → chunks → embeddings → vector store.
- **Hybrid RAG**: dense (FAISS / Chroma) + sparse (BM25) + Reciprocal Rank Fusion + optional cross-encoder reranker.
- **Gemini 2.5 Flash** with streaming token deltas over Server-Sent Events.
- **Memory system**: short-term (recent turns), long-term (rolling LLM-generated summary), and per-user preference memory.
- **Auth**: JWT access + refresh, bcrypt-hashed passwords, admin role.
- **Production guardrails**: structured JSON logs, request-id tracing, rate limiting, Prometheus metrics, MLflow eval harness.
- **Async pipeline**: background processing via FastAPI BackgroundTasks or a Redis-backed worker.
- **Frontend**: Next.js 14 + Tailwind + TypeScript with streaming chat, drag-drop upload, dark mode.
- **Clean architecture**: every layer (vector store, embedder, LLM, storage) is swappable.
- **One-command deploy**: `docker compose up` brings up Postgres, Redis, MLflow, backend, worker, and frontend.

---

## 🏗 Architecture

```
┌─────────────┐         ┌──────────────────────────────────────────────┐
│   Next.js   │ ◀─SSE──▶│              FastAPI Backend                  │
│  (chat UI)  │         │  ┌──────────┬──────────┬───────────────────┐ │
└─────────────┘         │  │   Auth   │  Memory  │  Chat orchestrator│ │
       ▲                │  └──────────┴──────────┴───────────────────┘ │
       │ REST/SSE       │  ┌─────────────┬──────────┬───────────────┐  │
       ▼                │  │   Hybrid    │ Context  │ Gemini Client │  │
┌─────────────┐         │  │  Retriever  │ Builder  │   (streaming) │  │
│   FFmpeg    │         │  └─────────────┴──────────┴───────────────┘  │
│   Whisper   │         │  ┌─────────────────┬──────────────┬────────┐ │
│  Chunking   │         │  │  Embeddings     │ Vector Store │   DB   │ │
└─────────────┘         │  │ (MiniLM-L6-v2)  │ (FAISS/Chroma│  (PG)  │ │
       │                │  └─────────────────┴──────────────┴────────┘ │
       └────────────────▶ Background worker drains Redis queue          │
                        └──────────────────────────────────────────────┘
                                ▲                  ▲           ▲
                                │                  │           │
                          ┌──────────┐      ┌─────────┐  ┌─────────┐
                          │PostgreSQL│      │  Redis  │  │ MLflow  │
                          └──────────┘      └─────────┘  └─────────┘
```

See `docs/architecture.md` for a deeper walkthrough.

---

## 🚀 Quick Start (Docker — recommended)

```bash
cp .env.example .env
# Edit .env and set GEMINI_API_KEY (and SECRET_KEY for prod)

docker compose up --build
```

Services:
- Frontend → http://localhost:3000
- API docs → http://localhost:8000/docs
- MLflow → http://localhost:5000
- Prometheus metrics → http://localhost:8000/metrics

Create an admin:
```bash
docker compose exec backend python -m scripts.create_admin \
    --email you@example.com --username you --password ChangeMe123!
```

---

## 🛠 Local Dev (without Docker)

```bash
# 1. Backend
python -m venv .venv
source .venv/bin/activate            # Windows: .\.venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt

# 2. Start Postgres + Redis (Docker is easiest here)
docker compose up -d postgres redis

# 3. Migrate
cp .env.example .env                 # set GEMINI_API_KEY
cd backend && alembic upgrade head && cd ..

# 4. Run API
uvicorn app.main:app --reload --app-dir backend

# 5. Frontend
cd frontend && npm install && npm run dev
```

---

## 🧱 Folder Structure

```
project-root/
├── backend/
│   ├── app/
│   │   ├── api/v1/             ← FastAPI routes (auth, videos, chat, admin)
│   │   ├── auth/               ← JWT issue/verify + dependencies
│   │   ├── core/               ← settings, logging, exceptions
│   │   ├── db/                 ← SQLAlchemy engine + base
│   │   ├── embeddings/         ← Embedder ABC + MiniLM impl
│   │   ├── llm/                ← Gemini client + prompt templates
│   │   ├── memory/             ← Short-term, long-term, Redis cache
│   │   ├── middleware/         ← request-id, rate limit
│   │   ├── models/             ← ORM models (User, Video, Chunk, Conv, Msg)
│   │   ├── monitoring/         ← Prometheus + MLflow helpers
│   │   ├── rag/                ← audio, transcription, chunking,
│   │   │                          vector store, retriever, context builder
│   │   ├── schemas/            ← Pydantic request/response models
│   │   ├── services/           ← Orchestration (UserSvc, VideoSvc, ChatSvc)
│   │   ├── storage/            ← Local + S3 backends behind ABC
│   │   ├── utils/              ← text + file helpers
│   │   └── workers/            ← Redis-queue worker for video pipeline
│   ├── alembic/                ← migrations
│   └── tests/
├── frontend/
│   ├── app/                    ← Next.js App Router pages
│   ├── components/             ← UI primitives + chat + layout
│   ├── hooks/                  ← useChatStream (SSE)
│   ├── lib/                    ← api client + zustand stores
│   └── types/
├── docker/                     ← Dockerfiles
├── scripts/                    ← setup, create_admin, eval_retrieval
├── docs/                       ← architecture, API reference, deploy
├── uploads/   vector_store/   logs/   notebooks/
├── docker-compose.yml
└── .env.example
```

---

## 🔌 Key API Endpoints

| Method | Path                                | Notes                                          |
|--------|-------------------------------------|------------------------------------------------|
| POST   | `/api/v1/auth/register`             | Create account                                 |
| POST   | `/api/v1/auth/login`                | Returns access + refresh tokens                |
| POST   | `/api/v1/auth/refresh`              | Rotate tokens                                  |
| GET    | `/api/v1/auth/me`                   | Current user                                   |
| POST   | `/api/v1/videos/upload`             | Multipart upload, kicks off pipeline           |
| GET    | `/api/v1/videos`                    | List your videos                               |
| GET    | `/api/v1/videos/{id}`               | Video detail incl. status & errors             |
| POST   | `/api/v1/videos/{id}/reprocess`     | Retry pipeline                                 |
| POST   | `/api/v1/videos/{id}/summary`       | LLM-generated bullet summary                   |
| DELETE | `/api/v1/videos/{id}`               | Soft delete + vector cleanup                   |
| POST   | `/api/v1/chat`                      | Non-streaming chat                             |
| POST   | `/api/v1/chat/stream`               | SSE streaming chat                             |
| GET    | `/api/v1/chat/conversations`        | List conversations                             |
| GET    | `/api/v1/chat/conversations/{id}`   | Conversation + full message history            |
| GET    | `/api/v1/users/preferences`         | Get personalization profile                    |
| PATCH  | `/api/v1/users/preferences`         | Update personalization profile                 |
| GET    | `/api/v1/users/recommendations`     | Personalized recs                              |
| GET    | `/api/v1/admin/stats`               | Admin: system-wide counts                      |
| GET    | `/metrics`                          | Prometheus scrape endpoint                     |
| GET    | `/api/v1/health/ready`              | Readiness probe (DB + embedder)                |

Full OpenAPI at http://localhost:8000/docs.

---

## ⚙️ Configuration

All settings come from environment variables — see `.env.example` for the
exhaustive list. Critical ones:

| Var                          | Purpose                                          |
|------------------------------|--------------------------------------------------|
| `GEMINI_API_KEY`             | Your Google AI Studio key (required)             |
| `SECRET_KEY`                 | JWT signing key — **change for prod**            |
| `DATABASE_URL`               | Async Postgres URL                               |
| `VECTOR_STORE_BACKEND`       | `faiss` (default) or `chroma`                    |
| `EMBEDDING_MODEL`            | Hugging Face model id                            |
| `WHISPER_MODEL_SIZE`         | `tiny` / `base` / `small` / `medium` / `large-v3`|
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | Recursive chunker params                       |
| `USE_RERANKER`               | Toggle cross-encoder reranking                   |

---

## 🔒 Security

- Passwords bcrypt-hashed (cost 12, via passlib).
- JWT access tokens (60min) + refresh tokens (14d) with `type` claim.
- Rate limiting (`slowapi`) — defaults to 60/min/user.
- CORS allowlist via `CORS_ORIGINS`.
- Per-user ownership enforced on every video / conversation route.
- File uploads validated by MIME type + size cap (`MAX_UPLOAD_SIZE_MB`).
- Non-root container user where possible.

---

## 📈 Scaling Recommendations

| Bottleneck         | Mitigation                                                       |
|--------------------|------------------------------------------------------------------|
| Whisper / embedding| Run `worker` service horizontally (Redis BLPOP fan-out)          |
| FAISS size > 5M    | Switch to `chroma` or hosted vector DB (Pinecone/Weaviate/pgvector) |
| Gemini latency     | Already streaming — also enable prompt caching server-side       |
| Postgres           | Add a read replica for `/admin/stats` and analytics              |
| Storage            | Set `STORAGE_BACKEND=s3` and provide AWS creds                   |

---

## 🧪 Tests

```bash
cd backend
pytest -q                                 # unit
pytest --cov=app --cov-report=term-missing
```

---

## 📜 License

MIT — see `LICENSE` (add your own).
