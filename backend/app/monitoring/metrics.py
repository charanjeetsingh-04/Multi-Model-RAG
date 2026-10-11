"""Custom Prometheus metrics on top of the FastAPI instrumentator defaults.

We expose:
  * llm_requests_total{model,status}
  * llm_latency_seconds{model}      (histogram)
  * llm_tokens_total{model,kind}    (counter, kind=in|out)
  * retrieval_latency_seconds       (histogram)
  * video_processing_total{status}
"""
from __future__ import annotations

from prometheus_client import Counter, Histogram

LLM_REQUESTS = Counter(
    "llm_requests_total",
    "Total LLM calls",
    labelnames=("model", "status"),
)
LLM_LATENCY = Histogram(
    "llm_latency_seconds",
    "LLM call latency",
    labelnames=("model",),
    buckets=(0.25, 0.5, 1, 2, 4, 8, 16, 32),
)
LLM_TOKENS = Counter(
    "llm_tokens_total",
    "Tokens consumed",
    labelnames=("model", "kind"),
)
RETRIEVAL_LATENCY = Histogram(
    "retrieval_latency_seconds",
    "Retrieval latency",
    buckets=(0.025, 0.05, 0.1, 0.25, 0.5, 1, 2),
)
VIDEO_PROCESSING = Counter(
    "video_processing_total",
    "Video processing pipeline outcomes",
    labelnames=("status",),
)
APP_ERRORS = Counter(
    "app_errors_total",
    "Domain errors raised, labeled by registry code",
    labelnames=("code",),
)
CACHE_OPS = Counter(
    "cache_ops_total",
    "Cache hits / misses / sets",
    labelnames=("op",),  # hit | miss | set | invalidate
)
EMBED_CACHE = Counter(
    "embedding_cache_total",
    "Embedding cache outcomes",
    labelnames=("result",),  # hit | miss
)
TASK_QUEUE_LATENCY = Histogram(
    "task_queue_latency_seconds",
    "Latency from enqueue to handler start",
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 30, 60),
)
