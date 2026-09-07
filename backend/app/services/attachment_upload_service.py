from __future__ import annotations

import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import ClassVar
from uuid import uuid4

from bson import ObjectId
from fastapi import HTTPException, status

from app.core.config import Settings, get_settings
from app.core.time import BusinessClock
from app.infrastructure.evidence_storage import EvidenceStorage
from app.infrastructure.malware_scanner import MalwareScanner, ScanResult, create_malware_scanner
from app.models.attachment import (
    AttachmentPurpose,
    CompleteUploadSessionResponse,
    CreateUploadSessionRequest,
    UploadSessionDocument,
    UploadSessionResponse,
    UploadSessionStatus,
)
from app.models.user import CurrentUser, UserRole
from app.repositories.attachment_upload_repository import AttachmentUploadRepository
from app.services.department_service import parse_object_id


class AttachmentUploadService:
    """Coordinates temporary browser uploads without exposing storage keys.

    Upload sessions do not emit a Change Stream: the owner always receives
    create/complete/cancel state through the direct response, so no lifecycle
    event is needed for other clients.
    """

    _ALLOWED_EXTENSIONS: ClassVar[set[str]] = {
        ".pdf",
        ".doc",
        ".docx",
        ".xls",
        ".xlsx",
        ".ppt",
        ".pptx",
        ".txt",
        ".png",
        ".jpg",
        ".jpeg",
    }
    _MIME_BY_EXTENSION: ClassVar[dict[str, set[str]]] = {
        ".pdf": {"application/pdf"},
        ".doc": {"application/msword"},
        ".docx": {"application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
        ".xls": {"application/vnd.ms-excel"},
        ".xlsx": {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
        ".ppt": {"application/vnd.ms-powerpoint"},
        ".pptx": {"application/vnd.openxmlformats-officedocument.presentationml.presentation"},
        ".txt": {"text/plain"},
        ".png": {"image/png"},
        ".jpg": {"image/jpeg"},
        ".jpeg": {"image/jpeg"},
    }

    def __init__(
        self,
        repository: AttachmentUploadRepository,
        storage: EvidenceStorage,
        settings: Settings | None = None,
        clock: BusinessClock | None = None,
        scanner: MalwareScanner | None = None,
    ) -> None:
        self.repository = repository
        self.storage = storage
        self.settings = settings or get_settings()
        self._clock = clock or BusinessClock()
        self.scanner = scanner or create_malware_scanner(self.settings)

    async def create(
        self,
        request: CreateUploadSessionRequest,
        current_user: CurrentUser,
        scope: ObjectId | None,
    ) -> UploadSessionResponse:
        if not self.settings.storage_direct_upload_enabled:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Tải trực tiếp chưa được bật, vui lòng dùng biểu mẫu tải tệp thông thường",
            )
        file_name = self._validate_file(request)
        department_id = parse_object_id(request.department_id, "Mã phòng ban")
        await self._validate_context(request, current_user, scope, department_id)
        await self.repository.ensure_indexes()
        now = self._now()
        session_id = str(uuid4())
        storage_key = self._storage_key(request, department_id, session_id, file_name)
        expires_at = now + timedelta(seconds=self.settings.storage_upload_session_ttl)
        try:
            await self.storage.ensure_browser_upload_config()
            upload_url = await self.storage.create_upload_url(
                storage_key,
                request.content_type,
                request.checksum.lower(),
                self.settings.storage_upload_url_ttl,
            )
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Không thể tạo liên kết tải tệp, vui lòng kiểm tra kho lưu trữ",
            ) from exc
        if not upload_url:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Kho lưu trữ chưa sẵn sàng để tải trực tiếp",
            )
        document = {
            "_id": session_id,
            "owner_id": current_user.user_id,
            "department_id": str(department_id),
            "purpose": request.purpose.value,
            "target_id": request.target_id,
            "week_start": request.week_start,
            "task_id": request.task_id,
            "work_date": request.work_date,
            "file_name": file_name,
            "content_type": request.content_type,
            "file_size": request.file_size,
            "checksum": request.checksum.lower(),
            "generated_storage_key": storage_key,
            "status": UploadSessionStatus.PENDING.value,
            "expires_at": expires_at,
            "created_at": now,
            "updated_at": now,
        }
        try:
            await self.repository.insert(document)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Không thể khởi tạo phiên tải tệp, vui lòng thử lại",
            ) from exc
        return UploadSessionResponse(
            id=session_id,
            upload_url=upload_url,
            expires_at=now + timedelta(seconds=self.settings.storage_upload_url_ttl),
            required_headers={
                "Content-Type": request.content_type,
                "x-amz-meta-sha256": request.checksum.lower(),
            },
        )

    async def complete(
        self, session_id: str, current_user: CurrentUser
    ) -> CompleteUploadSessionResponse:
        session = await self._owned_session(session_id, current_user.user_id)
        now = self._now()
        if session.status == UploadSessionStatus.COMMITTED:
            raise HTTPException(status_code=409, detail="Phiên tải tệp đã được xác nhận")
        if session.status in {
            UploadSessionStatus.EXPIRED,
            UploadSessionStatus.FAILED,
            UploadSessionStatus.CANCELLED,
        }:
            raise HTTPException(status_code=409, detail="Phiên tải tệp không còn hiệu lực")
        if now >= session.expires_at:
            await self.repository.update_status(session.id, UploadSessionStatus.EXPIRED.value, now)
            raise HTTPException(status_code=409, detail="Phiên tải tệp đã hết hạn")
        try:
            metadata = await self.storage.head_object(session.generated_storage_key)
        except Exception as exc:
            raise HTTPException(
                status_code=503,
                detail="Không thể kiểm tra tệp trong kho lưu trữ",
            ) from exc
        if not metadata or not self._matches(session, metadata):
            await self._fail_session(session, now)
            raise HTTPException(
                status_code=422,
                detail="Tệp tải lên không khớp kích thước, loại nội dung hoặc mã kiểm tra",
            )
        try:
            content = await self.storage.read_bytes(session.generated_storage_key)
            if (
                content is None
                or len(content) != session.file_size
                or hashlib.sha256(content).hexdigest().lower() != session.checksum.lower()
            ):
                await self._fail_session(session, now)
                raise HTTPException(status_code=422, detail="Mã kiểm tra tệp không khớp")
            scan_result: ScanResult = await self.scanner.scan(content)
            if not scan_result.clean:
                await self._fail_session(session, now)
                raise HTTPException(status_code=422, detail="Tệp không vượt qua kiểm tra an toàn")
        except HTTPException:
            raise
        except Exception as exc:
            await self._fail_session(session, now)
            raise HTTPException(
                status_code=503,
                detail="Không thể xác minh an toàn tệp tải lên",
            ) from exc
        await self.repository.update_status(session.id, UploadSessionStatus.UPLOADED.value, now)
        return CompleteUploadSessionResponse(
            id=session.id,
            status=UploadSessionStatus.UPLOADED,
            file_name=session.file_name,
            content_type=session.content_type,
            file_size=session.file_size,
        )

    async def cancel(self, session_id: str, current_user: CurrentUser) -> None:
        session = await self._owned_session(session_id, current_user.user_id)
        if session.status == UploadSessionStatus.COMMITTED:
            raise HTTPException(status_code=409, detail="Không thể hủy phiên đã được lưu")
        try:
            await self.storage.delete(session.generated_storage_key)
        except Exception:
            pass
        await self.repository.update_status(
            session.id, UploadSessionStatus.CANCELLED.value, self._now()
        )

    async def resolve_for_department_evaluation(
        self,
        session_ids: list[str],
        owner_id: str,
        department_id: ObjectId,
        week_start,
    ) -> list[dict[str, object]]:
        if (
            not session_ids
            or len(session_ids) != len(set(session_ids))
            or len(session_ids) > self.settings.storage_max_files_per_evaluation
        ):
            raise HTTPException(status_code=422, detail="Số lượng tệp đính kèm không hợp lệ")
        sessions = await self.repository.find_uploaded_for_owner(session_ids, owner_id)
        if len(sessions) != len(set(session_ids)):
            raise HTTPException(status_code=422, detail="Có phiên tải tệp chưa được xác minh")
        for session in sessions:
            if (
                session.purpose != AttachmentPurpose.DEPARTMENT_EVALUATION
                or session.department_id != str(department_id)
                or session.week_start != week_start
            ):
                raise HTTPException(status_code=403, detail="Tệp không thuộc kỳ đánh giá này")
        return [
            {
                "attachment_id": session.id,
                "storage_key": session.generated_storage_key,
                "file_name": session.file_name,
                "content_type": session.content_type,
                "file_size": session.file_size,
                "checksum": session.checksum,
            }
            for session in sessions
        ]

    async def commit(self, session_ids: list[str]) -> None:
        await self.repository.mark_committed(session_ids, self._now())

    async def fail(self, session_ids: list[str]) -> None:
        await self.repository.mark_failed(session_ids, self._now())

    async def discard(self, session_ids: list[str], owner_id: str) -> None:
        sessions = await self.repository.find_for_owner(session_ids, owner_id)
        for session in sessions:
            if session.status != UploadSessionStatus.COMMITTED:
                try:
                    await self.storage.delete(session.generated_storage_key)
                except Exception:
                    pass
        await self.repository.mark_failed(session_ids, self._now())

    async def _owned_session(self, session_id: str, owner_id: str) -> UploadSessionDocument:
        session = await self.repository.find_by_id(session_id)
        if session is None or session.owner_id != owner_id:
            raise HTTPException(status_code=404, detail="Không tìm thấy phiên tải tệp")
        return session

    async def _fail_session(self, session: UploadSessionDocument, now: datetime) -> None:
        try:
            await self.storage.delete(session.generated_storage_key)
        except Exception:
            pass
        finally:
            await self.repository.update_status(session.id, UploadSessionStatus.FAILED.value, now)

    def _validate_file(self, request: CreateUploadSessionRequest) -> str:
        file_name = Path(request.file_name).name
        extension = Path(file_name).suffix.lower()
        if file_name != request.file_name or extension not in self._ALLOWED_EXTENSIONS:
            raise HTTPException(status_code=422, detail="Tên hoặc định dạng tệp không được hỗ trợ")
        if request.content_type not in self._MIME_BY_EXTENSION[extension]:
            raise HTTPException(status_code=422, detail="Loại nội dung tệp không khớp định dạng")
        if request.file_size > self.settings.storage_max_file_size:
            raise HTTPException(status_code=422, detail="Kích thước tệp vượt quá giới hạn cho phép")
        return file_name

    async def _validate_context(
        self, request, current_user, scope, department_id: ObjectId
    ) -> None:
        if not await self.repository.department_is_active(department_id):
            raise HTTPException(status_code=404, detail="Phòng ban không tồn tại hoặc đã ngừng hoạt động")
        if request.purpose == AttachmentPurpose.DEPARTMENT_EVALUATION:
            if current_user.role != UserRole.LEADERSHIP or scope is not None:
                raise HTTPException(status_code=403, detail="Chỉ Lãnh đạo được tải tài liệu đánh giá phòng ban")
            if request.week_start is None or request.target_id or request.task_id or request.work_date:
                raise HTTPException(status_code=422, detail="Ngữ cảnh đánh giá phòng ban không hợp lệ")
            return
        if current_user.role != UserRole.MANAGER or scope != department_id:
            raise HTTPException(status_code=403, detail="Không có quyền tải minh chứng công việc này")
        if not request.task_id or request.work_date is None:
            raise HTTPException(status_code=422, detail="Minh chứng công việc thiếu ngữ cảnh")
        if request.target_id and request.target_id != request.task_id:
            raise HTTPException(status_code=422, detail="Mã đối tượng minh chứng không khớp công việc")
        task_id = parse_object_id(request.task_id, "Mã công việc")
        if not await self.repository.task_belongs_to_department(task_id, department_id):
            raise HTTPException(status_code=403, detail="Công việc không thuộc phòng ban của bạn")

    @staticmethod
    def _storage_key(request, department_id: ObjectId, session_id: str, file_name: str) -> str:
        extension = Path(file_name).suffix.lower()
        if request.purpose == AttachmentPurpose.DEPARTMENT_EVALUATION:
            return f"department-evaluations/{department_id}/{request.week_start}/{session_id}{extension}"
        return f"task-execution/{department_id}/{request.task_id}/{request.work_date}/{session_id}{extension}"

    @staticmethod
    def _matches(session: UploadSessionDocument, metadata: dict[str, object]) -> bool:
        raw_size = metadata.get("size")
        if isinstance(raw_size, int):
            size = raw_size
        elif isinstance(raw_size, (str, bytes, bytearray)):
            size = int(raw_size or 0)
        else:
            size = 0
        return (
            size == session.file_size
            and str(metadata.get("content_type") or "") == session.content_type
            and str(metadata.get("checksum") or "").lower() == session.checksum.lower()
        )

    def _now(self) -> datetime:
        return self._clock.now()


__all__ = ["AttachmentUploadService"]
