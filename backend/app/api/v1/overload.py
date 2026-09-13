from fastapi import APIRouter, Depends

from app.api.dependencies import get_current_user, get_department_scope
from app.api.overload import get_overload_service
from app.api.v1._query import build_sort_stage, validate_date_range
from app.core.pagination import DateRangeParams, ListQueryParams, PageResponse
from app.infrastructure.rate_limit import rate_limit_group
from app.models.overload import OverloadLogResponse
from app.models.user import CurrentUser
from app.services.overload_service import OverloadService

router = APIRouter(prefix="/overload", tags=["Overload v1"])


@router.get(
    "",
    response_model=PageResponse[OverloadLogResponse],
    summary="Danh sách nhân viên quá tải phiên bản v1",
    dependencies=[Depends(rate_limit_group("read_heavy"))],
)
async def list_overload_logs_v1(
    pagination: ListQueryParams = Depends(),
    date_range: DateRangeParams = Depends(),
    scope=Depends(get_department_scope),
    _: CurrentUser = Depends(get_current_user),
    service: OverloadService = Depends(get_overload_service),
) -> PageResponse[OverloadLogResponse]:
    validate_date_range(date_range.from_date, date_range.to_date)
    page = await service.list_logs_page_v1(
        scope,
        date_range.from_date,
        date_range.to_date,
        build_sort_stage(
            pagination.sort,
            {"date", "created_at", "tasks_completed", "quality_score"},
            "date",
            -1,
        ),
        pagination.page,
        pagination.page_size,
    )
    return PageResponse(
        items=page.items,
        page=pagination.page,
        page_size=pagination.page_size,
        total=page.total,
        has_next=pagination.page * pagination.page_size < page.total,
    )
