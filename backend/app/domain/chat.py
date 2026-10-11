"""Domain dataclasses for chat — used between services and the LLM layer."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field


@dataclass
class RetrievedPassage:
    chunk_id: uuid.UUID
    video_id: uuid.UUID
    text: str
    score: float
    start_time: float | None = None
    end_time: float | None = None


@dataclass
class ChatTurn:
    role: str          # "user" | "assistant" | "system"
    content: str


@dataclass
class CitationDTO:
    index: int
    chunk_id: str
    video_id: str
    score: float
    start_time: float | None = None
    end_time: float | None = None
    snippet: str | None = None


@dataclass
class ChatResult:
    conversation_id: uuid.UUID
    message_id: uuid.UUID
    text: str
    citations: list[CitationDTO] = field(default_factory=list)
    tokens_in: int | None = None
    tokens_out: int | None = None
    latency_ms: int = 0
