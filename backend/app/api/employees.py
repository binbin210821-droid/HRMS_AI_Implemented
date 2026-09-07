from fastapi import APIRouter, Depends, Query, status

from app.api.dependencies import get_department_scope
from app.core.database import get_mongo_database
from app.core.time import BusinessClock
from app.models.employee import EmployeeCreate, EmployeeResponse, EmployeeUpdate
from app.repositories.employee_repository import EmployeeRepository
from app.services.employee_service import EmployeeService

router = APIRouter(prefix="/api/employees", tags=["Employees"])


def get_employee_service() -> EmployeeService:
    return EmployeeService(
        EmployeeRepository(get_mongo_database().get_database()), clock=BusinessClock()
    )


@router.get("", response_model=list[EmployeeResponse], summary="Danh sách nhân viên")
async def list_employees(
    department_id: str | None = Query(default=None),
    scope=Depends(get_department_scope),
    service: EmployeeService = Depends(get_employee_service),
) -> list[EmployeeResponse]:
    return await service.list(scope, department_id)


@router.get("/{employee_id}", response_model=EmployeeResponse, summary="Chi tiết nhân viên")
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
)
async def create_employee(
    request: EmployeeCreate,
    scope=Depends(get_department_scope),
    service: EmployeeService = Depends(get_employee_service),
) -> EmployeeResponse:
    return await service.create(request, scope)


@router.patch("/{employee_id}", response_model=EmployeeResponse, summary="Cập nhật nhân viên")
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
)
async def delete_employee(
    employee_id: str,
    scope=Depends(get_department_scope),
    service: EmployeeService = Depends(get_employee_service),
) -> None:
    await service.delete(employee_id, scope)
