from datetime import date as Date

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from pydantic import ValidationError

from app.api.dependencies import get_current_user, get_department_scope, require_role
from app.core.config import get_settings
from app.core.database import get_mongo_database
from app.core.time import BusinessClock
from app.infrastructure.evidence_storage import create_evidence_storage
from app.infrastructure.malware_scanner import create_malware_scanner
from app.models.department_evaluation import (
    DepartmentEvaluationDownloadUrlResponse,
    DepartmentWeeklyEvaluationListResponse,
    DepartmentWeeklyEvaluationPayload,
    DepartmentWeeklyEvaluationResponse,
    DepartmentWeeklyEvaluationUpdatePayload,
    DepartmentWeeklyReviewResponse,
)
from app.models.user import CurrentUser, UserRole
from app.repositories.attachment_upload_repository import AttachmentUploadRepository
from app.repositories.department_evaluation_repository import DepartmentEvaluationRepository
from app.services.attachment_upload_service import AttachmentUploadService
from app.services.department_evaluation_service import (
    DepartmentEvaluationService,
    EvaluationUpload,
)

router = APIRouter(prefix="/api/department-evaluations", tags=["Department Evaluations"])


def get_department_evaluation_service() -> DepartmentEvaluationService:
    database = get_mongo_database().get_database()
    storage = create_evidence_storage()
    return DepartmentEvaluationService(
        DepartmentEvaluationRepository(database),
        storage,
        clock=BusinessClock(),
        scanner=create_malware_scanner(),
        upload_service=AttachmentUploadService(
            AttachmentUploadRepository(database), storage, clock=BusinessClock()
        ),
    )


async def _read_uploads(files: list[UploadFile]) -> list[EvaluationUpload]:
    maximum = get_settings().storage_max_file_size
    uploads: list[EvaluationUpload] = []
    for file in files:
        try:
            content = await file.read(maximum + 1)
        finally:
            await file.close()
        uploads.append(
            EvaluationUpload(
                file_name=file.filename or "tai-lieu",
                content_type=file.content_type or "application/octet-stream",
                content=content,
            )
        )
    return uploads


def _parse_payload(value: str, model_type):
    try:
        return model_type.model_validate_json(value)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Thông tin đánh giá phòng ban không hợp lệ",
        ) from exc


@router.get(
    "/weekly-review",
    response_model=DepartmentWeeklyReviewResponse,
    summary="Xem bằng chứng đánh giá phòng ban theo tuần",
)
async def get_weekly_department_review(
    department_id: str,
    week_start: Date,
    _: CurrentUser = Depends(require_role(UserRole.LEADERSHIP)),
    service: DepartmentEvaluationService = Depends(get_department_evaluation_service),
) -> DepartmentWeeklyReviewResponse:
    return await service.weekly_review(department_id, week_start)


@router.get(
    "",
    response_model=DepartmentWeeklyEvaluationListResponse,
    summary="Danh sách đánh giá phòng ban theo tuần",
)
async def list_department_evaluations(
    department_id: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=12, ge=1, le=50),
    scope=Depends(get_department_scope),
    _: CurrentUser = Depends(get_current_user),
    service: DepartmentEvaluationService = Depends(get_department_evaluation_service),
) -> DepartmentWeeklyEvaluationListResponse:
    return await service.list(scope, department_id, page, page_size)


@router.get(
    "/{evaluation_id}",
    response_model=DepartmentWeeklyEvaluationResponse,
    summary="Xem chi tiết đánh giá phòng ban",
)
async def get_department_evaluation(
    evaluation_id: str,
    scope=Depends(get_department_scope),
    _: CurrentUser = Depends(get_current_user),
    service: DepartmentEvaluationService = Depends(get_department_evaluation_service),
) -> DepartmentWeeklyEvaluationResponse:
    return await service.get(evaluation_id, scope)


@router.get(
    "/{evaluation_id}/attachments/{attachment_id}/download-url",
    response_model=DepartmentEvaluationDownloadUrlResponse,
    summary="Tạo liên kết tải tài liệu đánh giá",
)
async def get_department_evaluation_attachment_url(
    evaluation_id: str,
    attachment_id: str,
    scope=Depends(get_department_scope),
    _: CurrentUser = Depends(get_current_user),
    service: DepartmentEvaluationService = Depends(get_department_evaluation_service),
) -> DepartmentEvaluationDownloadUrlResponse:
    return await service.get_attachment_download_url(evaluation_id, attachment_id, scope)


@router.post(
    "/weekly-review",
    response_model=DepartmentWeeklyEvaluationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Lãnh đạo đánh giá phòng ban theo tuần",
)
async def create_weekly_department_evaluation(
    payload: str = Form(...),
    files: list[UploadFile] | None = File(default=None),
    current_user: CurrentUser = Depends(require_role(UserRole.LEADERSHIP)),
    service: DepartmentEvaluationService = Depends(get_department_evaluation_service),
) -> DepartmentWeeklyEvaluationResponse:
    request = _parse_payload(payload, DepartmentWeeklyEvaluationPayload)
    return await service.create(
        request, await _read_uploads(files or []), current_user.user_id
    )


@router.patch(
    "/{evaluation_id}",
    response_model=DepartmentWeeklyEvaluationResponse,
    summary="Thay đổi đánh giá phòng ban theo tuần",
)
async def update_weekly_department_evaluation(
    evaluation_id: str,
    payload: str = Form(...),
    files: list[UploadFile] | None = File(default=None),
    current_user: CurrentUser = Depends(require_role(UserRole.LEADERSHIP)),
    service: DepartmentEvaluationService = Depends(get_department_evaluation_service),
) -> DepartmentWeeklyEvaluationResponse:
    request = _parse_payload(payload, DepartmentWeeklyEvaluationUpdatePayload)
    return await service.update(
        evaluation_id,
        request,
        await _read_uploads(files or []),
        current_user.user_id,
    )


__all__ = ["router"]
