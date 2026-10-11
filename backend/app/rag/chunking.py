"""Transcript chunking with timestamp preservation.

Why two strategies?
  * Recursive char-splitter: cheap, deterministic, works on any text.
  * Semantic: groups whisper segments that talk about the "same thing"
    using sentence-embedding cosine drift — better for narrated content
    where speaker pauses don't align with topic boundaries.

Either way we return `Chunk` objects that retain start/end times so
citations in the chat UI can render "Source 02:31–02:48".
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

import numpy as np
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.core.config import settings
from app.rag.transcription import TranscriptSegment
from app.utils.text import clean_transcript, estimate_tokens


@dataclass
class Chunk:
    index: int
    text: str
    start_time: float | None = None
    end_time: float | None = None
    token_count: int = 0
    metadata: dict = field(default_factory=dict)


class RecursiveChunker:
    """Char-based recursive splitter that re-attaches timestamps.

    Approach: split the cleaned full transcript with LangChain's recursive
    splitter (works on paragraphs → sentences → words), then map each chunk
    back to whisper segments by character position to recover start/end times.
    """

    def __init__(
        self,
        chunk_size: int = settings.CHUNK_SIZE,
        chunk_overlap: int = settings.CHUNK_OVERLAP,
    ) -> None:
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", ". ", "? ", "! ", "; ", ", ", " ", ""],
            length_function=len,
        )

    def chunk(self, segments: Sequence[TranscriptSegment]) -> list[Chunk]:
        if not segments:
            return []

        # Build a (char_position → segment) index so we can map back.
        spans: list[tuple[int, int, TranscriptSegment]] = []
        running = ""
        for seg in segments:
            start_pos = len(running)
            running += seg.text + " "
            spans.append((start_pos, len(running), seg))

        running = clean_transcript(running)
        pieces = self.splitter.split_text(running)

        chunks: list[Chunk] = []
        cursor = 0
        for i, piece in enumerate(pieces):
            # Find piece in running starting from cursor (chunks are in order)
            pos = running.find(piece, max(0, cursor - settings.CHUNK_OVERLAP))
            if pos == -1:
                pos = cursor
            end = pos + len(piece)
            cursor = pos + max(1, len(piece) - settings.CHUNK_OVERLAP)

            start_time, end_time = self._lookup_times(spans, pos, end)
            chunks.append(
                Chunk(
                    index=i,
                    text=piece.strip(),
                    start_time=start_time,
                    end_time=end_time,
                    token_count=estimate_tokens(piece),
                )
            )
        return chunks

    @staticmethod
    def _lookup_times(
        spans: list[tuple[int, int, TranscriptSegment]],
        char_start: int,
        char_end: int,
    ) -> tuple[float | None, float | None]:
        start_t: float | None = None
        end_t: float | None = None
        for s_start, s_end, seg in spans:
            if s_end < char_start:
                continue
            if s_start > char_end:
                break
            if start_t is None:
                start_t = seg.start
            end_t = seg.end
        return start_t, end_t


class SemanticChunker:
    """Groups adjacent whisper segments by embedding similarity.

    Heavy compared to RecursiveChunker but produces semantically coherent
    chunks — fewer "topic mid-cut" chunks ⇒ better retrieval quality.
    """

    def __init__(self, embedder, threshold: float = 0.6, max_tokens: int = settings.CHUNK_SIZE) -> None:
        self.embedder = embedder
        self.threshold = threshold
        self.max_tokens = max_tokens

    def chunk(self, segments: Sequence[TranscriptSegment]) -> list[Chunk]:
        if not segments:
            return []
        texts = [s.text for s in segments]
        embeddings = self.embedder.embed_batch(texts)
        embeddings = np.asarray(embeddings, dtype=np.float32)

        chunks: list[Chunk] = []
        current_text: list[str] = []
        current_start = segments[0].start
        current_end = segments[0].end
        current_tokens = 0

        for i, seg in enumerate(segments):
            tokens = estimate_tokens(seg.text)
            # Break if either: (a) similarity to previous drops below threshold
            # or (b) chunk exceeds max tokens
            similarity = 1.0
            if i > 0:
                a, b = embeddings[i - 1], embeddings[i]
                similarity = float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))

            should_split = (similarity < self.threshold) or (current_tokens + tokens > self.max_tokens)
            if should_split and current_text:
                chunks.append(
                    Chunk(
                        index=len(chunks),
                        text=clean_transcript(" ".join(current_text)),
                        start_time=current_start,
                        end_time=current_end,
                        token_count=current_tokens,
                    )
                )
                current_text = []
                current_tokens = 0
                current_start = seg.start

            current_text.append(seg.text)
            current_end = seg.end
            current_tokens += tokens

        if current_text:
            chunks.append(
                Chunk(
                    index=len(chunks),
                    text=clean_transcript(" ".join(current_text)),
                    start_time=current_start,
                    end_time=current_end,
                    token_count=current_tokens,
                )
            )
        return chunks
