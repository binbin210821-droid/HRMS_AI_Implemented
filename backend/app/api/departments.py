from fastapi import APIRouter, Depends, status

from app.api.dependencies import get_department_scope, require_role
from app.core.database import get_mongo_database
from app.core.time import BusinessClock
from app.models.department import DepartmentCreate, DepartmentResponse, DepartmentUpdate
from app.models.user import CurrentUser, UserRole
from app.repositories.department_repository import DepartmentRepository
from app.services.department_service import DepartmentService

router = APIRouter(prefix="/api/departments", tags=["Departments"])


def get_department_service() -> DepartmentService:
    return DepartmentService(
        DepartmentRepository(get_mongo_database().get_database()), clock=BusinessClock()
    )


@router.get("", response_model=list[DepartmentResponse], summary="Danh sách phòng ban")
async def list_departments(
    scope=Depends(get_department_scope),
    service: DepartmentService = Depends(get_department_service),
) -> list[DepartmentResponse]:
    return await service.list(scope)


@router.get("/{department_id}", response_model=DepartmentResponse, summary="Chi tiết phòng ban")
async def get_department(
    department_id: str,
    scope=Depends(get_department_scope),
    service: DepartmentService = Depends(get_department_service),
) -> DepartmentResponse:
    return await service.get(department_id, scope)


@router.post(
    "",
    response_model=DepartmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Tạo phòng ban",
)
async def create_department(
    request: DepartmentCreate,
    _: CurrentUser = Depends(require_role(UserRole.LEADERSHIP)),
    service: DepartmentService = Depends(get_department_service),
) -> DepartmentResponse:
    return await service.create(request)


@router.patch("/{department_id}", response_model=DepartmentResponse, summary="Cập nhật phòng ban")
async def update_department(
    department_id: str,
    request: DepartmentUpdate,
    _: CurrentUser = Depends(require_role(UserRole.LEADERSHIP)),
    service: DepartmentService = Depends(get_department_service),
) -> DepartmentResponse:
    return await service.update(department_id, request)


@router.delete(
    "/{department_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Xóa phòng ban",
)
async def delete_department(
    department_id: str,
    _: CurrentUser = Depends(require_role(UserRole.LEADERSHIP)),
    service: DepartmentService = Depends(get_department_service),
) -> None:
    await service.delete(department_id)
