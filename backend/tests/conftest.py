"""Shared fixtures.

Strategy:
  * Unit tests = use fakes from `tests/fakes.py`. Zero infra.
  * Integration tests = mark `@pytest.mark.integration`. CI sets up Postgres
    + Redis via `docker compose up -d postgres redis`. Run with:
        pytest -m integration
"""
from __future__ import annotations

import asyncio
import os

import pytest

# Avoid loading the real settings cache in test environment
os.environ.setdefault("GEMINI_API_KEY", "test")
os.environ.setdefault("REDIS_ENABLED", "false")
os.environ.setdefault("APP_ENV", "development")


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
def _no_real_cache(monkeypatch):
    """Hard-replace the cache singleton with a NullCache for all tests."""
    from app.cache import backend

    monkeypatch.setattr(backend, "_cache", backend.NullCache())
    yield
    monkeypatch.setattr(backend, "_cache", None)
