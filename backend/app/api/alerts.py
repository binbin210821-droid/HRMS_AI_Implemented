from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_current_user, get_department_scope, require_role
from app.core.database import get_mongo_database
from app.core.time import BusinessClock
from app.models.alert import AlertResolveRequest, AlertResponse, DepartmentAlertSummaryResponse
from app.models.user import CurrentUser, UserRole
from app.repositories.alert_repository import AlertRepository
from app.repositories.performance_repository import PerformanceRepository
from app.repositories.threshold_repository import ThresholdConfigRepository
from app.services.alert_service import EarlyWarningService

router = APIRouter(prefix="/api/alerts", tags=["Alerts"])


def get_alert_service() -> EarlyWarningService:
    database = get_mongo_database().get_database()
    return EarlyWarningService(
        AlertRepository(database),
        PerformanceRepository(database),
        ThresholdConfigRepository(database),
        clock=BusinessClock(),
    )


@router.get("", response_model=list[AlertResponse], summary="Danh sách cảnh báo ngưỡng bất lợi")
async def list_alerts(
    alert_status: str | None = Query(default=None, alias="status"),
    alert_type: str | None = Query(default="early_warning"),
    scope=Depends(get_department_scope),
    _: CurrentUser = Depends(get_current_user),
    service: EarlyWarningService = Depends(get_alert_service),
) -> list[AlertResponse]:
    return await service.list_alerts(
        scope,
        alert_status,
        None if alert_type == "all" else alert_type,
    )


@router.get(
    "/department-summary",
    response_model=list[DepartmentAlertSummaryResponse],
    summary="Tổng hợp cảnh báo theo phòng ban",
)
async def list_department_alert_summaries(
    _: CurrentUser = Depends(require_role(UserRole.LEADERSHIP)),
    service: EarlyWarningService = Depends(get_alert_service),
) -> list[DepartmentAlertSummaryResponse]:
    return await service.list_department_summaries()


@router.post("/scan", response_model=list[AlertResponse], summary="Quét cảnh báo ngưỡng bất lợi")
async def scan_alerts(
    scope=Depends(get_department_scope),
    _: CurrentUser = Depends(get_current_user),
    service: EarlyWarningService = Depends(get_alert_service),
) -> list[AlertResponse]:
    return await service.scan_all(scope)


@router.patch(
    "/{alert_id}/resolve",
    response_model=AlertResponse,
    summary="Đánh dấu cảnh báo đã xử lý",
)
async def resolve_alert(
    alert_id: str,
    request: AlertResolveRequest,
    scope=Depends(get_department_scope),
    current_user: CurrentUser = Depends(get_current_user),
    service: EarlyWarningService = Depends(get_alert_service),
) -> AlertResponse:
    return await service.resolve(alert_id, scope, current_user.user_id, request)
