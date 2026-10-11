"""Text cleaning helpers used across transcription + chunking."""
from __future__ import annotations

import re

_WHITESPACE = re.compile(r"\s+")
_REPEATED_PUNCT = re.compile(r"([.!?,])\1{2,}")
_NON_PRINTABLE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def clean_transcript(text: str) -> str:
    """Normalize transcript output for chunking + indexing."""
    if not text:
        return ""
    text = _NON_PRINTABLE.sub("", text)
    text = _REPEATED_PUNCT.sub(r"\1", text)
    text = _WHITESPACE.sub(" ", text).strip()
    return text


def estimate_tokens(text: str) -> int:
    """Rough estimate (~4 chars/token) used for budgeting LLM context."""
    return max(1, len(text) // 4)


def truncate_to_tokens(text: str, max_tokens: int) -> str:
    """Hard-truncate to a token budget (char approximation)."""
    max_chars = max_tokens * 4
    return text if len(text) <= max_chars else text[:max_chars] + "…"
