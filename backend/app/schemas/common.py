"""Shared response shapes."""
from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PageMeta(BaseModel):
    total: int
    page: int = 1
    page_size: int = 20


class Page(BaseModel, Generic[T]):
    items: list[T]
    meta: PageMeta


class HealthStatus(BaseModel):
    status: str = "ok"
    version: str
    env: str
    components: dict[str, str] = Field(default_factory=dict)


class StatusMessage(BaseModel):
    status: str = "ok"
    message: str | None = None
