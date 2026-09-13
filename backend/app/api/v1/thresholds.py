from fastapi import APIRouter, Depends, status

from app.api.dependencies import get_current_user, get_department_scope, require_role
from app.api.thresholds import get_threshold_service
from app.core.pagination import ListQueryParams, PageResponse
from app.infrastructure.rate_limit import rate_limit_group
from app.models.threshold import ThresholdConfigResponse
from app.models.user import CurrentUser, UserRole
from app.services.threshold_service import ThresholdConfigService

router = APIRouter(prefix="/threshold-configs", tags=["Threshold configs v1"])


@router.get(
    "",
    response_model=PageResponse[ThresholdConfigResponse],
    summary="Danh sách cấu hình ngưỡng phiên bản v1",
    dependencies=[Depends(rate_limit_group("read_light"))],
)
async def list_threshold_configs_v1(
    pagination: ListQueryParams = Depends(),
    scope=Depends(get_department_scope),
    _: CurrentUser = Depends(get_current_user),
    service: ThresholdConfigService = Depends(get_threshold_service),
) -> PageResponse[ThresholdConfigResponse]:
    page = await service.list_page(
        scope, (pagination.page - 1) * pagination.page_size, pagination.page_size
    )
    return PageResponse(
        items=page.items,
        page=pagination.page,
        page_size=pagination.page_size,
        total=page.total,
        has_next=pagination.page * pagination.page_size < page.total,
    )


@router.post(
    "/{config_id}/approvals",
    response_model=ThresholdConfigResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Duyệt cấu hình ngưỡng phiên bản v1",
    dependencies=[Depends(rate_limit_group("directive_action"))],
)
async def approve_threshold_config_resource_v1(
    config_id: str,
    current_user: CurrentUser = Depends(require_role(UserRole.LEADERSHIP)),
    service: ThresholdConfigService = Depends(get_threshold_service),
) -> ThresholdConfigResponse:
    return await service.approve(config_id, current_user.user_id)


__all__ = ["router"]
