"""Video ingestion service — orchestrates the full pipeline.

Optimizations vs v1:
  * Bulk insert of chunks (one COPY-style insert vs N inserts).
  * Embeddings are batched and content-hash-cached before hitting the model.
  * Vector store writes are batched; persist() is called once at the end.
  * Status updates use `UPDATE ... WHERE id = ?` (no SELECT first).
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.embeddings.embedder import get_embedder
from app.models.video import Video, VideoChunk, VideoStatus
from app.monitoring.metrics import VIDEO_PROCESSING
from app.rag.audio import AudioExtractor
from app.rag.chunking import RecursiveChunker
from app.rag.transcription import Transcriber
from app.rag.vector_store import get_vector_store
from app.repositories.video_repository import VideoChunkRepository, VideoRepository
from app.storage.factory import get_storage

logger = get_logger(__name__)


class VideoService:
    def __init__(
        self,
        videos: VideoRepository,
        chunks: VideoChunkRepository,
    ) -> None:
        self.videos = videos
        self.chunks = chunks
        self.storage = get_storage()
        self.audio = AudioExtractor()
        self.transcriber = Transcriber()
        self.chunker = RecursiveChunker()
        self.embedder = get_embedder()
        self.vector_store = get_vector_store()

    async def get(self, video_id: uuid.UUID, owner_id: uuid.UUID) -> Video:
        v = await self.videos.get_owned(video_id, owner_id)
        if not v:
            raise NotFoundError(message="Video not found")
        return v

    async def list_for_user(self, owner_id: uuid.UUID) -> list[Video]:
        return await self.videos.list_for_owner(owner_id)

    async def create(
        self,
        *,
        owner_id: uuid.UUID,
        title: str,
        description: str | None,
        filename: str,
        storage_path: str,
        mime_type: str,
        size_bytes: int,
    ) -> Video:
        v = Video(
            owner_id=owner_id,
            title=title,
            description=description,
            filename=filename,
            storage_path=storage_path,
            mime_type=mime_type,
            file_size_bytes=size_bytes,
            status=VideoStatus.UPLOADED,
        )
        self.videos.add(v)
        await self.videos.flush()
        return v

    async def soft_delete(self, video_id: uuid.UUID, owner_id: uuid.UUID) -> None:
        v = await self.get(video_id, owner_id)
        try:
            chunk_ids = await self.chunks.get_chunk_ids_for_video(v.id)
            if chunk_ids:
                self.vector_store.delete([str(c) for c in chunk_ids])
                self.vector_store.persist()
        except Exception as e:  # noqa: BLE001
            logger.warning("vector_delete_failed", error=str(e))

        await self.videos.soft_delete(v.id)
        try:
            await self.storage.delete(v.storage_path)
        except Exception as e:  # noqa: BLE001
            logger.warning("file_delete_failed", error=str(e))

    # ---- ingestion pipeline -------------------------------------------
    async def process_video(self, video_id: uuid.UUID) -> None:
        v = await self.videos.get(video_id)
        if not v:
            raise NotFoundError(message="Video not found")
        try:
            # 1. Audio + duration in parallel
            await self.videos.mark_status(v.id, VideoStatus.EXTRACTING_AUDIO)
            await self.videos.flush()
            local_video = await self.storage.get_local_path(v.storage_path)
            audio_task = asyncio.create_task(self.audio.extract(Path(local_video)))
            duration_task = asyncio.create_task(self.audio.get_duration(Path(local_video)))
            audio_path, duration = await asyncio.gather(audio_task, duration_task)
            v.duration_seconds = duration

            # 2. Transcription
            await self.videos.mark_status(v.id, VideoStatus.TRANSCRIBING)
            await self.videos.flush()
            transcript = await self.transcriber.transcribe(audio_path)
            v.transcript = transcript.text
            v.language = transcript.language

            # 3. Chunking
            await self.videos.mark_status(v.id, VideoStatus.CHUNKING)
            await self.videos.flush()
            chunks = self.chunker.chunk(transcript.segments)
            if not chunks:
                raise RuntimeError("No chunks produced from transcript")

            # 4. Wipe stale chunks (idempotent re-run)
            await self.chunks.delete_for_video(v.id)

            # 5. Embedding (single batched call)
            await self.videos.mark_status(v.id, VideoStatus.EMBEDDING)
            await self.videos.flush()
            texts = [c.text for c in chunks]
            vectors = self.embedder.embed_batch(texts)

            # 6. Persist chunks + index vectors
            await self.videos.mark_status(v.id, VideoStatus.INDEXING)
            await self.videos.flush()
            chunk_rows = [
                VideoChunk(
                    video_id=v.id,
                    chunk_index=c.index,
                    text=c.text,
                    start_time=c.start_time,
                    end_time=c.end_time,
                    token_count=c.token_count,
                )
                for c in chunks
            ]
            await self.chunks.bulk_insert(chunk_rows)
            for r in chunk_rows:
                r.vector_id = str(r.id)
            ids = [str(r.id) for r in chunk_rows]
            metadatas = [
                {
                    "video_id": str(v.id),
                    "user_id": str(v.owner_id),
                    "chunk_index": r.chunk_index,
                    "start_time": r.start_time,
                    "end_time": r.end_time,
                }
                for r in chunk_rows
            ]
            self.vector_store.add(ids, vectors, metadatas)
            self.vector_store.persist()

            # 7. Done
            await self.videos.mark_status(
                v.id, VideoStatus.READY, error=None, processed_at=datetime.now(timezone.utc)
            )
            VIDEO_PROCESSING.labels(status="ready").inc()
            logger.info("video_ready", video=str(v.id), chunks=len(chunk_rows))

        except Exception as e:  # noqa: BLE001
            VIDEO_PROCESSING.labels(status="failed").inc()
            await self.videos.mark_status(v.id, VideoStatus.FAILED, error=str(e))
            logger.exception("video_processing_failed", video=str(v.id))
            raise
