import asyncio
from collections.abc import Mapping
from typing import Protocol
from urllib.parse import urlparse

from app.core.config import get_settings


class EvidenceStorage(Protocol):
    async def ensure_browser_upload_config(self) -> None: ...

    async def create_upload_url(
        self,
        storage_key: str,
        content_type: str,
        checksum: str,
        expires_in: int,
    ) -> str | None: ...

    async def head_object(self, storage_key: str) -> dict[str, object] | None: ...

    async def read_bytes(self, storage_key: str) -> bytes | None: ...

    async def signed_url(self, storage_key: str) -> str | None: ...

    async def upload_bytes(
        self, storage_key: str, content: bytes, content_type: str, checksum: str
    ) -> None: ...

    async def delete(self, storage_key: str) -> None: ...

    async def list_objects(self, prefix: str | None = None) -> list[dict[str, object]]: ...


class DisabledEvidenceStorage:
    """Storage rỗng cho môi trường chưa cấu hình MinIO/S3."""

    async def ensure_browser_upload_config(self) -> None:
        return None

    async def create_upload_url(
        self, storage_key: str, content_type: str, checksum: str, expires_in: int
    ) -> str | None:
        return None

    async def head_object(self, storage_key: str) -> dict[str, object] | None:
        return None

    async def read_bytes(self, storage_key: str) -> bytes | None:
        return None

    async def signed_url(self, storage_key: str) -> str | None:
        return None

    async def upload_bytes(
        self, storage_key: str, content: bytes, content_type: str, checksum: str
    ) -> None:
        raise RuntimeError("Kho lưu trữ tài liệu định hướng chưa được cấu hình")

    async def delete(self, storage_key: str) -> None:
        return None

    async def list_objects(self, prefix: str | None = None) -> list[dict[str, object]]:
        return []


class S3EvidenceStorage:
    def __init__(self, settings=None) -> None:
        self.settings = settings or get_settings()

    async def ensure_browser_upload_config(self) -> None:
        await asyncio.to_thread(self._ensure_browser_upload_config)

    async def create_upload_url(
        self,
        storage_key: str,
        content_type: str,
        checksum: str,
        expires_in: int,
    ) -> str | None:
        return await asyncio.to_thread(
            self._create_upload_url, storage_key, content_type, checksum, expires_in
        )

    async def head_object(self, storage_key: str) -> dict[str, object] | None:
        return await asyncio.to_thread(self._head_object, storage_key)

    async def read_bytes(self, storage_key: str) -> bytes | None:
        return await asyncio.to_thread(self._read_bytes, storage_key)

    async def signed_url(self, storage_key: str) -> str | None:
        return await asyncio.to_thread(self._create_signed_url, storage_key)

    async def upload_bytes(
        self, storage_key: str, content: bytes, content_type: str, checksum: str
    ) -> None:
        await asyncio.to_thread(
            self._upload_bytes, storage_key, content, content_type, checksum
        )

    async def delete(self, storage_key: str) -> None:
        await asyncio.to_thread(
            self._client(self._internal_endpoint()).delete_object,
            Bucket=self.settings.storage_bucket,
            Key=storage_key,
        )

    async def list_objects(self, prefix: str | None = None) -> list[dict[str, object]]:
        return await asyncio.to_thread(self._list_objects, prefix)

    def _client(self, endpoint_url: str | None = None):
        try:
            import boto3
        except ImportError as exc:
            raise RuntimeError("Chưa cài thư viện lưu trữ minh chứng") from exc
        return boto3.client(
            "s3",
            endpoint_url=endpoint_url or self._internal_endpoint() or None,
            region_name=self.settings.storage_region,
            aws_access_key_id=self.settings.storage_access_key or None,
            aws_secret_access_key=self.settings.storage_secret_key or None,
        )

    def _upload_bytes(
        self, storage_key: str, content: bytes, content_type: str, checksum: str
    ) -> None:
        client = self._client(self._internal_endpoint())
        self._ensure_bucket(client)
        client.put_object(
            Bucket=self.settings.storage_bucket,
            Key=storage_key,
            Body=content,
            ContentType=content_type,
            Metadata={"sha256": checksum},
        )

    def _create_signed_url(self, storage_key: str) -> str:
        return self._client(self._public_endpoint()).generate_presigned_url(
            "get_object",
            Params={"Bucket": self.settings.storage_bucket, "Key": storage_key},
            ExpiresIn=self.settings.storage_signed_url_ttl,
        )

    def _create_upload_url(
        self, storage_key: str, content_type: str, checksum: str, expires_in: int
    ) -> str:
        client = self._client(self._public_endpoint())
        return client.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": self.settings.storage_bucket,
                "Key": storage_key,
                "ContentType": content_type,
                "Metadata": {"sha256": checksum},
            },
            ExpiresIn=expires_in,
        )

    def _ensure_browser_upload_config(self) -> None:
        client = self._client(self._internal_endpoint())
        self._ensure_bucket(client)
        origins = [
            origin.strip()
            for origin in self.settings.storage_public_cors_origins.split(",")
            if origin.strip()
        ]
        client.put_bucket_cors(
            Bucket=self.settings.storage_bucket,
            CORSConfiguration={
                "CORSRules": [
                    {
                        "AllowedOrigins": origins,
                        "AllowedMethods": ["PUT", "HEAD"],
                        "AllowedHeaders": ["Content-Type", "x-amz-meta-sha256"],
                        "ExposeHeaders": ["ETag", "x-amz-meta-sha256"],
                        "MaxAgeSeconds": 600,
                    }
                ]
            },
        )

    def _ensure_bucket(self, client) -> None:
        try:
            client.head_bucket(Bucket=self.settings.storage_bucket)
        except Exception as exc:
            response = getattr(exc, "response", {})
            code = str(response.get("Error", {}).get("Code", ""))
            if code not in {"404", "NoSuchBucket", "NotFound"}:
                raise
            client.create_bucket(Bucket=self.settings.storage_bucket)

    def _head_object(self, storage_key: str) -> dict[str, object] | None:
        try:
            response = self._client(self._internal_endpoint()).head_object(
                Bucket=self.settings.storage_bucket,
                Key=storage_key,
            )
        except Exception as exc:
            response = getattr(exc, "response", {})
            code = str(response.get("Error", {}).get("Code", ""))
            if code in {"404", "NoSuchKey", "NotFound"}:
                return None
            raise
        return {
            "size": response.get("ContentLength", 0),
            "content_type": response.get("ContentType", ""),
            "checksum": (response.get("Metadata") or {}).get("sha256", ""),
        }

    def _read_bytes(self, storage_key: str) -> bytes | None:
        try:
            response = self._client(self._internal_endpoint()).get_object(
                Bucket=self.settings.storage_bucket,
                Key=storage_key,
            )
        except Exception as exc:
            response = getattr(exc, "response", {})
            code = str(response.get("Error", {}).get("Code", ""))
            if code in {"404", "NoSuchKey", "NotFound"}:
                return None
            raise
        return response["Body"].read(self.settings.storage_max_file_size + 1)

    def _list_objects(self, prefix: str | None = None) -> list[dict[str, object]]:
        client = self._client(self._internal_endpoint())
        paginator = client.get_paginator("list_objects_v2")
        objects: list[dict[str, object]] = []
        for page in paginator.paginate(Bucket=self.settings.storage_bucket, Prefix=prefix or ""):
            objects.extend(
                {
                    "key": item.get("Key"),
                    "last_modified": item.get("LastModified"),
                    "size": item.get("Size", 0),
                }
                for item in page.get("Contents", [])
            )
        return objects

    def _internal_endpoint(self) -> str:
        return (
            self.settings.storage_internal_endpoint_url
            or self.settings.storage_endpoint_url
        )

    def _public_endpoint(self) -> str:
        return self.settings.storage_public_endpoint_url or self._internal_endpoint()


def create_evidence_storage(settings=None) -> EvidenceStorage:
    settings = settings or get_settings()
    if not settings.storage_bucket:
        return DisabledEvidenceStorage()
    if settings.environment.lower() == "production":
        endpoint = settings.storage_public_endpoint_url or settings.storage_endpoint_url
        parsed = urlparse(endpoint)
        if parsed.scheme != "https" or parsed.hostname in {"localhost", "127.0.0.1", "::1"}:
            raise RuntimeError(
                "Kho lưu trữ production phải sử dụng endpoint public HTTPS, không dùng localhost"
            )
    return S3EvidenceStorage(settings)


def validate_attachment_metadata(attachment: Mapping[str, object], settings=None) -> None:
    settings = settings or get_settings()
    content_type = str(attachment.get("content_type") or "")
    raw_file_size = attachment.get("file_size")
    if isinstance(raw_file_size, int):
        file_size = raw_file_size
    elif isinstance(raw_file_size, (str, bytes, bytearray)):
        file_size = int(raw_file_size or 0)
    else:
        file_size = 0
    if content_type not in settings.storage_allowed_content_types:
        raise ValueError("Loại tệp minh chứng không được hỗ trợ")
    if file_size <= 0 or file_size > settings.storage_max_file_size:
        raise ValueError("Kích thước tệp minh chứng không hợp lệ")
    if not attachment.get("storage_key") or not attachment.get("checksum"):
        raise ValueError("Minh chứng thiếu thông tin lưu trữ hoặc mã kiểm tra")


__all__ = ["EvidenceStorage", "create_evidence_storage", "validate_attachment_metadata"]
