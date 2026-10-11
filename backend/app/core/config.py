"""Typed application settings loaded from environment variables.

Pydantic validates every value at startup — if a required env var is missing
or malformed the process fails fast, which is exactly what we want in
production. Settings are a singleton (`get_settings()` is cached).
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import List, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- App ---
    APP_NAME: str = "video-rag-assistant"
    APP_ENV: Literal["development", "staging", "production"] = "development"
    APP_DEBUG: bool = True
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    APP_VERSION: str = "1.0.0"
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: Literal["json", "text"] = "json"

    # --- Security ---
    SECRET_KEY: str = Field(default="dev-secret-change-me-min-32-characters-long")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 14
    PASSWORD_HASH_SCHEME: str = "bcrypt"

    # --- CORS ---
    # Stored as a comma-separated string so Pydantic-Settings won't try to
    # JSON-decode it. Use `cors_origins` (the property) at call sites.
    CORS_ORIGINS: str = "http://localhost:3000"

    @property
    def cors_origins(self) -> List[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    # --- Database ---
    DATABASE_URL: str = (
        "postgresql+asyncpg://videorag:videorag_dev_pw@localhost:5432/videorag"
    )
    DATABASE_URL_SYNC: str = (
        "postgresql+psycopg2://videorag:videorag_dev_pw@localhost:5432/videorag"
    )
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20

    # --- Redis ---
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_ENABLED: bool = True

    # --- Storage ---
    STORAGE_BACKEND: Literal["local", "s3"] = "local"
    UPLOAD_DIR: Path = Path("./uploads")
    MAX_UPLOAD_SIZE_MB: int = 500

    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "us-east-1"
    S3_BUCKET: str = ""

    # --- Vector store ---
    VECTOR_STORE_BACKEND: Literal["faiss", "chroma"] = "faiss"
    VECTOR_STORE_DIR: Path = Path("./vector_store")
    EMBEDDING_DIM: int = 384

    # --- Embeddings ---
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    EMBEDDING_DEVICE: Literal["cpu", "cuda"] = "cpu"
    EMBEDDING_BATCH_SIZE: int = 32

    # --- Gemini ---
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.5-flash"
    GEMINI_TEMPERATURE: float = 0.3
    GEMINI_MAX_OUTPUT_TOKENS: int = 2048
    GEMINI_TOP_P: float = 0.95

    # --- Whisper / STT ---
    STT_BACKEND: Literal["faster-whisper", "openai-whisper"] = "faster-whisper"
    WHISPER_MODEL_SIZE: str = "base"
    WHISPER_DEVICE: str = "cpu"
    WHISPER_COMPUTE_TYPE: str = "int8"

    # --- RAG ---
    CHUNK_SIZE: int = 800
    CHUNK_OVERLAP: int = 120
    RETRIEVAL_TOP_K: int = 8
    RERANK_TOP_K: int = 4
    USE_HYBRID_SEARCH: bool = True
    USE_RERANKER: bool = True

    # --- Memory ---
    SHORT_TERM_MEMORY_TURNS: int = 10
    LONG_TERM_SUMMARY_THRESHOLD: int = 20

    # --- Rate limit ---
    RATE_LIMIT_PER_MINUTE: int = 60

    # --- MLflow ---
    MLFLOW_TRACKING_URI: str = "http://localhost:5000"
    MLFLOW_EXPERIMENT_NAME: str = "video-rag-assistant"

    # ---------- derived helpers ----------
    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

    def ensure_dirs(self) -> None:
        """Create storage directories at startup."""
        self.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        self.VECTOR_STORE_DIR.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached singleton — call this anywhere instead of instantiating Settings."""
    return Settings()  # type: ignore[call-arg]


settings = get_settings()
