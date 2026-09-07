from typing import Literal

from fastapi import APIRouter, Depends, Query, status

from app.api.dependencies import get_current_user, get_department_scope, require_role
from app.core.database import get_mongo_database
from app.core.time import BusinessClock
from app.models.task import (
    AcknowledgeDepartmentTaskDirectiveRequest,
    DepartmentTaskDirectiveResponse,
    DepartmentTaskPortfolioResponse,
    IssueDepartmentTaskDirectiveRequest,
    LeadershipTaskOverviewResponse,
    ReviewDepartmentTaskDirectiveRequest,
    SubmitDepartmentTaskDirectiveRequest,
    TaskCreate,
    TaskResponse,
    TaskStatus,
    TaskUpdate,
)
from app.models.user import CurrentUser, UserRole
from app.repositories.task_repository import TaskRepository
from app.services.task_service import TaskService

router = APIRouter(prefix="/api/tasks", tags=["Tasks"])


def get_task_service() -> TaskService:
    return TaskService(TaskRepository(get_mongo_database().get_database()), clock=BusinessClock())


@router.get("", response_model=list[TaskResponse], summary="Danh sách công việc")
async def list_tasks(
    employee_id: str | None = Query(default=None),
    task_status: TaskStatus | None = Query(default=None, alias="status"),
    overdue_only: bool = Query(default=False),
    scope=Depends(get_department_scope),
    _: CurrentUser = Depends(get_current_user),
    service: TaskService = Depends(get_task_service),
) -> list[TaskResponse]:
    return await service.list(scope, employee_id, task_status, overdue_only)


@router.get(
    "/leadership-overview",
    response_model=LeadershipTaskOverviewResponse,
    summary="Tổng quan công việc theo phòng ban",
)
async def get_leadership_overview(
    range_preset: Literal["7d", "30d", "90d"] = Query(default="30d", alias="range"),
    _: CurrentUser = Depends(require_role(UserRole.LEADERSHIP)),
    service: TaskService = Depends(get_task_service),
) -> LeadershipTaskOverviewResponse:
    return await service.leadership_overview(range_preset)


@router.get(
    "/departments/{department_id}/portfolio",
    response_model=DepartmentTaskPortfolioResponse,
    summary="Danh mục công việc phòng ban cho Lãnh đạo",
)
async def get_department_portfolio(
    department_id: str,
    range_preset: Literal["7d", "30d", "90d"] = Query(default="30d", alias="range"),
    focus: Literal["all", "overdue", "due_soon", "high_priority_open", "at_risk"] = Query(
        default="all"
    ),
    _: CurrentUser = Depends(require_role(UserRole.LEADERSHIP)),
    service: TaskService = Depends(get_task_service),
) -> DepartmentTaskPortfolioResponse:
    return await service.department_portfolio(department_id, range_preset, focus)


@router.get(
    "/department-directives",
    response_model=list[DepartmentTaskDirectiveResponse],
    summary="Danh sách chỉ thị công việc cấp phòng ban",
)
async def list_department_task_directives(
    directive_status: Literal[
        "pending", "acknowledged", "submitted", "accepted", "needs_revision"
    ]
    | None = Query(
        default=None, alias="status"
    ),
    scope=Depends(get_department_scope),
    _: CurrentUser = Depends(get_current_user),
    service: TaskService = Depends(get_task_service),
) -> list[DepartmentTaskDirectiveResponse]:
    return await service.list_department_directives(scope, directive_status)


@router.post(
    "/department-directives/{department_id}",
    response_model=DepartmentTaskDirectiveResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ra chỉ thị công việc cho phòng ban",
)
async def issue_department_task_directive(
    department_id: str,
    request: IssueDepartmentTaskDirectiveRequest,
    current_user: CurrentUser = Depends(require_role(UserRole.LEADERSHIP)),
    service: TaskService = Depends(get_task_service),
) -> DepartmentTaskDirectiveResponse:
    return await service.issue_department_directive(
        department_id, current_user.user_id, request
    )


@router.post(
    "/department-directives/{directive_id}/acknowledge",
    response_model=DepartmentTaskDirectiveResponse,
    summary="Xác nhận chỉ thị công việc cấp phòng ban",
)
async def acknowledge_department_task_directive(
    directive_id: str,
    request: AcknowledgeDepartmentTaskDirectiveRequest,
    scope=Depends(get_department_scope),
    current_user: CurrentUser = Depends(get_current_user),
    service: TaskService = Depends(get_task_service),
) -> DepartmentTaskDirectiveResponse:
    return await service.acknowledge_department_directive(
        directive_id, scope, current_user.user_id, request
    )


@router.post(
    "/department-directives/{directive_id}/submit",
    response_model=DepartmentTaskDirectiveResponse,
    summary="Manager gửi nghiệm thu chỉ thị công việc",
)
async def submit_department_task_directive(
    directive_id: str,
    request: SubmitDepartmentTaskDirectiveRequest,
    scope=Depends(get_department_scope),
    current_user: CurrentUser = Depends(get_current_user),
    service: TaskService = Depends(get_task_service),
) -> DepartmentTaskDirectiveResponse:
    return await service.submit_department_directive(
        directive_id, scope, current_user.user_id, request
    )


@router.post(
    "/department-directives/{directive_id}/accept",
    response_model=DepartmentTaskDirectiveResponse,
    summary="Lãnh đạo nghiệm thu chỉ thị công việc",
)
async def accept_department_task_directive(
    directive_id: str,
    request: ReviewDepartmentTaskDirectiveRequest,
    current_user: CurrentUser = Depends(require_role(UserRole.LEADERSHIP)),
    service: TaskService = Depends(get_task_service),
) -> DepartmentTaskDirectiveResponse:
    return await service.accept_department_directive(
        directive_id, current_user.user_id, request
    )


@router.post(
    "/department-directives/{directive_id}/request-revision",
    response_model=DepartmentTaskDirectiveResponse,
    summary="Yêu cầu xử lý lại chỉ thị công việc",
)
async def request_task_directive_revision(
    directive_id: str,
    request: ReviewDepartmentTaskDirectiveRequest,
    current_user: CurrentUser = Depends(require_role(UserRole.LEADERSHIP)),
    service: TaskService = Depends(get_task_service),
) -> DepartmentTaskDirectiveResponse:
    return await service.request_department_directive_revision(
        directive_id, current_user.user_id, request
    )


@router.get("/{task_id}", response_model=TaskResponse, summary="Chi tiết công việc")
async def get_task(
    task_id: str,
    scope=Depends(get_department_scope),
    _: CurrentUser = Depends(get_current_user),
    service: TaskService = Depends(get_task_service),
) -> TaskResponse:
    return await service.get(task_id, scope)


@router.post(
    "",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Tạo công việc",
)
async def create_task(
    request: TaskCreate,
    scope=Depends(get_department_scope),
    current_user: CurrentUser = Depends(require_role(UserRole.MANAGER)),
    service: TaskService = Depends(get_task_service),
) -> TaskResponse:
    return await service.create(request, scope, current_user.user_id)


@router.patch("/{task_id}", response_model=TaskResponse, summary="Cập nhật công việc")
async def update_task(
    task_id: str,
    request: TaskUpdate,
    scope=Depends(get_department_scope),
    _: CurrentUser = Depends(require_role(UserRole.MANAGER)),
    service: TaskService = Depends(get_task_service),
) -> TaskResponse:
    return await service.update(task_id, request, scope)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Xóa công việc")
async def delete_task(
    task_id: str,
    scope=Depends(get_department_scope),
    _: CurrentUser = Depends(require_role(UserRole.MANAGER)),
    service: TaskService = Depends(get_task_service),
) -> None:
    await service.delete(task_id, scope)
