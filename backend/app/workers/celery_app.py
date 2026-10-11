"""Celery app — one place to configure broker, results, queues, retries.

Run worker:    celery -A app.workers.celery_app worker -Q ingest,maintenance --concurrency=2
Run beat:      celery -A app.workers.celery_app beat
Run flower:    celery -A app.workers.celery_app flower --port=5555
"""
from __future__ import annotations

from celery import Celery
from celery.signals import after_setup_logger, task_prerun

from app.core.config import settings
from app.core.logging import configure_logging, get_logger

celery_app = Celery(
    "video_rag",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,        # heavy tasks: don't hoard
    task_default_queue="default",
    task_routes={
        "app.workers.tasks.process_video": {"queue": "ingest"},
        "app.workers.tasks.cleanup_failed_videos": {"queue": "maintenance"},
        "app.workers.tasks.summarize_inactive_conversations": {"queue": "maintenance"},
    },
    task_default_retry_delay=10,
    task_time_limit=60 * 30,             # hard kill after 30 min
    task_soft_time_limit=60 * 25,
    broker_connection_retry_on_startup=True,
    result_expires=60 * 60 * 24,         # 1 day TTL on results
    timezone="UTC",
    enable_utc=True,
)

# Periodic schedule
celery_app.conf.beat_schedule = {
    "cleanup-failed-videos-hourly": {
        "task": "app.workers.tasks.cleanup_failed_videos",
        "schedule": 60 * 60,             # every hour
    },
    "summarize-inactive-conversations-daily": {
        "task": "app.workers.tasks.summarize_inactive_conversations",
        "schedule": 60 * 60 * 24,        # every 24h
    },
}


@after_setup_logger.connect
def _configure_celery_logging(*_args, **_kwargs):
    configure_logging()


@task_prerun.connect
def _bind_task_logger(sender=None, task_id=None, task=None, **_):
    log = get_logger("celery")
    log.info("task_start", task=getattr(task, "name", "?"), task_id=task_id)
