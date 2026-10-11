"""Legacy entrypoint — kept so old docker-compose definitions still work.

Prefer Celery:
    celery -A app.workers.celery_app worker -Q ingest --concurrency=2

This shim simply launches the Celery worker via its own CLI.
"""
from __future__ import annotations

import sys

from celery.bin.celery import main as celery_main


def main() -> None:
    sys.argv = [
        "celery",
        "-A",
        "app.workers.celery_app",
        "worker",
        "-Q",
        "ingest,maintenance,default",
        "--concurrency=2",
        "--loglevel=INFO",
    ]
    celery_main()


if __name__ == "__main__":
    main()
