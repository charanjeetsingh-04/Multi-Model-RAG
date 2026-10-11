"""Speech-to-text using faster-whisper.

Whisper is the de-facto open transcription model. `faster-whisper` (CTranslate2
backend) is ~4× quicker and uses less RAM than the original. The model is
loaded lazily and cached — first call pays the ~30s warmup cost, every
subsequent call is fast.

The output `TranscriptSegment` carries timestamps so chunks remain
time-aligned for citations in the chat UI ("00:12 → 00:48").
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class TranscriptSegment:
    start: float
    end: float
    text: str


@dataclass(frozen=True)
class TranscriptionResult:
    text: str
    language: str
    segments: list[TranscriptSegment]
    duration: float


@lru_cache(maxsize=1)
def _get_whisper():
    """Lazy singleton — heavy import deferred until first transcription."""
    from faster_whisper import WhisperModel  # noqa: PLC0415

    logger.info(
        "loading_whisper",
        model_size=settings.WHISPER_MODEL_SIZE,
        device=settings.WHISPER_DEVICE,
        compute_type=settings.WHISPER_COMPUTE_TYPE,
    )
    return WhisperModel(
        settings.WHISPER_MODEL_SIZE,
        device=settings.WHISPER_DEVICE,
        compute_type=settings.WHISPER_COMPUTE_TYPE,
    )


class Transcriber:
    async def transcribe(self, audio_path: Path, language: str | None = None) -> TranscriptionResult:
        logger.info("transcribe_start", audio=str(audio_path))

        def _run() -> TranscriptionResult:
            model = _get_whisper()
            segments, info = model.transcribe(
                str(audio_path),
                language=language,
                vad_filter=True,           # drop silences
                vad_parameters={"min_silence_duration_ms": 500},
                beam_size=5,
                condition_on_previous_text=False,
            )
            collected: list[TranscriptSegment] = []
            text_parts: list[str] = []
            for s in segments:
                collected.append(TranscriptSegment(start=s.start, end=s.end, text=s.text.strip()))
                text_parts.append(s.text.strip())
            return TranscriptionResult(
                text=" ".join(text_parts),
                language=info.language,
                segments=collected,
                duration=info.duration,
            )

        result = await asyncio.to_thread(_run)
        logger.info(
            "transcribe_done",
            language=result.language,
            duration=result.duration,
            segments=len(result.segments),
        )
        return result
