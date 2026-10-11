# Deployment Guide

## Local (Docker Compose)

```bash
cp .env.example .env
# Set GEMINI_API_KEY, SECRET_KEY (32+ chars), POSTGRES_PASSWORD
docker compose up --build
```

The first launch takes a few minutes — Whisper + MiniLM models are
downloaded into the `hfcache` volume and reused on subsequent boots.

## Production checklist

- [ ] Set `APP_ENV=production`, `APP_DEBUG=false`, `LOG_FORMAT=json`.
- [ ] Rotate `SECRET_KEY` to a 64-char random string.
- [ ] Restrict `CORS_ORIGINS` to your real frontend domains.
- [ ] Put a TLS-terminating proxy (Nginx, Cloudflare, ALB) in front of `backend` and `frontend`.
- [ ] Move uploads to S3: `STORAGE_BACKEND=s3` + credentials.
- [ ] Move vectors to a managed DB (pgvector / Pinecone) once index size > a few hundred MB.
- [ ] Use a managed Postgres (RDS, Cloud SQL) with daily snapshots.
- [ ] Scale workers: `docker compose up --scale worker=4`.
- [ ] Wire Prometheus scrape against `:8000/metrics` and pipe to Grafana.
- [ ] Enable a CDN in front of the Next.js standalone build.
- [ ] Rate-limit tuning: set `RATE_LIMIT_PER_MINUTE` per your billing tolerance.

## Kubernetes (sketch)

* One Deployment per service (backend, worker, frontend, mlflow).
* Postgres + Redis as managed services or a StatefulSet.
* `livenessProbe`: `GET /api/v1/health/live`
* `readinessProbe`: `GET /api/v1/health/ready`
* HPA on backend keyed on `http_request_duration_seconds_bucket` from Prometheus.
* HPA on worker keyed on Redis queue length (use `keda` if available).

## Migrations

```bash
docker compose exec backend alembic upgrade head
# To create a new revision after model edits:
docker compose exec backend alembic revision --autogenerate -m "describe change"
```

## Backups

* Postgres: nightly `pg_dump` to S3.
* Vector store: snapshot the `vectors` Docker volume (or migrate to pgvector).
* Uploads: replicate from S3 cross-region.
