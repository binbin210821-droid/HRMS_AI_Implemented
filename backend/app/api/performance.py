from datetime import date as Date

from fastapi import APIRouter, Depends, Query, status

from app.api.dependencies import get_current_user, get_department_scope, require_role
from app.core.database import get_mongo_database
from app.core.time import BusinessClock
from app.infrastructure.evidence_storage import create_evidence_storage
from app.models.performance import (
    CompanyPerformanceAnalyticsResponse,
    DepartmentPerformanceAnalyticsResponse,
    EmployeePerformanceAnalyticsResponse,
    PerformanceMetricCreate,
    PerformanceMetricResponse,
)
from app.models.task_execution import (
    DailyPerformanceReviewCreate,
    DailyPerformanceReviewResponse,
    DailyReviewDownloadUrlResponse,
)
from app.models.user import CurrentUser, UserRole
from app.repositories.performance_repository import PerformanceRepository
from app.repositories.task_execution_repository import TaskExecutionRepository
from app.repositories.task_repository import TaskRepository
from app.services.performance_review_service import PerformanceReviewService
from app.services.performance_service import PerformanceService

router = APIRouter(prefix="/api/performance", tags=["Performance"])


def get_performance_service() -> PerformanceService:
    return PerformanceService(
        PerformanceRepository(get_mongo_database().get_database()), clock=BusinessClock()
    )


def get_performance_review_service() -> PerformanceReviewService:
    database = get_mongo_database().get_database()
    return PerformanceReviewService(
        TaskRepository(database),
        TaskExecutionRepository(database),
        PerformanceRepository(database),
        create_evidence_storage(),
        clock=BusinessClock(),
    )


@router.get(
    "/daily-review",
    response_model=DailyPerformanceReviewResponse,
    summary="Xem công việc và bằng chứng để nghiệm thu ngày",
)
async def get_daily_performance_review(
    employee_id: str,
    review_date: Date = Query(alias="date"),
    scope=Depends(get_department_scope),
    _: CurrentUser = Depends(require_role(UserRole.MANAGER)),
    service: PerformanceReviewService = Depends(get_performance_review_service),
) -> DailyPerformanceReviewResponse:
    return await service.get_review(employee_id, review_date, scope)


@router.post(
    "/daily-review",
    response_model=DailyPerformanceReviewResponse,
    summary="Nghiệm thu và lưu điểm hiệu suất ngày",
)
async def save_daily_performance_review(
    request: DailyPerformanceReviewCreate,
    scope=Depends(get_department_scope),
    current_user: CurrentUser = Depends(require_role(UserRole.MANAGER)),
    service: PerformanceReviewService = Depends(get_performance_review_service),
) -> DailyPerformanceReviewResponse:
    return await service.save_review(request, scope, current_user.user_id)


@router.get(
    "/daily-review/{employee_id}/{review_date}/attachments/{attachment_id}/download-url",
    response_model=DailyReviewDownloadUrlResponse,
    summary="Tạo liên kết tải minh chứng công việc",
)
async def get_daily_review_attachment_url(
    employee_id: str,
    review_date: Date,
    attachment_id: str,
    scope=Depends(get_department_scope),
    _: CurrentUser = Depends(require_role(UserRole.MANAGER)),
    service: PerformanceReviewService = Depends(get_performance_review_service),
) -> DailyReviewDownloadUrlResponse:
    return await service.get_attachment_download_url(
        employee_id, review_date, attachment_id, scope
    )


@router.patch(
    "/daily-review",
    response_model=DailyPerformanceReviewResponse,
    summary="Thay đổi điểm nghiệm thu hiệu suất trong ngày",
)
async def update_daily_performance_review(
    request: DailyPerformanceReviewCreate,
    scope=Depends(get_department_scope),
    current_user: CurrentUser = Depends(require_role(UserRole.MANAGER)),
    service: PerformanceReviewService = Depends(get_performance_review_service),
) -> DailyPerformanceReviewResponse:
    return await service.update_review(request, scope, current_user.user_id)


@router.post(
    "/daily",
    response_model=PerformanceMetricResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Deprecated: đã thay bằng /api/performance/daily-review",
    deprecated=True,
)
async def create_daily_performance(
    request: PerformanceMetricCreate,
    scope=Depends(get_department_scope),
    current_user: CurrentUser = Depends(require_role(UserRole.MANAGER)),
    service: PerformanceService = Depends(get_performance_service),
) -> PerformanceMetricResponse:
    return await service.create_daily(request, scope, current_user.user_id)


@router.get(
    "", response_model=list[PerformanceMetricResponse], summary="Danh sách chỉ số hiệu suất"
)
async def list_performance(
    employee_id: str | None = Query(default=None),
    department_id: str | None = Query(default=None),
    start_date: Date | None = Query(default=None),
    end_date: Date | None = Query(default=None),
    scope=Depends(get_department_scope),
    _: CurrentUser = Depends(get_current_user),
    service: PerformanceService = Depends(get_performance_service),
) -> list[PerformanceMetricResponse]:
    return await service.list(scope, employee_id, department_id, start_date, end_date)


@router.get(
    "/analytics/employee/{employee_id}",
    response_model=EmployeePerformanceAnalyticsResponse,
    summary="Xu hướng hiệu suất của nhân viên",
)
async def get_employee_performance_analytics(
    employee_id: str,
    start_date: Date | None = Query(default=None),
    end_date: Date | None = Query(default=None),
    scope=Depends(get_department_scope),
    _: CurrentUser = Depends(get_current_user),
    service: PerformanceService = Depends(get_performance_service),
) -> EmployeePerformanceAnalyticsResponse:
    return await service.employee_analytics(scope, employee_id, start_date, end_date)


@router.get(
    "/analytics/department/{department_id}",
    response_model=DepartmentPerformanceAnalyticsResponse,
    summary="So sánh hiệu suất trong phòng ban",
)
async def get_department_performance_analytics(
    department_id: str,
    start_date: Date | None = Query(default=None),
    end_date: Date | None = Query(default=None),
    scope=Depends(get_department_scope),
    _: CurrentUser = Depends(get_current_user),
    service: PerformanceService = Depends(get_performance_service),
) -> DepartmentPerformanceAnalyticsResponse:
    return await service.department_analytics(scope, department_id, start_date, end_date)


@router.get(
    "/analytics/company",
    response_model=CompanyPerformanceAnalyticsResponse,
    summary="So sánh hiệu suất giữa các phòng ban",
)
async def get_company_performance_analytics(
    start_date: Date | None = Query(default=None),
    end_date: Date | None = Query(default=None),
    _: CurrentUser = Depends(require_role(UserRole.LEADERSHIP)),
    service: PerformanceService = Depends(get_performance_service),
) -> CompanyPerformanceAnalyticsResponse:
    return await service.company_analytics(start_date, end_date)
