"""S3 storage backend (optional). Active only when STORAGE_BACKEND=s3.

Kept minimal — pulls object to a temp file when `get_local_path` is called,
since FFmpeg / Whisper need real paths. Production: replace with streaming.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

from app.core.config import settings
from app.storage.base import StorageBackend


class S3Storage(StorageBackend):
    def __init__(self) -> None:
        self.bucket = settings.S3_BUCKET
        self.client = boto3.client(
            "s3",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION,
        )

    async def exists(self, key: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError:
            return False

    async def get_local_path(self, key: str) -> Path:
        tmp = Path(tempfile.gettempdir()) / f"s3_{Path(key).name}"
        self.client.download_file(self.bucket, key, str(tmp))
        return tmp

    async def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=key)

    def public_url(self, key: str) -> str | None:
        return f"https://{self.bucket}.s3.{settings.AWS_REGION}.amazonaws.com/{key}"
