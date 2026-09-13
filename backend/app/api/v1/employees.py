from fastapi import APIRouter, Depends, Query, Response, status

from app.api.dependencies import get_department_scope
from app.api.employees import get_employee_service
from app.api.v1._query import build_sort_stage
from app.core.pagination import ListQueryParams, PageResponse
from app.infrastructure.rate_limit import rate_limit_group
from app.models.employee import EmployeeCreate, EmployeeResponse, EmployeeUpdate
from app.services.employee_service import EmployeeService

router = APIRouter(prefix="/employees", tags=["Employees v1"])


@router.get(
    "",
    response_model=PageResponse[EmployeeResponse],
    summary="Danh sách nhân viên phiên bản v1",
    dependencies=[Depends(rate_limit_group("read_light"))],
)
async def list_employees_v1(
    pagination: ListQueryParams = Depends(),
    department_id: str | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    scope=Depends(get_department_scope),
    service: EmployeeService = Depends(get_employee_service),
) -> PageResponse[EmployeeResponse]:
    page = await service.list_page_v1(
        scope,
        department_id,
        is_active,
        build_sort_stage(
            pagination.sort, {"full_name", "employee_code", "created_at"}, "full_name"
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


@router.get(
    "/{employee_id}",
    response_model=EmployeeResponse,
    summary="Chi tiết nhân viên phiên bản v1",
    dependencies=[Depends(rate_limit_group("read_light"))],
)
async def get_employee_v1(
    employee_id: str,
    scope=Depends(get_department_scope),
    service: EmployeeService = Depends(get_employee_service),
) -> EmployeeResponse:
    return await service.get(employee_id, scope)


@router.post(
    "",
    response_model=EmployeeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Tạo nhân viên phiên bản v1",
    dependencies=[Depends(rate_limit_group("mutation"))],
)
async def create_employee_v1(
    request: EmployeeCreate,
    response: Response,
    scope=Depends(get_department_scope),
    service: EmployeeService = Depends(get_employee_service),
) -> EmployeeResponse:
    created = await service.create(request, scope)
    response.headers["Location"] = f"/api/v1/employees/{created.id}"
    return created


@router.patch(
    "/{employee_id}",
    response_model=EmployeeResponse,
    summary="Cập nhật nhân viên phiên bản v1",
    dependencies=[Depends(rate_limit_group("mutation"))],
)
async def update_employee_v1(
    employee_id: str,
    request: EmployeeUpdate,
    scope=Depends(get_department_scope),
    service: EmployeeService = Depends(get_employee_service),
) -> EmployeeResponse:
    return await service.update(employee_id, request, scope)


@router.delete(
    "/{employee_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Xóa nhân viên phiên bản v1",
    dependencies=[Depends(rate_limit_group("mutation"))],
)
async def delete_employee_v1(
    employee_id: str,
    scope=Depends(get_department_scope),
    service: EmployeeService = Depends(get_employee_service),
) -> None:
    await service.delete(employee_id, scope)
