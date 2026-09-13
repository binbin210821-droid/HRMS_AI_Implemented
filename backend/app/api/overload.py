from fastapi import APIRouter, Depends, Request, Response

from app.api.dependencies import get_current_user, get_department_scope
from app.core.database import get_mongo_database
from app.core.pagination import PaginationParams, get_pagination, paginate_v1
from app.core.time import BusinessClock
from app.infrastructure.rate_limit import rate_limit_group
from app.models.overload import OverloadLogResponse, OverloadScanResponse
from app.models.user import CurrentUser
from app.repositories.overload_repository import OverloadRepository
from app.services.overload_service import OverloadService

router = APIRouter(prefix="/overload", tags=["Overload"])


def get_overload_service() -> OverloadService:
    return OverloadService(
        OverloadRepository(get_mongo_database().get_database()), clock=BusinessClock()
    )


@router.get(
    "",
    response_model=list[OverloadLogResponse],
    summary="Danh sách nhân viên quá tải",
    dependencies=[Depends(rate_limit_group("read_heavy"))],
)
async def list_overload_logs(
    request: Request,
    response: Response,
    pagination: PaginationParams = Depends(get_pagination),
    scope=Depends(get_department_scope),
    _: CurrentUser = Depends(get_current_user),
    service: OverloadService = Depends(get_overload_service),
) -> list[OverloadLogResponse]:
    if request.url.path.startswith("/api/v1/"):
        return paginate_v1(
            request,
            response,
            await service.list_logs_page(scope, pagination.offset, pagination.limit),
            pagination,
        )
    return paginate_v1(request, response, await service.list_logs(scope), pagination)


@router.post(
    "/scans",
    response_model=OverloadScanResponse,
    summary="Quét quá tải thủ công",
    name="scan_overload_logs_v1",
    dependencies=[Depends(rate_limit_group("scan"))],
)
@router.post(
    "/scan",
    response_model=OverloadScanResponse,
    summary="Deprecated: quét quá tải thủ công",
    deprecated=True,
    name="scan_overload_logs_legacy",
    dependencies=[Depends(rate_limit_group("scan"))],
)
async def scan_overload_logs(
    scope=Depends(get_department_scope),
    _: CurrentUser = Depends(get_current_user),
    service: OverloadService = Depends(get_overload_service),
) -> OverloadScanResponse:
    return await service.scan(scope)
