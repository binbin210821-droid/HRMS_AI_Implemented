from typing import Literal

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.ai import get_ai_service
from app.api.dependencies import get_current_user, get_department_scope, require_role
from app.api.tasks import get_task_service, list_department_task_directives
from app.api.v1._query import build_sort_stage, validate_date_range
from app.core.database import get_mongo_database
from app.core.pagination import DateRangeParams, ListQueryParams, PageResponse
from app.core.time import BusinessClock
from app.infrastructure.idempotency import IdempotencyContext, complete_idempotency, idempotent
from app.infrastructure.rate_limit import rate_limit_group
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
from app.models.task_planning import OverdueTaskPlanningResponse
from app.models.user import CurrentUser, UserRole
from app.repositories.performance_repository import PerformanceRepository
from app.repositories.task_repository import TaskRepository
from app.services.ai_service import AiService
from app.services.task_action_planning_service import TaskActionPlanningService
from app.services.task_service import TaskService

router = APIRouter(prefix="/tasks", tags=["Tasks v1"])


def get_task_action_planning_service() -> TaskActionPlanningService:
    database = get_mongo_database().get_database()
    return TaskActionPlanningService(
        TaskRepository(database), PerformanceRepository(database), BusinessClock()
    )


@router.post(
    "/{task_id}/ai-proposal",
    response_model=OverdueTaskPlanningResponse,
    summary="Đề xuất xử lý công việc quá hạn bằng AI",
    dependencies=[Depends(rate_limit_group("ai_chat"))],
)
async def get_overdue_task_ai_proposal_v1(
    task_id: str,
    scope=Depends(get_department_scope),
    current_user: CurrentUser = Depends(require_role(UserRole.MANAGER)),
    task_service: TaskService = Depends(get_task_service),
    planning_service: TaskActionPlanningService = Depends(get_task_action_planning_service),
    ai_service: AiService = Depends(get_ai_service),
) -> OverdueTaskPlanningResponse:
    task = await task_service.get(task_id, scope)
    plan = await planning_service.build_plan(task, scope)
    return await ai_service.generate_overdue_task_action_proposal(plan, scope, current_user.user_id)


@router.get(
    "",
    response_model=PageResponse[TaskResponse],
    summary="Danh sách công việc phiên bản v1",
    dependencies=[Depends(rate_limit_group("read_operational"))],
)
async def list_tasks_v1(
    pagination: ListQueryParams = Depends(),
    date_range: DateRangeParams = Depends(),
    employee_id: str | None = Query(default=None),
    department_id: str | None = Query(default=None),
    task_status: TaskStatus | None = Query(default=None, alias="status"),
    overdue_only: bool = Query(default=False),
    scope=Depends(get_department_scope),
    _: CurrentUser = Depends(get_current_user),
    service: TaskService = Depends(get_task_service),
) -> PageResponse[TaskResponse]:
    validate_date_range(date_range.from_date, date_range.to_date)
    page = await service.list_page_v1(
        scope,
        employee_id,
        department_id,
        task_status,
        overdue_only,
        date_range.from_date,
        date_range.to_date,
        build_sort_stage(
            pagination.sort,
            {"due_date", "created_at", "priority", "status"},
            "due_date",
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
    "/leadership-overview",
    response_model=LeadershipTaskOverviewResponse,
    summary="Tổng quan công việc theo phòng ban phiên bản v1",
    dependencies=[Depends(rate_limit_group("read_heavy"))],
)
async def get_leadership_overview_v1(
    range_preset: Literal["7d", "30d", "90d"] = Query(default="30d", alias="range"),
    _: CurrentUser = Depends(require_role(UserRole.LEADERSHIP)),
    service: TaskService = Depends(get_task_service),
) -> LeadershipTaskOverviewResponse:
    return await service.leadership_overview(range_preset)


@router.get(
    "/departments/{department_id}/portfolio",
    response_model=DepartmentTaskPortfolioResponse,
    summary="Danh mục công việc phòng ban cho Lãnh đạo phiên bản v1",
    dependencies=[Depends(rate_limit_group("read_heavy"))],
)
async def get_department_portfolio_v1(
    department_id: str,
    range_preset: Literal["7d", "30d", "90d"] = Query(default="30d", alias="range"),
    focus: Literal["all", "overdue", "not_directed", "due_soon", "high_priority_open", "at_risk"] = Query(
        default="all"
    ),
    _: CurrentUser = Depends(require_role(UserRole.LEADERSHIP)),
    service: TaskService = Depends(get_task_service),
) -> DepartmentTaskPortfolioResponse:
    return await service.department_portfolio(department_id, range_preset, focus)


@router.post(
    "/department-directives/{department_id}",
    response_model=DepartmentTaskDirectiveResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ra chỉ thị công việc cho phòng ban phiên bản v1",
    dependencies=[Depends(rate_limit_group("directive_action"))],
)
async def issue_department_task_directive_v1(
    department_id: str,
    request: IssueDepartmentTaskDirectiveRequest,
    current_user: CurrentUser = Depends(require_role(UserRole.LEADERSHIP)),
    service: TaskService = Depends(get_task_service),
    idempotency: IdempotencyContext | None = Depends(idempotent("task_directive")),
) -> DepartmentTaskDirectiveResponse:
    result = await service.issue_department_directive(
        department_id, current_user.user_id, request
    )
    await complete_idempotency(idempotency, result, status_code=status.HTTP_201_CREATED)
    return result


# Phải đăng ký path tĩnh trước `/{task_id}`. Hàm legacy được tái sử dụng để
# giữ nguyên payload list + pagination headers mà các caller compatibility đang dùng.
router.add_api_route(
    "/department-directives",
    list_department_task_directives,
    methods=["GET"],
    response_model=list[DepartmentTaskDirectiveResponse],
    name="list_department_task_directives_v1",
    summary="Danh sách chỉ thị công việc cấp phòng ban phiên bản v1",
    dependencies=[Depends(rate_limit_group("read_light"))],
)


@router.get(
    "/{task_id}",
    response_model=TaskResponse,
    summary="Chi tiết công việc phiên bản v1",
    dependencies=[Depends(rate_limit_group("read_heavy"))],
)
async def get_task_v1(
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
    summary="Tạo công việc phiên bản v1",
    dependencies=[Depends(rate_limit_group("mutation"))],
)
async def create_task_v1(
    request: TaskCreate,
    response: Response,
    scope=Depends(get_department_scope),
    current_user: CurrentUser = Depends(require_role(UserRole.MANAGER)),
    service: TaskService = Depends(get_task_service),
) -> TaskResponse:
    created = await service.create(request, scope, current_user.user_id)
    response.headers["Location"] = f"/api/v1/tasks/{created.id}"
    return created


@router.patch(
    "/{task_id}",
    response_model=TaskResponse,
    summary="Cập nhật công việc phiên bản v1",
    dependencies=[Depends(rate_limit_group("mutation"))],
)
async def update_task_v1(
    task_id: str,
    request: TaskUpdate,
    scope=Depends(get_department_scope),
    current_user: CurrentUser = Depends(require_role(UserRole.MANAGER)),
    service: TaskService = Depends(get_task_service),
) -> TaskResponse:
    return await service.update(task_id, request, scope, current_user.user_id)


@router.delete(
    "/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Xóa công việc phiên bản v1",
    dependencies=[Depends(rate_limit_group("mutation"))],
)
async def delete_task_v1(
    task_id: str,
    scope=Depends(get_department_scope),
    _: CurrentUser = Depends(require_role(UserRole.MANAGER)),
    service: TaskService = Depends(get_task_service),
) -> None:
    await service.delete(task_id, scope)


@router.post(
    "/department-directives/{directive_id}/acknowledgements",
    response_model=DepartmentTaskDirectiveResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Xác nhận chỉ thị công việc phiên bản v1",
    dependencies=[Depends(rate_limit_group("directive_action"))],
)
async def acknowledge_department_task_directive_resource_v1(
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
    "/department-directives/{directive_id}/submissions",
    response_model=DepartmentTaskDirectiveResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Gửi nghiệm thu chỉ thị công việc phiên bản v1",
    dependencies=[Depends(rate_limit_group("directive_action"))],
)
async def submit_department_task_directive_resource_v1(
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
    "/department-directives/{directive_id}/acceptances",
    response_model=DepartmentTaskDirectiveResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Nghiệm thu chỉ thị công việc phiên bản v1",
    dependencies=[Depends(rate_limit_group("directive_action"))],
)
async def accept_department_task_directive_resource_v1(
    directive_id: str,
    request: ReviewDepartmentTaskDirectiveRequest,
    current_user: CurrentUser = Depends(require_role(UserRole.LEADERSHIP)),
    service: TaskService = Depends(get_task_service),
) -> DepartmentTaskDirectiveResponse:
    return await service.accept_department_directive(directive_id, current_user.user_id, request)


@router.post(
    "/department-directives/{directive_id}/revision-requests",
    response_model=DepartmentTaskDirectiveResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Yêu cầu xử lý lại chỉ thị công việc phiên bản v1",
    dependencies=[Depends(rate_limit_group("directive_action"))],
)
async def request_task_directive_revision_resource_v1(
    directive_id: str,
    request: ReviewDepartmentTaskDirectiveRequest,
    current_user: CurrentUser = Depends(require_role(UserRole.LEADERSHIP)),
    service: TaskService = Depends(get_task_service),
) -> DepartmentTaskDirectiveResponse:
    return await service.request_department_directive_revision(
        directive_id, current_user.user_id, request
    )
