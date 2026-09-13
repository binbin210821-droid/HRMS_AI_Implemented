"""Explicit v1 scan actions for alerts and overload analysis."""

from fastapi import APIRouter, Depends

from app.api.alerts import get_alert_service
from app.api.dependencies import get_current_user, get_department_scope
from app.api.overload import get_overload_service
from app.infrastructure.rate_limit import rate_limit_group
from app.models.alert import AlertResponse
from app.models.overload import OverloadScanResponse
from app.models.user import CurrentUser
from app.services.alert_service import EarlyWarningService
from app.services.overload_service import OverloadService

router = APIRouter(tags=["Scans v1"])


@router.post(
    "/alert-scans",
    response_model=list[AlertResponse],
    summary="Quét cảnh báo ngưỡng bất lợi phiên bản v1",
    dependencies=[Depends(rate_limit_group("scan"))],
)
async def scan_alerts_v1(
    scope=Depends(get_department_scope),
    _: CurrentUser = Depends(get_current_user),
    service: EarlyWarningService = Depends(get_alert_service),
) -> list[AlertResponse]:
    return await service.scan_all(scope)


@router.post(
    "/overload-scans",
    response_model=OverloadScanResponse,
    summary="Quét quá tải phiên bản v1",
    dependencies=[Depends(rate_limit_group("scan"))],
)
async def scan_overload_v1(
    scope=Depends(get_department_scope),
    _: CurrentUser = Depends(get_current_user),
    service: OverloadService = Depends(get_overload_service),
) -> OverloadScanResponse:
    return await service.scan(scope)


__all__ = ["router"]
