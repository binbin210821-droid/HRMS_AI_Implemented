from datetime import date as Date

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.dependencies import get_current_user, get_department_scope, require_role
from app.api.performance import get_performance_review_service, get_performance_service
from app.infrastructure.idempotency import IdempotencyContext, complete_idempotency, idempotent
from app.infrastructure.rate_limit import rate_limit_group
from app.models.performance import DepartmentWeeklyPerformanceTrendResponse
from app.models.task_execution import (
    DailyPerformanceReviewCreate,
    DailyPerformanceReviewResponse,
    DailyPerformanceReviewUpdateV1,
    DailyReviewDownloadUrlResponse,
)
from app.models.user import CurrentUser, UserRole
from app.services.performance_review_service import PerformanceReviewService
from app.services.performance_service import PerformanceService

router = APIRouter(prefix="/performance", tags=["Performance v1"])


@router.get(
    "/daily-reviews/{employee_id}/{date}",
    response_model=DailyPerformanceReviewResponse,
    summary="Xem nghiệm thu hiệu suất ngày phiên bản v1",
    dependencies=[Depends(rate_limit_group("read_light"))],
)
async def get_daily_review_v1(
    employee_id: str,
    date: Date,
    scope=Depends(get_department_scope),
    _: CurrentUser = Depends(require_role(UserRole.MANAGER)),
    service: PerformanceReviewService = Depends(get_performance_review_service),
) -> DailyPerformanceReviewResponse:
    return await service.get_review(employee_id, date, scope)


@router.get(
    "/daily-reviews/{employee_id}/{date}/attachments/{attachment_id}/download-url",
    response_model=DailyReviewDownloadUrlResponse,
    summary="Tạo liên kết tải minh chứng công việc phiên bản v1",
    dependencies=[Depends(rate_limit_group("read_light"))],
)
async def get_daily_review_attachment_url_v1(
    employee_id: str,
    date: Date,
    attachment_id: str,
    scope=Depends(get_department_scope),
    _: CurrentUser = Depends(require_role(UserRole.MANAGER)),
    service: PerformanceReviewService = Depends(get_performance_review_service),
) -> DailyReviewDownloadUrlResponse:
    return await service.get_attachment_download_url(employee_id, date, attachment_id, scope)


@router.post(
    "/daily-reviews",
    response_model=DailyPerformanceReviewResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Nghiệm thu và lưu điểm hiệu suất ngày phiên bản v1",
    dependencies=[Depends(rate_limit_group("mutation"))],
)
async def create_daily_review_v1(
    request: DailyPerformanceReviewCreate,
    response: Response,
    scope=Depends(get_department_scope),
    current_user: CurrentUser = Depends(require_role(UserRole.MANAGER)),
    service: PerformanceReviewService = Depends(get_performance_review_service),
    idempotency: IdempotencyContext | None = Depends(idempotent("daily_review")),
) -> DailyPerformanceReviewResponse:
    result = await service.save_review(request, scope, current_user.user_id)
    response.headers["Location"] = (
        f"/api/v1/performance/daily-reviews/{result.employee.id}/{result.date.isoformat()}"
    )
    await complete_idempotency(idempotency, result, response, status_code=201)
    return result


@router.patch(
    "/daily-reviews/{employee_id}/{date}",
    response_model=DailyPerformanceReviewResponse,
    summary="Thay đổi điểm nghiệm thu hiệu suất ngày phiên bản v1",
    dependencies=[Depends(rate_limit_group("mutation"))],
)
async def update_daily_review_v1(
    employee_id: str,
    date: Date,
    request: DailyPerformanceReviewUpdateV1,
    scope=Depends(get_department_scope),
    current_user: CurrentUser = Depends(require_role(UserRole.MANAGER)),
    service: PerformanceReviewService = Depends(get_performance_review_service),
) -> DailyPerformanceReviewResponse:
    service_request = DailyPerformanceReviewCreate(
        employee_id=employee_id,
        date=date,
        items=request.items,
    )
    return await service.update_review(
        service_request,
        scope,
        current_user.user_id,
        reason=request.reason,
    )


@router.get(
    "/analytics/department/{department_id}/weekly-trend",
    response_model=DepartmentWeeklyPerformanceTrendResponse,
    summary="Xu hướng hiệu suất theo tuần của phòng ban",
    dependencies=[Depends(rate_limit_group("read_heavy"))],
)
async def get_department_weekly_trend_v1(
    department_id: str,
    start_date: Date | None = Query(default=None),
    end_date: Date | None = Query(default=None),
    scope=Depends(get_department_scope),
    _: CurrentUser = Depends(get_current_user),
    service: PerformanceService = Depends(get_performance_service),
) -> DepartmentWeeklyPerformanceTrendResponse:
    return await service.department_weekly_trend(scope, department_id, start_date, end_date)


__all__ = ["router"]
