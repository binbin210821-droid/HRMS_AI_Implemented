from fastapi import APIRouter, Depends, Response, status

from app.api.departments import get_department_service
from app.api.dependencies import get_department_scope, require_role
from app.core.pagination import ListQueryParams, PageResponse
from app.infrastructure.rate_limit import rate_limit_group
from app.models.department import DepartmentCreate, DepartmentResponse, DepartmentUpdate
from app.models.user import CurrentUser, UserRole
from app.services.department_service import DepartmentService

router = APIRouter(prefix="/departments", tags=["Departments v1"])


@router.get(
    "",
    response_model=PageResponse[DepartmentResponse],
    summary="Danh sách phòng ban phiên bản v1",
    dependencies=[Depends(rate_limit_group("read_light"))],
)
async def list_departments_v1(
    pagination: ListQueryParams = Depends(),
    scope=Depends(get_department_scope),
    service: DepartmentService = Depends(get_department_service),
) -> PageResponse[DepartmentResponse]:
    page = await service.list_page_v1(scope, pagination.page, pagination.page_size)
    return PageResponse(
        items=page.items,
        page=pagination.page,
        page_size=pagination.page_size,
        total=page.total,
        has_next=pagination.page * pagination.page_size < page.total,
    )


@router.get(
    "/{department_id}",
    response_model=DepartmentResponse,
    summary="Chi tiết phòng ban phiên bản v1",
    dependencies=[Depends(rate_limit_group("read_light"))],
)
async def get_department_v1(
    department_id: str,
    scope=Depends(get_department_scope),
    service: DepartmentService = Depends(get_department_service),
) -> DepartmentResponse:
    return await service.get(department_id, scope)


@router.post(
    "",
    response_model=DepartmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Tạo phòng ban phiên bản v1",
    dependencies=[Depends(rate_limit_group("mutation"))],
)
async def create_department_v1(
    request: DepartmentCreate,
    response: Response,
    _: CurrentUser = Depends(require_role(UserRole.LEADERSHIP)),
    service: DepartmentService = Depends(get_department_service),
) -> DepartmentResponse:
    created = await service.create(request)
    response.headers["Location"] = f"/api/v1/departments/{created.id}"
    return created


@router.patch(
    "/{department_id}",
    response_model=DepartmentResponse,
    summary="Cập nhật phòng ban phiên bản v1",
    dependencies=[Depends(rate_limit_group("mutation"))],
)
async def update_department_v1(
    department_id: str,
    request: DepartmentUpdate,
    _: CurrentUser = Depends(require_role(UserRole.LEADERSHIP)),
    service: DepartmentService = Depends(get_department_service),
) -> DepartmentResponse:
    return await service.update(department_id, request)


@router.delete(
    "/{department_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Xóa phòng ban phiên bản v1",
    dependencies=[Depends(rate_limit_group("mutation"))],
)
async def delete_department_v1(
    department_id: str,
    _: CurrentUser = Depends(require_role(UserRole.LEADERSHIP)),
    service: DepartmentService = Depends(get_department_service),
) -> None:
    await service.delete(department_id)
