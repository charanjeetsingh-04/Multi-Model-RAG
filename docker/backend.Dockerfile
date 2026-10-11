# =========================================================================
# Backend image — FastAPI + AI deps + FFmpeg
# =========================================================================
FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/cache/hf \
    TRANSFORMERS_CACHE=/cache/hf \
    SENTENCE_TRANSFORMERS_HOME=/cache/hf

# System deps: ffmpeg for audio, gcc for any wheels that need it, libgomp for faiss
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    build-essential \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Layered install for cache-friendliness
COPY backend/requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt

# Copy source last so editing code doesn't bust the deps layer
COPY backend /app/
COPY .env.example /app/.env.example

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD curl -fsS http://localhost:8000/api/v1/health/live || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
