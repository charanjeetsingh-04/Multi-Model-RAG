# How to Run — Multi-Modal Video RAG Assistant

A practical, step-by-step guide. Pick **one** of the three paths below.

---

## TL;DR

| Goal | Recommended path |
|------|------------------|
| Just want it working in 5 minutes | **Path A — Docker Compose** |
| You want hot-reload while coding | **Path B — Local hybrid (Docker for infra, Python/Node native)** |
| You need to push to a cluster | **Path C — Kubernetes** |

Pre-flight in all cases:
```powershell
# from project root
copy .env.example .env  # if .env doesn't exist
# open .env and confirm GEMINI_API_KEY is set
```

---

## Path A — Docker Compose (recommended)

This brings up Postgres + Redis + MLflow + backend + Celery worker + Celery Beat + Flower + frontend in one command. No Python/Node installed on host required.

### Requirements

- Docker Desktop 24+ with Compose v2 (`docker compose version` ≥ 2.20)
- ~6 GB free RAM for the containers
- ~5 GB free disk (mostly the HuggingFace cache for Whisper/MiniLM on first run)

### Steps

```powershell
# 1. Set Gemini key (already done if you ran `cp .env.example .env`)
notepad .env   # confirm GEMINI_API_KEY=...

# 2. Build images + start everything
docker compose up --build -d

# 3. Watch logs while models warm up (~2-3 min on first run)
docker compose logs -f backend worker
# Ctrl+C when you see "app_starting" → "Uvicorn running" → "worker ready"

# 4. Run DB migrations (idempotent; backend also auto-runs them on boot)
docker compose exec backend alembic upgrade head

# 5. Create an admin user
docker compose exec backend python -m scripts.create_admin `
    --email you@example.com --username you --password ChangeMe123!
```

### Open these in a browser

| What | URL |
|------|-----|
| Frontend (the app) | http://localhost:3000 |
| API docs (Swagger) | http://localhost:8000/docs |
| Prometheus metrics | http://localhost:8000/metrics |
| Flower (Celery UI)  | http://localhost:5555 |
| MLflow              | http://localhost:5000 |

### Verify the stack

```powershell
# Health probe
curl http://localhost:8000/api/v1/health/ready

# Should return:
# { "status": "ok", "version": "1.0.0", "env": "development", "components": { "database": "ok", "embedder": "ok" } }
```

### Stop / restart / clean

```powershell
docker compose down               # stop containers (keeps volumes)
docker compose down -v            # also wipe Postgres + uploads + vectors (DESTRUCTIVE)
docker compose up -d backend      # restart only the backend
docker compose logs -f worker     # tail celery worker logs
```

---

## Path B — Local hybrid (best for development)

Postgres + Redis run in Docker (so you don't have to install them), but the backend and frontend run natively for hot-reload.

### Requirements

- Python 3.11+ (`python --version`)
- Node 20+ (`node --version`)
- FFmpeg in PATH (`ffmpeg -version`)
- Docker (just for Postgres + Redis)

### Steps

```powershell
# 1. Infra in Docker
docker compose up -d postgres redis

# 2. Python env + deps
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r backend/requirements.txt

# 3. DB migrations
cd backend
alembic upgrade head
cd ..

# 4. Backend (terminal 1)
uvicorn app.main:app --reload --app-dir backend --host 0.0.0.0 --port 8000

# 5. Celery worker (terminal 2)
.\.venv\Scripts\Activate.ps1
cd backend
celery -A app.workers.celery_app worker -Q ingest,maintenance,default --concurrency=2 --loglevel=INFO

# 6. Celery beat (terminal 3, optional — only if you want periodic jobs)
.\.venv\Scripts\Activate.ps1
cd backend
celery -A app.workers.celery_app beat --loglevel=INFO

# 7. Frontend (terminal 4)
cd frontend
npm install
npm run dev
```

> **On Windows**, Celery's default prefork pool can misbehave. If you see worker hangs, run with the `solo` pool while developing:
> ```powershell
> celery -A app.workers.celery_app worker -Q ingest --pool=solo --loglevel=INFO
> ```

### First request flow (manual smoke test)

```powershell
# Register
curl -X POST http://localhost:8000/api/v1/auth/register `
    -H "Content-Type: application/json" `
    -d "{\"email\":\"a@b.com\",\"username\":\"alice\",\"password\":\"Min8Chars!\"}"

# Login → grab the access_token
curl -X POST http://localhost:8000/api/v1/auth/login `
    -H "Content-Type: application/json" `
    -d "{\"email\":\"a@b.com\",\"password\":\"Min8Chars!\"}"

# Upload (replace TOKEN + path)
curl -X POST http://localhost:8000/api/v1/videos/upload `
    -H "Authorization: Bearer TOKEN" `
    -F "title=Demo" -F "file=@C:\path\to\video.mp4"
```

Open http://localhost:3000 and the UI will pick up everything.

---

## Path C — Kubernetes

Full manifests live under [k8s/](./k8s/). Use Kustomize:

```bash
# Staging
kubectl apply -k k8s/overlays/staging

# Production
kubectl apply -k k8s/overlays/production
```

Pre-reqs:
- A cluster with an Ingress controller (NGINX recommended) and cert-manager.
- A `Secret` named `video-rag-secrets` (see [k8s/base/secret.example.yaml](./k8s/base/secret.example.yaml)).
- A RWX `StorageClass` for shared uploads/vectors (EFS / Filestore / Azure Files), or set `STORAGE_BACKEND=s3` and remove the PVCs.

Confirm:
```bash
kubectl -n video-rag get pods,svc,ingress,hpa
kubectl -n video-rag logs deploy/backend -f
```

---

## Common issues + fixes

| Symptom | Fix |
|---------|-----|
| `Connection refused` on Postgres | `docker compose up -d postgres` first; then `docker compose ps` to confirm it's healthy. |
| `Could not import module "main"` from Uvicorn | You ran `uvicorn` from the wrong directory. Use `--app-dir backend`. |
| Backend stuck on "Loading whisper" the first time | Normal — Whisper + MiniLM weights are ~600 MB. Watch `docker compose logs -f backend`; the second boot is instant. |
| `GEMINI_API_KEY is not configured` | Open `.env` and paste the key. Restart the affected container. |
| Video processing stays in `extracting_audio` | Ensure the worker is running and connected to the same Redis. `docker compose logs worker` will show task pickups. |
| Frontend says "CORS error" | Add your frontend origin to `CORS_ORIGINS` in `.env`, then restart backend. |
| `permission denied` on uploads volume (Linux/Mac) | `chown -R 1000:1000 ./uploads ./vector_store` — the container user is uid 1000. |
| Port already in use | `docker compose down` or change the port mapping in `docker-compose.yml`. |
| Mac M-series: FAISS install fails locally | Stick with Docker (Path A) or `pip install faiss-cpu==1.8.0 --no-deps` then install other deps. |

## Run the tests

```powershell
# Unit tests (no infra needed)
.\.venv\Scripts\Activate.ps1
cd backend
pytest tests/unit -q

# Integration tests (needs Postgres + Redis running)
docker compose up -d postgres redis
pytest -m integration -q
```

## Where the data lives

| Thing | Location |
|-------|----------|
| Uploaded videos | `./uploads/<user_uuid>/<uuid>__name.mp4` (or S3 if configured) |
| FAISS index + metadata | `./vector_store/index.faiss` + `meta.json` |
| Logs | container stdout (JSON in prod); `./logs/` for local file logging |
| Postgres data | Docker volume `pgdata` |
| Redis data | in-memory (ephemeral by default) |
| HuggingFace model cache | Docker volume `hfcache` (so re-creating the backend container is fast) |

## Tearing it all down

```powershell
docker compose down -v        # removes containers AND volumes — fresh slate
Remove-Item -Recurse -Force .\uploads\*, .\vector_store\*, .\logs\* -ErrorAction SilentlyContinue
```
