"""File helpers — async-safe writes, MIME validation, path generation."""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import BinaryIO

import aiofiles
from fastapi import UploadFile

from app.core.config import settings
from app.core.exceptions import ValidationError

ALLOWED_VIDEO_TYPES = {
    "video/mp4",
    "video/quicktime",
    "video/x-matroska",
    "video/webm",
    "video/avi",
    "video/x-msvideo",
}


def validate_video(upload: UploadFile) -> None:
    if upload.content_type not in ALLOWED_VIDEO_TYPES:
        raise ValidationError(
            f"Unsupported video type: {upload.content_type}",
            details={"allowed": sorted(ALLOWED_VIDEO_TYPES)},
        )


def build_storage_path(user_id: str, original_name: str) -> Path:
    """`<UPLOAD_DIR>/<user_id>/<uuid>__<sanitized>.<ext>`"""
    safe = "".join(c for c in original_name if c.isalnum() or c in "._-")[-80:]
    folder = settings.UPLOAD_DIR / str(user_id)
    folder.mkdir(parents=True, exist_ok=True)
    return folder / f"{uuid.uuid4().hex}__{safe}"


async def save_upload(upload: UploadFile, dest: Path) -> int:
    """Stream upload to disk; return total bytes."""
    total = 0
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    async with aiofiles.open(dest, "wb") as out:
        while chunk := await upload.read(1024 * 1024):
            total += len(chunk)
            if total > max_bytes:
                await out.close()
                dest.unlink(missing_ok=True)
                raise ValidationError(
                    f"File exceeds {settings.MAX_UPLOAD_SIZE_MB}MB limit"
                )
            await out.write(chunk)
    return total
