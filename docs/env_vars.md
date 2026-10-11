# Environment Variables Reference

This is the authoritative list. Anything in `.env.example` matches what
`app.core.config.Settings` parses.

## Application
| Name | Default | Notes |
|------|---------|-------|
| `APP_NAME` | `video-rag-assistant` | Used in logs + metadata |
| `APP_ENV` | `development` | `development\|staging\|production` |
| `APP_DEBUG` | `true` | Disable in prod |
| `APP_HOST` | `0.0.0.0` | Bind address |
| `APP_PORT` | `8000` | |
| `LOG_LEVEL` | `INFO` | |
| `LOG_FORMAT` | `json` | `json` (prod) or `text` (dev) |

## Security
| Name | Default | Notes |
|------|---------|-------|
| `SECRET_KEY` | dev placeholder | **Rotate for production.** Min 32 chars. |
| `JWT_ALGORITHM` | `HS256` | |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `14` | |

## CORS
| Name | Default | Notes |
|------|---------|-------|
| `CORS_ORIGINS` | `http://localhost:3000` | Comma-separated |

## Database
| Name | Default | Notes |
|------|---------|-------|
| `DATABASE_URL` | (asyncpg URL) | Used by the app |
| `DATABASE_URL_SYNC` | (psycopg2 URL) | Used by Alembic |
| `DB_POOL_SIZE` | `10` | |
| `DB_MAX_OVERFLOW` | `20` | |

## Redis
| Name | Default | Notes |
|------|---------|-------|
| `REDIS_URL` | `redis://localhost:6379/0` | |
| `REDIS_ENABLED` | `true` | Set `false` to disable cache |

## Storage
| Name | Default | Notes |
|------|---------|-------|
| `STORAGE_BACKEND` | `local` | `local\|s3` |
| `UPLOAD_DIR` | `./uploads` | |
| `MAX_UPLOAD_SIZE_MB` | `500` | |
| `AWS_*`, `S3_BUCKET` | | only used if `STORAGE_BACKEND=s3` |

## Vector store / Embeddings
| Name | Default | Notes |
|------|---------|-------|
| `VECTOR_STORE_BACKEND` | `faiss` | `faiss\|chroma` |
| `VECTOR_STORE_DIR` | `./vector_store` | |
| `EMBEDDING_DIM` | `384` | Must match the embedding model |
| `EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | |
| `EMBEDDING_DEVICE` | `cpu` | `cpu\|cuda` |
| `EMBEDDING_BATCH_SIZE` | `32` | |

## Gemini
| Name | Default | Notes |
|------|---------|-------|
| `GEMINI_API_KEY` | _(empty)_ | **Required.** |
| `GEMINI_MODEL` | `gemini-2.5-flash` | |
| `GEMINI_TEMPERATURE` | `0.3` | |
| `GEMINI_MAX_OUTPUT_TOKENS` | `2048` | |
| `GEMINI_TOP_P` | `0.95` | |

## STT
| Name | Default | Notes |
|------|---------|-------|
| `STT_BACKEND` | `faster-whisper` | |
| `WHISPER_MODEL_SIZE` | `base` | Use `small`/`medium` for better quality |
| `WHISPER_DEVICE` | `cpu` | |
| `WHISPER_COMPUTE_TYPE` | `int8` | `int8` is best on CPU |

## RAG
| Name | Default | Notes |
|------|---------|-------|
| `CHUNK_SIZE` | `800` | Chars |
| `CHUNK_OVERLAP` | `120` | Chars |
| `RETRIEVAL_TOP_K` | `8` | Pre-rerank |
| `RERANK_TOP_K` | `4` | Post-rerank |
| `USE_HYBRID_SEARCH` | `true` | Dense + BM25 |
| `USE_RERANKER` | `true` | Cross-encoder |

## Memory
| Name | Default | Notes |
|------|---------|-------|
| `SHORT_TERM_MEMORY_TURNS` | `10` | Recent turns to include in prompt |
| `LONG_TERM_SUMMARY_THRESHOLD` | `20` | Recompute summary every N messages |

## Rate limit / MLflow
| Name | Default | Notes |
|------|---------|-------|
| `RATE_LIMIT_PER_MINUTE` | `60` | Per user (or IP if anonymous) |
| `MLFLOW_TRACKING_URI` | `http://localhost:5000` | |
| `MLFLOW_EXPERIMENT_NAME` | `video-rag-assistant` | |

## Frontend
| Name | Default | Notes |
|------|---------|-------|
| `NEXT_PUBLIC_API_BASE_URL` | `http://localhost:8000` | |
| `NEXT_PUBLIC_APP_NAME` | `Video RAG Assistant` | |
