"""Audio extraction from video via FFmpeg.

We always output mono 16kHz WAV — that's what every modern STT system expects
and avoids any sample-rate mismatch errors inside Whisper.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

import ffmpeg  # ffmpeg-python wrapper

from app.core.exceptions import ExternalServiceError
from app.core.logging import get_logger

logger = get_logger(__name__)


class AudioExtractor:
    SAMPLE_RATE = 16_000
    CHANNELS = 1

    async def extract(self, video_path: Path, out_path: Path | None = None) -> Path:
        out_path = out_path or video_path.with_suffix(".wav")
        logger.info("audio_extract_start", video=str(video_path), out=str(out_path))

        def _run() -> None:
            try:
                (
                    ffmpeg.input(str(video_path))
                    .output(
                        str(out_path),
                        ac=self.CHANNELS,
                        ar=self.SAMPLE_RATE,
                        acodec="pcm_s16le",
                        loglevel="error",
                    )
                    .overwrite_output()
                    .run(capture_stdout=True, capture_stderr=True)
                )
            except ffmpeg.Error as e:
                stderr = e.stderr.decode("utf-8", errors="ignore") if e.stderr else ""
                raise ExternalServiceError(f"FFmpeg failed: {stderr[:500]}") from e

        # Run in thread pool — FFmpeg call is blocking C code.
        await asyncio.to_thread(_run)
        logger.info("audio_extract_done", out=str(out_path), size=out_path.stat().st_size)
        return out_path

    async def get_duration(self, video_path: Path) -> float:
        def _probe() -> float:
            try:
                info = ffmpeg.probe(str(video_path))
                return float(info["format"]["duration"])
            except Exception as e:  # noqa: BLE001
                logger.warning("probe_failed", error=str(e))
                return 0.0

        return await asyncio.to_thread(_probe)
