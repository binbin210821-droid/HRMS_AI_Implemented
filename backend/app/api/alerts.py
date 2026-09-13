from fastapi import APIRouter, Depends, Query, Request, Response

from app.api.dependencies import get_current_user, get_department_scope, require_role
from app.core.database import get_mongo_database
from app.core.pagination import PaginationParams, get_pagination, paginate_v1
from app.core.time import BusinessClock
from app.infrastructure.rate_limit import rate_limit_group
from app.models.alert import AlertResolveRequest, AlertResponse, DepartmentAlertSummaryResponse
from app.models.user import CurrentUser, UserRole
from app.repositories.alert_repository import AlertRepository
from app.repositories.performance_repository import PerformanceRepository
from app.repositories.threshold_repository import ThresholdConfigRepository
from app.services.alert_service import EarlyWarningService

router = APIRouter(prefix="/alerts", tags=["Alerts"])


def get_alert_service() -> EarlyWarningService:
    database = get_mongo_database().get_database()
    return EarlyWarningService(
        AlertRepository(database),
        PerformanceRepository(database),
        ThresholdConfigRepository(database),
        clock=BusinessClock(),
    )


@router.get(
    "",
    response_model=list[AlertResponse],
    summary="Danh sách cảnh báo ngưỡng bất lợi",
    dependencies=[Depends(rate_limit_group("read_operational"))],
)
async def list_alerts(
    request: Request,
    response: Response,
    alert_status: str | None = Query(default=None, alias="status"),
    alert_type: str | None = Query(default="early_warning"),
    pagination: PaginationParams = Depends(get_pagination),
    scope=Depends(get_department_scope),
    _: CurrentUser = Depends(get_current_user),
    service: EarlyWarningService = Depends(get_alert_service),
) -> list[AlertResponse]:
    normalized_type = None if alert_type == "all" else alert_type
    if request.url.path.startswith("/api/v1/"):
        return paginate_v1(
            request,
            response,
            await service.list_alerts_page(
                scope, alert_status, normalized_type, pagination.offset, pagination.limit
            ),
            pagination,
        )
    return paginate_v1(
        request, response, await service.list_alerts(scope, alert_status, normalized_type), pagination
    )


@router.get(
    "/department-summary",
    response_model=list[DepartmentAlertSummaryResponse],
    summary="Tổng hợp cảnh báo theo phòng ban",
    dependencies=[Depends(rate_limit_group("read_heavy"))],
)
async def list_department_alert_summaries(
    request: Request,
    response: Response,
    pagination: PaginationParams = Depends(get_pagination),
    _: CurrentUser = Depends(require_role(UserRole.LEADERSHIP)),
    service: EarlyWarningService = Depends(get_alert_service),
) -> list[DepartmentAlertSummaryResponse]:
    if request.url.path.startswith("/api/v1/"):
        return paginate_v1(
            request,
            response,
            await service.list_department_summaries_page(pagination.offset, pagination.limit),
            pagination,
        )
    return paginate_v1(request, response, await service.list_department_summaries(), pagination)


@router.post(
    "/scan",
    response_model=list[AlertResponse],
    summary="Quét cảnh báo ngưỡng bất lợi",
    dependencies=[Depends(rate_limit_group("scan"))],
)
async def scan_alerts(
    scope=Depends(get_department_scope),
    _: CurrentUser = Depends(get_current_user),
    service: EarlyWarningService = Depends(get_alert_service),
) -> list[AlertResponse]:
    return await service.scan_all(scope)


@router.patch(
    "/{alert_id}",
    response_model=AlertResponse,
    summary="Đánh dấu cảnh báo đã xử lý",
    name="resolve_alert_v1",
    dependencies=[Depends(rate_limit_group("mutation"))],
)
@router.patch(
    "/{alert_id}/resolve",
    response_model=AlertResponse,
    summary="Deprecated: đánh dấu cảnh báo đã xử lý",
    deprecated=True,
    name="resolve_alert_legacy",
    dependencies=[Depends(rate_limit_group("mutation"))],
)
async def resolve_alert(
    alert_id: str,
    request: AlertResolveRequest,
    scope=Depends(get_department_scope),
    current_user: CurrentUser = Depends(get_current_user),
    service: EarlyWarningService = Depends(get_alert_service),
) -> AlertResponse:
    return await service.resolve(alert_id, scope, current_user.user_id, request)
