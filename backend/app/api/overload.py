from fastapi import APIRouter, Depends

from app.api.dependencies import get_current_user, get_department_scope
from app.core.database import get_mongo_database
from app.core.time import BusinessClock
from app.models.overload import OverloadLogResponse, OverloadScanResponse
from app.models.user import CurrentUser
from app.repositories.overload_repository import OverloadRepository
from app.services.overload_service import OverloadService

router = APIRouter(prefix="/api/overload", tags=["Overload"])


def get_overload_service() -> OverloadService:
    return OverloadService(
        OverloadRepository(get_mongo_database().get_database()), clock=BusinessClock()
    )


@router.get("", response_model=list[OverloadLogResponse], summary="Danh sách nhân viên quá tải")
async def list_overload_logs(
    scope=Depends(get_department_scope),
    _: CurrentUser = Depends(get_current_user),
    service: OverloadService = Depends(get_overload_service),
) -> list[OverloadLogResponse]:
    return await service.list_logs(scope)


@router.post(
    "/scan",
    response_model=OverloadScanResponse,
    summary="Deprecated: đường tự động chính dùng event từ metric mới; endpoint chỉ giữ tương thích ngược thủ công",
    deprecated=True,
)
async def scan_overload_logs(
    scope=Depends(get_department_scope),
    _: CurrentUser = Depends(get_current_user),
    service: OverloadService = Depends(get_overload_service),
) -> OverloadScanResponse:
    return await service.scan(scope)
