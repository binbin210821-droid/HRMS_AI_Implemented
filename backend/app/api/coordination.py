from fastapi import APIRouter, Depends, Query, status

from app.api.dependencies import get_current_user, get_department_scope, require_role
from app.core.database import get_mongo_database
from app.core.time import BusinessClock
from app.models.coordination import (
    AcknowledgeDepartmentAlertDirectiveRequest,
    ApplyCoordinationRequest,
    CoordinationDirectiveResponse,
    CoordinationPlanResponse,
    CoordinationSuggestionResponse,
    DepartmentAlertDirectiveResponse,
    DirectiveTargetResponse,
    FulfillDirectiveRequest,
    IssueDepartmentAlertDirectiveRequest,
    IssueDirectiveRequest,
    ReviewDepartmentAlertDirectiveRequest,
    SubmitDepartmentAlertDirectiveRequest,
)
from app.models.overload import WorkloadCandidateResponse
from app.models.user import CurrentUser, UserRole
from app.repositories.coordination_repository import CoordinationRepository
from app.repositories.department_repository import DepartmentRepository
from app.services.coordination_service import CoordinationService

router = APIRouter(prefix="/api/coordination", tags=["Coordination"])


def get_service() -> CoordinationService:
    database = get_mongo_database().get_database()
    return CoordinationService(
        CoordinationRepository(database),
        department_repository=DepartmentRepository(database),
        clock=BusinessClock(),
    )


@router.get(
    "/suggestions",
    response_model=list[CoordinationSuggestionResponse],
    summary="Danh sách gợi ý điều phối trong phạm vi",
)
async def list_coordination_suggestions(
    scope=Depends(get_department_scope),
    _: CurrentUser = Depends(get_current_user),
    service: CoordinationService = Depends(get_service),
) -> list[CoordinationSuggestionResponse]:
    return await service.list_suggestions(scope)


@router.post(
    "/alerts/{alert_id}/apply",
    response_model=CoordinationPlanResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Áp dụng hoặc chỉnh sửa gợi ý điều phối",
)
async def apply_coordination(
    alert_id: str,
    request: ApplyCoordinationRequest,
    scope=Depends(get_department_scope),
    current_user: CurrentUser = Depends(get_current_user),
    service: CoordinationService = Depends(get_service),
) -> CoordinationPlanResponse:
    return await service.apply(alert_id, scope, current_user.user_id, request)


@router.post(
    "/department-directives/{department_id}",
    response_model=DepartmentAlertDirectiveResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Phát hành chỉ thị cảnh báo cấp phòng ban",
)
async def issue_department_alert_directive(
    department_id: str,
    request: IssueDepartmentAlertDirectiveRequest,
    current_user: CurrentUser = Depends(require_role(UserRole.LEADERSHIP)),
    service: CoordinationService = Depends(get_service),
) -> DepartmentAlertDirectiveResponse:
    return await service.issue_department_directive(department_id, current_user.user_id, request)


@router.get(
    "/department-directives",
    response_model=list[DepartmentAlertDirectiveResponse],
    summary="Danh sách chỉ thị cảnh báo cấp phòng ban",
)
async def list_department_alert_directives(
    directive_status: str | None = Query(default=None, alias="status"),
    scope=Depends(get_department_scope),
    _: CurrentUser = Depends(get_current_user),
    service: CoordinationService = Depends(get_service),
) -> list[DepartmentAlertDirectiveResponse]:
    return await service.list_department_directives(scope, directive_status)


@router.post(
    "/department-directives/{directive_id}/acknowledge",
    response_model=DepartmentAlertDirectiveResponse,
    summary="Manager xác nhận chỉ thị cảnh báo cấp phòng ban",
)
async def acknowledge_department_alert_directive(
    directive_id: str,
    request: AcknowledgeDepartmentAlertDirectiveRequest,
    scope=Depends(get_department_scope),
    current_user: CurrentUser = Depends(get_current_user),
    service: CoordinationService = Depends(get_service),
) -> DepartmentAlertDirectiveResponse:
    return await service.acknowledge_department_directive(
        directive_id, scope, current_user.user_id, request
    )


@router.post(
    "/department-directives/{directive_id}/submit",
    response_model=DepartmentAlertDirectiveResponse,
    summary="Manager gửi nghiệm thu chỉ thị cảnh báo",
)
async def submit_department_alert_directive(
    directive_id: str,
    request: SubmitDepartmentAlertDirectiveRequest,
    scope=Depends(get_department_scope),
    current_user: CurrentUser = Depends(get_current_user),
    service: CoordinationService = Depends(get_service),
) -> DepartmentAlertDirectiveResponse:
    return await service.submit_department_directive(
        directive_id, scope, current_user.user_id, request
    )


@router.post(
    "/department-directives/{directive_id}/accept",
    response_model=DepartmentAlertDirectiveResponse,
    summary="Lãnh đạo nghiệm thu chỉ thị cảnh báo",
)
async def accept_department_alert_directive(
    directive_id: str,
    request: ReviewDepartmentAlertDirectiveRequest,
    current_user: CurrentUser = Depends(require_role(UserRole.LEADERSHIP)),
    service: CoordinationService = Depends(get_service),
) -> DepartmentAlertDirectiveResponse:
    return await service.accept_department_directive(
        directive_id, current_user.user_id, request
    )


@router.post(
    "/department-directives/{directive_id}/request-revision",
    response_model=DepartmentAlertDirectiveResponse,
    summary="Yêu cầu xử lý lại chỉ thị cảnh báo",
)
async def request_alert_directive_revision(
    directive_id: str,
    request: ReviewDepartmentAlertDirectiveRequest,
    current_user: CurrentUser = Depends(require_role(UserRole.LEADERSHIP)),
    service: CoordinationService = Depends(get_service),
) -> DepartmentAlertDirectiveResponse:
    return await service.request_department_directive_revision(
        directive_id, current_user.user_id, request
    )


@router.get(
    "/alerts/{alert_id}/directive-targets",
    response_model=list[DirectiveTargetResponse],
    summary="Deprecated: danh sách đích của flow điều phối cũ; thay bằng chỉ thị cấp phòng ban qua /api/coordination/department-directives",
    deprecated=True,
)
async def list_directive_targets(
    alert_id: str,
    current_user: CurrentUser = Depends(require_role(UserRole.LEADERSHIP)),
    service: CoordinationService = Depends(get_service),
) -> list[DirectiveTargetResponse]:
    return await service.list_directive_targets(alert_id, current_user.user_id)


@router.post(
    "/alerts/{alert_id}/direct",
    response_model=CoordinationDirectiveResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Deprecated: flow điều phối cá nhân cũ; thay bằng chỉ thị cấp phòng ban qua /api/coordination/department-directives",
    deprecated=True,
)
async def issue_directive(
    alert_id: str,
    request: IssueDirectiveRequest,
    current_user: CurrentUser = Depends(require_role(UserRole.LEADERSHIP)),
    service: CoordinationService = Depends(get_service),
) -> CoordinationDirectiveResponse:
    return await service.issue_directive(alert_id, current_user.user_id, request)


@router.get(
    "/directives",
    response_model=list[CoordinationDirectiveResponse],
    summary="Danh sách chỉ thị điều phối",
)
async def list_directives(
    directive_status: str | None = Query(default=None, alias="status"),
    scope=Depends(get_department_scope),
    _: CurrentUser = Depends(get_current_user),
    service: CoordinationService = Depends(get_service),
) -> list[CoordinationDirectiveResponse]:
    return await service.list_directives(scope, directive_status)


@router.get(
    "/directives/{directive_id}/candidates",
    response_model=list[WorkloadCandidateResponse],
    summary="Danh sách ứng viên tiếp nhận chỉ thị điều phối",
)
async def list_directive_candidates(
    directive_id: str,
    scope=Depends(get_department_scope),
    _: CurrentUser = Depends(get_current_user),
    service: CoordinationService = Depends(get_service),
) -> list[WorkloadCandidateResponse]:
    return await service.list_directive_candidates(directive_id, scope)


@router.post(
    "/directives/{directive_id}/fulfill",
    response_model=CoordinationPlanResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Manager tiếp nhận chỉ thị điều phối",
)
async def fulfill_directive(
    directive_id: str,
    request: FulfillDirectiveRequest,
    scope=Depends(get_department_scope),
    current_user: CurrentUser = Depends(get_current_user),
    service: CoordinationService = Depends(get_service),
) -> CoordinationPlanResponse:
    return await service.fulfill_directive(directive_id, scope, current_user.user_id, request)


__all__ = ["router"]
