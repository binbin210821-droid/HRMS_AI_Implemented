from fastapi import APIRouter, Depends, Request, Response, status

from app.api.dependencies import get_current_user, get_department_scope, require_role
from app.core.database import get_mongo_database
from app.core.pagination import PaginationParams, get_pagination, paginate_v1
from app.core.time import BusinessClock
from app.infrastructure.rate_limit import rate_limit_group
from app.models.threshold import (
    ThresholdConfigCreate,
    ThresholdConfigResponse,
)
from app.models.user import CurrentUser, UserRole
from app.repositories.threshold_repository import ThresholdConfigRepository
from app.services.threshold_service import ThresholdConfigService

router = APIRouter(prefix="/threshold-configs", tags=["Threshold configs"])


def get_threshold_service() -> ThresholdConfigService:
    return ThresholdConfigService(
        ThresholdConfigRepository(get_mongo_database().get_database()), clock=BusinessClock()
    )


@router.get(
    "",
    response_model=list[ThresholdConfigResponse],
    summary="Danh sách cấu hình ngưỡng",
    dependencies=[Depends(rate_limit_group("read_light"))],
)
async def list_threshold_configs(
    request: Request,
    response: Response,
    pagination: PaginationParams = Depends(get_pagination),
    scope=Depends(get_department_scope),
    _: CurrentUser = Depends(get_current_user),
    service: ThresholdConfigService = Depends(get_threshold_service),
) -> list[ThresholdConfigResponse]:
    if request.url.path.startswith("/api/v1/"):
        return paginate_v1(
            request,
            response,
            await service.list_page(scope, pagination.offset, pagination.limit),
            pagination,
        )
    return paginate_v1(request, response, await service.list(scope), pagination)


@router.post(
    "",
    response_model=ThresholdConfigResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Đề xuất cấu hình ngưỡng",
    dependencies=[Depends(rate_limit_group("mutation"))],
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
    summary="Deprecated: duyệt cấu hình ngưỡng",
    deprecated=True,
    name="approve_threshold_config_legacy",
    dependencies=[Depends(rate_limit_group("directive_action"))],
)
@router.patch(
    "/{config_id}",
    response_model=ThresholdConfigResponse,
    summary="Duyệt cấu hình ngưỡng",
    name="approve_threshold_config_v1",
    dependencies=[Depends(rate_limit_group("directive_action"))],
)
async def approve_threshold_config(
    config_id: str,
    current_user: CurrentUser = Depends(require_role(UserRole.LEADERSHIP)),
    service: ThresholdConfigService = Depends(get_threshold_service),
) -> ThresholdConfigResponse:
    return await service.approve(config_id, current_user.user_id)
