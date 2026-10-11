"""MLflow tracking for offline evaluation runs (eval scripts, A/B tests).

We don't log every chat — that's Prometheus' job. MLflow holds *experiments*:
when you tune chunk size, swap embedding model, or change reranker, log a
run here so you can compare retrieval@k / answer-quality across versions.
"""
from __future__ import annotations

from contextlib import contextmanager

import mlflow

from app.core.config import settings


def init_mlflow() -> None:
    mlflow.set_tracking_uri(settings.MLFLOW_TRACKING_URI)
    mlflow.set_experiment(settings.MLFLOW_EXPERIMENT_NAME)


@contextmanager
def run(name: str, tags: dict[str, str] | None = None):
    init_mlflow()
    with mlflow.start_run(run_name=name, tags=tags or {}) as r:
        yield r


def log_params(params: dict) -> None:
    mlflow.log_params(params)


def log_metrics(metrics: dict, step: int | None = None) -> None:
    mlflow.log_metrics(metrics, step=step)


def log_artifact(path: str) -> None:
    mlflow.log_artifact(path)
