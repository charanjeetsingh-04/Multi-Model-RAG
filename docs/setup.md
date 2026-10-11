# Step-by-step Setup Guide

## 1. Prerequisites

| Tool | Version |
|------|---------|
| Docker Desktop | 24+ |
| Python | 3.11+ (only for local dev without Docker) |
| Node | 20+ (only for local dev) |
| FFmpeg | 5+ (only for local dev) |

Get a Gemini API key from https://aistudio.google.com/app/apikey.

## 2. Clone & configure

```bash
git clone <repo> video-rag-assistant
cd video-rag-assistant
cp .env.example .env
```

Open `.env` and set:

```
GEMINI_API_KEY=<paste your key>
SECRET_KEY=<paste a 32+ char random string>
POSTGRES_PASSWORD=<strong password>
```

## 3. Launch with Docker

```bash
docker compose up --build
```

First-run sequence (~3-5 minutes):

1. Postgres + Redis + MLflow start.
2. Backend image builds (FFmpeg + Python deps).
3. Backend container runs `alembic upgrade head`, then Uvicorn.
4. Worker container starts and waits on the Redis queue.
5. Frontend builds and starts Next.js on port 3000.

## 4. Create an admin user

```bash
docker compose exec backend python -m scripts.create_admin \
    --email you@example.com --username you --password ChangeMe123!
```

## 5. Try it

1. Open http://localhost:3000.
2. Register an account (or log in as the admin).
3. Upload a video on the **Upload** page.
4. Wait for status → `ready` (visible in the Library page; polls every 5s).
5. Open **Chat**, optionally pick the specific video in the scope dropdown.
6. Ask: *"Summarize the main points and cite timestamps."*

## 6. Inspect the system

* API docs: http://localhost:8000/docs
* Prometheus: http://localhost:8000/metrics
* MLflow UI: http://localhost:5000
* Logs: `docker compose logs -f backend worker`

## 7. Local dev (no Docker)

```bash
# Backend
python -m venv .venv
. .venv/bin/activate
pip install -r backend/requirements.txt

# Bring up just Postgres + Redis
docker compose up -d postgres redis

# Migrations
cd backend
alembic upgrade head

# API
uvicorn app.main:app --reload

# Frontend (separate terminal)
cd ../frontend
npm install
npm run dev
```
