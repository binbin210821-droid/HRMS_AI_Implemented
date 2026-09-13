from fastapi import APIRouter, Depends, Query, Request, Response, status

from app.api.dependencies import get_department_scope
from app.core.database import get_mongo_database
from app.core.pagination import PaginationParams, get_pagination, paginate_v1
from app.core.time import BusinessClock
from app.infrastructure.rate_limit import rate_limit_group
from app.models.employee import EmployeeCreate, EmployeeResponse, EmployeeUpdate
from app.repositories.employee_repository import EmployeeRepository
from app.services.employee_service import EmployeeService

router = APIRouter(prefix="/employees", tags=["Employees"])


def get_employee_service() -> EmployeeService:
    return EmployeeService(
        EmployeeRepository(get_mongo_database().get_database()), clock=BusinessClock()
    )


@router.get(
    "",
    response_model=list[EmployeeResponse],
    summary="Danh sách nhân viên",
    dependencies=[Depends(rate_limit_group("read_light"))],
)
async def list_employees(
    request: Request,
    response: Response,
    department_id: str | None = Query(default=None),
    pagination: PaginationParams = Depends(get_pagination),
    scope=Depends(get_department_scope),
    service: EmployeeService = Depends(get_employee_service),
) -> list[EmployeeResponse]:
    if request.url.path.startswith("/api/v1/"):
        return paginate_v1(
            request,
            response,
            await service.list_page(scope, department_id, pagination.offset, pagination.limit),
            pagination,
        )
    return paginate_v1(request, response, await service.list(scope, department_id), pagination)


@router.get(
    "/{employee_id}",
    response_model=EmployeeResponse,
    summary="Chi tiết nhân viên",
    dependencies=[Depends(rate_limit_group("read_light"))],
)
async def get_employee(
    employee_id: str,
    scope=Depends(get_department_scope),
    service: EmployeeService = Depends(get_employee_service),
) -> EmployeeResponse:
    return await service.get(employee_id, scope)


@router.post(
    "",
    response_model=EmployeeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Tạo nhân viên",
    dependencies=[Depends(rate_limit_group("mutation"))],
)
async def create_employee(
    request: EmployeeCreate,
    scope=Depends(get_department_scope),
    service: EmployeeService = Depends(get_employee_service),
) -> EmployeeResponse:
    return await service.create(request, scope)


@router.patch(
    "/{employee_id}",
    response_model=EmployeeResponse,
    summary="Cập nhật nhân viên",
    dependencies=[Depends(rate_limit_group("mutation"))],
)
async def update_employee(
    employee_id: str,
    request: EmployeeUpdate,
    scope=Depends(get_department_scope),
    service: EmployeeService = Depends(get_employee_service),
) -> EmployeeResponse:
    return await service.update(employee_id, request, scope)


@router.delete(
    "/{employee_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Xóa nhân viên",
    dependencies=[Depends(rate_limit_group("mutation"))],
)
async def delete_employee(
    employee_id: str,
    scope=Depends(get_department_scope),
    service: EmployeeService = Depends(get_employee_service),
) -> None:
    await service.delete(employee_id, scope)
