"""Upload-session resources exposed directly under the v1 API root."""

from fastapi import APIRouter, Depends, Response, status

from app.api.attachments import get_attachment_upload_service
from app.api.dependencies import get_current_user, get_department_scope
from app.infrastructure.idempotency import IdempotencyContext, complete_idempotency, idempotent
from app.infrastructure.rate_limit import rate_limit_group
from app.models.attachment import (
    CompleteUploadSessionResponse,
    CreateUploadSessionRequest,
    UploadSessionResponse,
)
from app.models.user import CurrentUser
from app.services.attachment_upload_service import AttachmentUploadService

router = APIRouter(tags=["Attachments v1"])


@router.post(
    "/upload-sessions",
    response_model=UploadSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Tạo phiên tải tệp trực tiếp phiên bản v1",
    dependencies=[Depends(rate_limit_group("upload_session"))],
)
async def create_upload_session_v1(
    request: CreateUploadSessionRequest,
    response: Response,
    scope=Depends(get_department_scope),
    current_user: CurrentUser = Depends(get_current_user),
    service: AttachmentUploadService = Depends(get_attachment_upload_service),
    idempotency: IdempotencyContext | None = Depends(idempotent("upload_session")),
) -> UploadSessionResponse:
    result = await service.create(request, current_user, scope)
    response.headers["Location"] = f"/api/v1/upload-sessions/{result.id}"
    await complete_idempotency(idempotency, result, response, status_code=201)
    return result


@router.patch(
    "/upload-sessions/{session_id}",
    response_model=CompleteUploadSessionResponse,
    summary="Xác nhận tệp đã tải lên phiên bản v1",
    dependencies=[Depends(rate_limit_group("upload_completion"))],
)
async def complete_upload_session_v1_compat(
    session_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    service: AttachmentUploadService = Depends(get_attachment_upload_service),
    idempotency: IdempotencyContext | None = Depends(idempotent("upload_completion")),
) -> CompleteUploadSessionResponse:
    """Mirror PATCH cũ: không có body và thực hiện complete."""
    result = await service.complete(session_id, current_user)
    await complete_idempotency(idempotency, result)
    return result


@router.delete(
    "/upload-sessions/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Hủy phiên tải tệp phiên bản v1",
    dependencies=[Depends(rate_limit_group("upload_completion"))],
)
async def cancel_upload_session_v1(
    session_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    service: AttachmentUploadService = Depends(get_attachment_upload_service),
) -> Response:
    await service.cancel(session_id, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/upload-sessions/{session_id}/completions",
    response_model=CompleteUploadSessionResponse,
    summary="Xác nhận tệp đã tải lên phiên bản v1",
    dependencies=[Depends(rate_limit_group("upload_completion"))],
)
async def complete_upload_session_resource_v1(
    session_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    service: AttachmentUploadService = Depends(get_attachment_upload_service),
    idempotency: IdempotencyContext | None = Depends(idempotent("upload_completion")),
) -> CompleteUploadSessionResponse:
    result = await service.complete(session_id, current_user)
    await complete_idempotency(idempotency, result)
    return result


__all__ = ["router"]
