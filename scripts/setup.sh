#!/usr/bin/env bash
# One-shot local dev setup (Linux/macOS/WSL).
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env — open it and set GEMINI_API_KEY."
fi

python -m venv .venv
. .venv/bin/activate
pip install --upgrade pip
pip install -r backend/requirements.txt

mkdir -p uploads vector_store logs

(cd frontend && npm install)
echo "Done. Run:  docker compose up -d postgres redis  &&  alembic upgrade head"
