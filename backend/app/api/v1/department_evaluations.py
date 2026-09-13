from datetime import date as Date

from fastapi import APIRouter, Depends, File, Form, Response, UploadFile, status

from app.api.department_evaluations import (
    _parse_payload,
    _read_uploads,
    get_department_evaluation_service,
)
from app.api.dependencies import get_department_scope, require_role
from app.infrastructure.idempotency import IdempotencyContext, complete_idempotency, idempotent
from app.infrastructure.rate_limit import rate_limit_group
from app.models.department_evaluation import (
    DepartmentEvaluationDownloadUrlResponse,
    DepartmentWeeklyEvaluationPayload,
    DepartmentWeeklyEvaluationResponse,
    DepartmentWeeklyEvaluationUpdatePayload,
    DepartmentWeeklyReviewResponse,
)
from app.models.user import CurrentUser, UserRole
from app.services.department_evaluation_service import DepartmentEvaluationService

router = APIRouter(prefix="/department-evaluations", tags=["Department Evaluations v1"])


@router.get(
    "/weekly-reviews/{department_id}/{week_start}",
    response_model=DepartmentWeeklyReviewResponse,
    summary="Xem bằng chứng đánh giá phòng ban theo tuần phiên bản v1",
    dependencies=[Depends(rate_limit_group("read_light"))],
)
async def get_weekly_department_review_v1(
    department_id: str,
    week_start: Date,
    _: CurrentUser = Depends(require_role(UserRole.LEADERSHIP)),
    service: DepartmentEvaluationService = Depends(get_department_evaluation_service),
) -> DepartmentWeeklyReviewResponse:
    return await service.weekly_review(department_id, week_start)


@router.get(
    "/{evaluation_id}/attachments/{attachment_id}/download-url",
    response_model=DepartmentEvaluationDownloadUrlResponse,
    summary="Tạo liên kết tải tài liệu đánh giá phiên bản v1",
    dependencies=[Depends(rate_limit_group("read_light"))],
)
async def get_department_evaluation_attachment_url_v1(
    evaluation_id: str,
    attachment_id: str,
    scope=Depends(get_department_scope),
    _: CurrentUser = Depends(require_role(UserRole.LEADERSHIP)),
    service: DepartmentEvaluationService = Depends(get_department_evaluation_service),
) -> DepartmentEvaluationDownloadUrlResponse:
    return await service.get_attachment_download_url(evaluation_id, attachment_id, scope)


@router.post(
    "/weekly-evaluations",
    response_model=DepartmentWeeklyEvaluationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Lãnh đạo đánh giá phòng ban theo tuần phiên bản v1",
    dependencies=[Depends(rate_limit_group("mutation"))],
)
async def create_weekly_department_evaluation_v1(
    response: Response,
    payload: str = Form(...),
    files: list[UploadFile] | None = File(default=None),
    current_user: CurrentUser = Depends(require_role(UserRole.LEADERSHIP)),
    service: DepartmentEvaluationService = Depends(get_department_evaluation_service),
    idempotency: IdempotencyContext | None = Depends(idempotent("weekly_evaluation")),
) -> DepartmentWeeklyEvaluationResponse:
    request = _parse_payload(payload, DepartmentWeeklyEvaluationPayload)
    result = await service.create(request, await _read_uploads(files or []), current_user.user_id)
    response.headers["Location"] = f"/api/v1/department-evaluations/{result.id}"
    await complete_idempotency(
        idempotency, result, response, status_code=201
    )
    return result


@router.patch(
    "/{evaluation_id}",
    response_model=DepartmentWeeklyEvaluationResponse,
    summary="Thay đổi đánh giá phòng ban theo tuần phiên bản v1",
    dependencies=[Depends(rate_limit_group("mutation"))],
)
async def update_weekly_department_evaluation_v1(
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
