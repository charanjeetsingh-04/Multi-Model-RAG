"""Context window builder.

Takes retrieved chunks + memory + system prompt, fits them into the LLM's
context budget. Order:
  1. System instructions
  2. Long-term memory summary (if any)
  3. Recent conversation turns (short-term memory)
  4. Retrieved passages (with citation tags)
  5. The user's new question

Each passage is wrapped:   [#1] (video=<id> 00:12-00:48): "..."
so the LLM can cite by number and we can look up the citation later.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.rag.retriever import RetrievedChunk
from app.utils.text import estimate_tokens, truncate_to_tokens


@dataclass
class ContextBlock:
    text: str
    citations: list[dict]   # parallel to "[#N]" markers in `text`
    tokens: int


class ContextBuilder:
    def __init__(self, max_context_tokens: int = 2500) -> None:
        # Tighter budget = lower token bill + faster Gemini response.
        # 2500 fits ~10 typical passages, plenty for top_k=4-8 RAG.
        self.max_tokens = max_context_tokens

    def build(self, chunks: list[RetrievedChunk]) -> ContextBlock:
        if not chunks:
            return ContextBlock(text="", citations=[], tokens=0)

        lines: list[str] = []
        citations: list[dict] = []
        total = 0
        for i, c in enumerate(chunks, start=1):
            ts = ""
            if c.start_time is not None and c.end_time is not None:
                ts = f" [{self._fmt(c.start_time)}–{self._fmt(c.end_time)}]"
            line = f"[#{i}] (video={c.video_id}{ts}): {c.text}"
            line_tokens = estimate_tokens(line)
            if total + line_tokens > self.max_tokens:
                line = truncate_to_tokens(line, self.max_tokens - total)
                lines.append(line)
                citations.append(self._citation(i, c))
                break
            lines.append(line)
            citations.append(self._citation(i, c))
            total += line_tokens

        return ContextBlock(text="\n\n".join(lines), citations=citations, tokens=total)

    @staticmethod
    def _citation(idx: int, c: RetrievedChunk) -> dict:
        return {
            "index": idx,
            "chunk_id": str(c.chunk_id),
            "video_id": str(c.video_id),
            "score": round(c.score, 4),
            "start_time": c.start_time,
            "end_time": c.end_time,
            "snippet": c.text[:180],
        }

    @staticmethod
    def _fmt(seconds: float) -> str:
        m, s = divmod(int(seconds), 60)
        return f"{m:02d}:{s:02d}"
