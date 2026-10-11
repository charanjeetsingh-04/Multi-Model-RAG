# Final optimized folder structure (v2)

```
project-root/
├── backend/
│   ├── alembic/
│   │   └── versions/
│   │       ├── 0001_initial_schema.py
│   │       └── 0002_perf_indexes.py            # v2: hot-path composite indexes
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                             # app factory; wires OTel + middleware + DI
│   │   ├── api/
│   │   │   └── v1/
│   │   │       ├── router.py
│   │   │       └── routes/                     # thin handlers — only HTTP shape
│   │   │           ├── admin.py
│   │   │           ├── auth.py
│   │   │           ├── chat.py                 # SSE streaming + sync chat
│   │   │           ├── health.py               # live + ready probes
│   │   │           ├── users.py
│   │   │           └── videos.py
│   │   ├── auth/
│   │   │   ├── dependencies.py                 # get_current_user, require_admin
│   │   │   └── security.py                     # JWT + bcrypt
│   │   ├── cache/                              # ★ NEW v2
│   │   │   ├── backend.py                      # RedisCache + NullCache
│   │   │   ├── decorators.py                   # @cached, @invalidates
│   │   │   └── keys.py                         # CacheKeys registry
│   │   ├── core/
│   │   │   ├── config.py                       # Pydantic Settings
│   │   │   ├── errors.py                       # ★ ErrorCode registry
│   │   │   ├── exceptions.py                   # ★ RFC 7807 envelope
│   │   │   ├── logging.py                      # ★ structlog + OTel binding
│   │   │   └── observability.py                # ★ OTel bootstrap
│   │   ├── db/
│   │   │   ├── base.py
│   │   │   └── session.py
│   │   ├── dependencies/                       # ★ NEW v2 — DI providers
│   │   │   ├── repositories.py
│   │   │   └── services.py
│   │   ├── domain/                             # ★ NEW v2 — pure types
│   │   │   └── chat.py
│   │   ├── embeddings/
│   │   │   └── embedder.py                     # ★ Redis content-hash cache
│   │   ├── llm/
│   │   │   ├── gemini_client.py                # ★ token counter + idempotency cache
│   │   │   └── prompts.py                      # ★ tight prompts, lower tokens
│   │   ├── memory/__init__.py                  # compat shim → services/memory_service
│   │   ├── middleware/
│   │   │   ├── rate_limit.py
│   │   │   └── request_context.py              # ★ gateway-aware (X-Request-ID, X-Forwarded-For)
│   │   ├── models/                             # SQLAlchemy ORM
│   │   │   ├── chat.py
│   │   │   ├── user.py
│   │   │   └── video.py
│   │   ├── monitoring/
│   │   │   ├── metrics.py                      # ★ APP_ERRORS, CACHE_OPS, EMBED_CACHE
│   │   │   └── mlflow_tracker.py
│   │   ├── rag/
│   │   │   ├── audio.py
│   │   │   ├── chunking.py
│   │   │   ├── context_builder.py              # ★ tighter token budget (2500)
│   │   │   ├── retriever.py                    # ★ parallel dense+sparse, retrieval cache
│   │   │   ├── transcription.py
│   │   │   └── vector_store.py
│   │   ├── repositories/                       # ★ NEW v2
│   │   │   ├── base.py
│   │   │   ├── chat_repository.py
│   │   │   ├── preference_repository.py
│   │   │   ├── user_repository.py
│   │   │   └── video_repository.py
│   │   ├── schemas/                            # Pydantic API DTOs
│   │   │   ├── chat.py
│   │   │   ├── common.py
│   │   │   ├── user.py
│   │   │   └── video.py
│   │   ├── services/
│   │   │   ├── chat_service.py                 # ★ asyncio.gather for parallel memory+RAG
│   │   │   ├── memory_service.py               # ★ moved from app/memory; cached profile
│   │   │   ├── user_service.py                 # ★ repo-based
│   │   │   └── video_service.py                # ★ repo-based + bulk insert
│   │   ├── storage/
│   │   │   ├── base.py
│   │   │   ├── factory.py
│   │   │   ├── local.py
│   │   │   └── s3.py
│   │   ├── utils/
│   │   │   ├── files.py
│   │   │   └── text.py
│   │   └── workers/
│   │       ├── celery_app.py                   # ★ NEW v2 — Celery wiring + Beat schedule
│   │       ├── tasks.py                        # ★ process_video + maintenance jobs
│   │       ├── video_worker.py                 # legacy shim → Celery
│   │       └── queue.py                        # legacy shim (deprecated)
│   ├── tests/
│   │   ├── conftest.py                         # ★ shared fixtures + cache muzzle
│   │   ├── fakes.py                            # ★ in-memory repos for unit tests
│   │   ├── integration/                        # ★ marked `integration`
│   │   │   └── test_health.py
│   │   └── unit/                               # ★ pure unit tests
│   │       ├── test_cache_decorators.py
│   │       ├── test_error_envelope.py
│   │       └── test_user_service.py
│   ├── alembic.ini
│   ├── pyproject.toml
│   ├── pytest.ini
│   └── requirements.txt                        # ★ +celery, +flower, +opentelemetry
├── docker/
│   ├── backend.Dockerfile
│   ├── frontend.Dockerfile
│   └── mlflow.Dockerfile
├── docker-compose.yml                          # ★ Celery worker/beat/flower services
├── docs/
│   ├── ARCHITECTURE_V2.md                      # ★ v2 architecture
│   ├── COST.md                                 # ★ cost strategy
│   ├── FOLDER_STRUCTURE_V2.md                  # ★ this file
│   ├── PERFORMANCE.md                          # ★ perf playbook
│   ├── SCALING.md                              # ★ scaling tiers
│   ├── api.md
│   ├── architecture.md
│   ├── deployment.md
│   ├── env_vars.md
│   └── setup.md
├── frontend/                                   # Next.js 14
│   └── (unchanged structure)
├── k8s/                                        # ★ NEW v2
│   ├── base/
│   │   ├── backend.yaml                        # Deployment + Service + HPA + PDB
│   │   ├── configmap.yaml
│   │   ├── frontend.yaml
│   │   ├── ingress.yaml                        # incl. NetworkPolicy
│   │   ├── kustomization.yaml
│   │   ├── migration-job.yaml                  # alembic upgrade head
│   │   ├── namespace.yaml
│   │   ├── secret.example.yaml
│   │   ├── storage.yaml                        # RWX PVCs
│   │   └── worker.yaml                         # Celery + Beat + Flower
│   └── overlays/
│       ├── production/kustomization.yaml
│       └── staging/kustomization.yaml
├── scripts/
│   ├── create_admin.py
│   ├── eval_retrieval.py
│   ├── setup.ps1
│   └── setup.sh
├── uploads/   vector_store/   logs/   notebooks/
├── .dockerignore
├── .env / .env.example
├── .gitignore
└── README.md
```

Legend: **★** = added or significantly refactored in v2.
