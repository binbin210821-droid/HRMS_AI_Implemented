from fastapi import APIRouter, Depends, status

from app.api.dependencies import get_current_user, get_department_scope, require_role
from app.core.database import get_mongo_database
from app.core.time import BusinessClock
from app.models.threshold import (
    ThresholdConfigCreate,
    ThresholdConfigResponse,
)
from app.models.user import CurrentUser, UserRole
from app.repositories.threshold_repository import ThresholdConfigRepository
from app.services.threshold_service import ThresholdConfigService

router = APIRouter(prefix="/api/threshold-configs", tags=["Threshold configs"])


def get_threshold_service() -> ThresholdConfigService:
    return ThresholdConfigService(
        ThresholdConfigRepository(get_mongo_database().get_database()), clock=BusinessClock()
    )


@router.get("", response_model=list[ThresholdConfigResponse], summary="Danh sách cấu hình ngưỡng")
async def list_threshold_configs(
    scope=Depends(get_department_scope),
    _: CurrentUser = Depends(get_current_user),
    service: ThresholdConfigService = Depends(get_threshold_service),
) -> list[ThresholdConfigResponse]:
    return await service.list(scope)


@router.post(
    "",
    response_model=ThresholdConfigResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Đề xuất cấu hình ngưỡng",
)
async def propose_threshold_config(
    request: ThresholdConfigCreate,
    scope=Depends(get_department_scope),
    current_user: CurrentUser = Depends(require_role(UserRole.MANAGER)),
    service: ThresholdConfigService = Depends(get_threshold_service),
) -> ThresholdConfigResponse:
    return await service.propose(request, scope, current_user.user_id)


@router.post(
    "/{config_id}/approve",
    response_model=ThresholdConfigResponse,
    summary="Duyệt cấu hình ngưỡng",
)
async def approve_threshold_config(
    config_id: str,
    current_user: CurrentUser = Depends(require_role(UserRole.LEADERSHIP)),
    service: ThresholdConfigService = Depends(get_threshold_service),
) -> ThresholdConfigResponse:
    return await service.approve(config_id, current_user.user_id)
