from fastapi import APIRouter, Depends, Response, status

from app.api.dependencies import get_current_user, get_department_scope
from app.core.database import get_mongo_database
from app.core.time import BusinessClock
from app.infrastructure.evidence_storage import create_evidence_storage
from app.infrastructure.idempotency import IdempotencyContext, complete_idempotency, idempotent
from app.infrastructure.malware_scanner import create_malware_scanner
from app.infrastructure.rate_limit import rate_limit_group
from app.models.attachment import (
    CompleteUploadSessionResponse,
    CreateUploadSessionRequest,
    UploadSessionResponse,
)
from app.models.user import CurrentUser
from app.repositories.attachment_upload_repository import AttachmentUploadRepository
from app.services.attachment_upload_service import AttachmentUploadService

router = APIRouter(prefix="/attachments", tags=["Attachments"])


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
    dependencies=[Depends(rate_limit_group("upload_session"))],
)
async def create_upload_session(
    request: CreateUploadSessionRequest,
    scope=Depends(get_department_scope),
    current_user: CurrentUser = Depends(get_current_user),
    service: AttachmentUploadService = Depends(get_attachment_upload_service),
    idempotency: IdempotencyContext | None = Depends(idempotent("upload_session")),
) -> UploadSessionResponse:
    result = await service.create(request, current_user, scope)
    await complete_idempotency(idempotency, result, status_code=201)
    return result


@router.post(
    "/upload-sessions/{session_id}/complete",
    response_model=CompleteUploadSessionResponse,
    summary="Deprecated: xác nhận tệp đã tải lên",
    deprecated=True,
    name="complete_upload_session_legacy",
    dependencies=[Depends(rate_limit_group("upload_completion"))],
)
@router.patch(
    "/upload-sessions/{session_id}",
    response_model=CompleteUploadSessionResponse,
    summary="Xác nhận tệp đã tải lên",
    name="complete_upload_session_v1",
    dependencies=[Depends(rate_limit_group("upload_completion"))],
)
async def complete_upload_session(
    session_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    service: AttachmentUploadService = Depends(get_attachment_upload_service),
    idempotency: IdempotencyContext | None = Depends(idempotent("upload_completion")),
) -> CompleteUploadSessionResponse:
    result = await service.complete(session_id, current_user)
    await complete_idempotency(idempotency, result)
    return result


@router.delete(
    "/upload-sessions/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Hủy phiên tải tệp",
    dependencies=[Depends(rate_limit_group("upload_completion"))],
)
async def cancel_upload_session(
    session_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    service: AttachmentUploadService = Depends(get_attachment_upload_service),
) -> Response:
    await service.cancel(session_id, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


__all__ = ["router"]
