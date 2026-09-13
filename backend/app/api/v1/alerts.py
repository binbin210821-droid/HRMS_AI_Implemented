from fastapi import APIRouter, Depends, Query

from app.api.ai import get_ai_service
from app.api.alerts import get_alert_service
from app.api.coordination import get_service as get_coordination_service
from app.api.dependencies import get_current_user, get_department_scope, require_role
from app.api.v1._query import build_sort_stage, validate_date_range
from app.core.pagination import DateRangeParams, ListQueryParams, PageResponse
from app.infrastructure.rate_limit import rate_limit_group
from app.models.ai_proposal import AiAlertProposalResponse
from app.models.alert import AlertResolveRequest, AlertResolveV1Request, AlertResponse
from app.models.coordination import (
    AcknowledgeDepartmentAlertDirectiveRequest,
    DepartmentAlertDirectiveResponse,
    ReviewDepartmentAlertDirectiveRequest,
    SubmitDepartmentAlertDirectiveRequest,
)
from app.models.user import CurrentUser, UserRole
from app.services.ai_service import AiService
from app.services.alert_service import EarlyWarningService
from app.services.coordination_service import CoordinationService

router = APIRouter(prefix="/alerts", tags=["Alerts v1"])


@router.get(
    "",
    response_model=PageResponse[AlertResponse],
    summary="Danh sách cảnh báo phiên bản v1",
    dependencies=[Depends(rate_limit_group("read_operational"))],
)
async def list_alerts_v1(
    pagination: ListQueryParams = Depends(),
    date_range: DateRangeParams = Depends(),
    status: str | None = Query(default=None),
    alert_type: str | None = Query(default="all"),
    department_id: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    scope=Depends(get_department_scope),
    _: CurrentUser = Depends(get_current_user),
    service: EarlyWarningService = Depends(get_alert_service),
) -> PageResponse[AlertResponse]:
    validate_date_range(date_range.from_date, date_range.to_date)
    normalized_type = None if alert_type in (None, "all") else alert_type
    page = await service.list_alerts_page_v1(
        scope,
        department_id,
        status,
        normalized_type,
        severity,
        date_range.from_date,
        date_range.to_date,
        build_sort_stage(pagination.sort, {"created_at", "severity", "status"}, "created_at", -1),
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


@router.patch(
    "/{alert_id}",
    response_model=AlertResponse,
    summary="Đánh dấu cảnh báo đã xử lý phiên bản v1",
    dependencies=[Depends(rate_limit_group("mutation"))],
)
async def resolve_alert_v1(
    alert_id: str,
    request: AlertResolveV1Request,
    scope=Depends(get_department_scope),
    current_user: CurrentUser = Depends(get_current_user),
    service: EarlyWarningService = Depends(get_alert_service),
) -> AlertResponse:
    return await service.resolve(
        alert_id,
        scope,
        current_user.user_id,
        AlertResolveRequest(resolution_note=request.resolution_note),
    )


@router.post(
    "/{alert_id}/ai-proposal",
    response_model=AiAlertProposalResponse,
    summary="Đề xuất phương án xử lý cảnh báo bằng AI",
    dependencies=[Depends(rate_limit_group("ai_chat"))],
)
async def get_alert_ai_proposal_v1(
    alert_id: str,
    scope=Depends(get_department_scope),
    current_user: CurrentUser = Depends(require_role(UserRole.MANAGER)),
    coordination_service: CoordinationService = Depends(get_coordination_service),
    ai_service: AiService = Depends(get_ai_service),
) -> AiAlertProposalResponse:
    alert, candidates = await coordination_service.get_rebalance_candidates_for_alert(
        alert_id, scope
    )
    return await ai_service.generate_alert_action_proposal(
        alert, scope, candidates, current_user.user_id
    )


@router.post(
    "/department-directives/{directive_id}/acknowledgements",
    response_model=DepartmentAlertDirectiveResponse,
    status_code=201,
    summary="Xác nhận chỉ thị cảnh báo phiên bản v1",
    dependencies=[Depends(rate_limit_group("directive_action"))],
)
async def acknowledge_department_alert_directive_resource_v1(
    directive_id: str,
    request: AcknowledgeDepartmentAlertDirectiveRequest,
    scope=Depends(get_department_scope),
    current_user: CurrentUser = Depends(get_current_user),
    service: CoordinationService = Depends(get_coordination_service),
) -> DepartmentAlertDirectiveResponse:
    return await service.acknowledge_department_directive(
        directive_id, scope, current_user.user_id, request
    )


@router.post(
    "/department-directives/{directive_id}/submissions",
    response_model=DepartmentAlertDirectiveResponse,
    status_code=201,
    summary="Gửi nghiệm thu chỉ thị cảnh báo phiên bản v1",
    dependencies=[Depends(rate_limit_group("directive_action"))],
)
async def submit_department_alert_directive_resource_v1(
    directive_id: str,
    request: SubmitDepartmentAlertDirectiveRequest,
    scope=Depends(get_department_scope),
    current_user: CurrentUser = Depends(get_current_user),
    service: CoordinationService = Depends(get_coordination_service),
) -> DepartmentAlertDirectiveResponse:
    return await service.submit_department_directive(
        directive_id, scope, current_user.user_id, request
    )


@router.post(
    "/department-directives/{directive_id}/acceptances",
    response_model=DepartmentAlertDirectiveResponse,
    status_code=201,
    summary="Nghiệm thu chỉ thị cảnh báo phiên bản v1",
    dependencies=[Depends(rate_limit_group("directive_action"))],
)
async def accept_department_alert_directive_resource_v1(
    directive_id: str,
    request: ReviewDepartmentAlertDirectiveRequest,
    current_user: CurrentUser = Depends(require_role(UserRole.LEADERSHIP)),
    service: CoordinationService = Depends(get_coordination_service),
) -> DepartmentAlertDirectiveResponse:
    return await service.accept_department_directive(directive_id, current_user.user_id, request)


@router.post(
    "/department-directives/{directive_id}/revision-requests",
    response_model=DepartmentAlertDirectiveResponse,
    status_code=201,
    summary="Yêu cầu xử lý lại chỉ thị cảnh báo phiên bản v1",
    dependencies=[Depends(rate_limit_group("directive_action"))],
)
async def request_alert_directive_revision_resource_v1(
    directive_id: str,
    request: ReviewDepartmentAlertDirectiveRequest,
    current_user: CurrentUser = Depends(require_role(UserRole.LEADERSHIP)),
    service: CoordinationService = Depends(get_coordination_service),
) -> DepartmentAlertDirectiveResponse:
    return await service.request_department_directive_revision(
        directive_id, current_user.user_id, request
    )
