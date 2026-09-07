from fastapi import APIRouter, Depends, Response, status

from app.api.dependencies import get_current_user, get_department_scope
from app.core.database import get_mongo_database
from app.core.time import BusinessClock
from app.infrastructure.evidence_storage import create_evidence_storage
from app.infrastructure.malware_scanner import create_malware_scanner
from app.models.attachment import (
    CompleteUploadSessionResponse,
    CreateUploadSessionRequest,
    UploadSessionResponse,
)
from app.models.user import CurrentUser
from app.repositories.attachment_upload_repository import AttachmentUploadRepository
from app.services.attachment_upload_service import AttachmentUploadService

router = APIRouter(prefix="/api/attachments", tags=["Attachments"])


def get_attachment_upload_service() -> AttachmentUploadService:
    return AttachmentUploadService(
        AttachmentUploadRepository(get_mongo_database().get_database()),
        create_evidence_storage(),
        clock=BusinessClock(),
        scanner=create_malware_scanner(),
    )


@router.post(
    "/upload-sessions",
    response_model=UploadSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Tạo phiên tải tệp trực tiếp",
)
async def create_upload_session(
    request: CreateUploadSessionRequest,
    scope=Depends(get_department_scope),
    current_user: CurrentUser = Depends(get_current_user),
    service: AttachmentUploadService = Depends(get_attachment_upload_service),
) -> UploadSessionResponse:
    return await service.create(request, current_user, scope)


@router.post(
    "/upload-sessions/{session_id}/complete",
    response_model=CompleteUploadSessionResponse,
    summary="Xác nhận tệp đã tải lên",
)
async def complete_upload_session(
    session_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    service: AttachmentUploadService = Depends(get_attachment_upload_service),
) -> CompleteUploadSessionResponse:
    return await service.complete(session_id, current_user)


@router.delete(
    "/upload-sessions/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Hủy phiên tải tệp",
)
async def cancel_upload_session(
    session_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    service: AttachmentUploadService = Depends(get_attachment_upload_service),
) -> Response:
    await service.cancel(session_id, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


__all__ = ["router"]
