from __future__ import annotations

from app.core.config import settings


class ObjectStorageClient:
    def __init__(self) -> None:
        self._client = None
        try:
            import boto3

            self._client = boto3.client(
                "s3",
                endpoint_url=settings.rustfs_url,
                aws_access_key_id=settings.rustfs_access_key_id,
                aws_secret_access_key=settings.rustfs_secret_access_key,
            )
        except Exception:
            self._client = None

    def available(self) -> bool:
        return self._client is not None

    def put_bytes(self, bucket: str, key: str, content: bytes, content_type: str = "application/octet-stream") -> str | None:
        if self._client is None:
            return None
        try:
            self._client.put_object(Bucket=bucket, Key=key, Body=content, ContentType=content_type)
            return f"{settings.rustfs_url.rstrip('/')}/{bucket}/{key}"
        except Exception:
            return None


object_storage = ObjectStorageClient()
