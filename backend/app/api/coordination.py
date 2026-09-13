from fastapi import APIRouter, Depends, Query, Request, Response, status

from app.api.dependencies import get_current_user, get_department_scope, require_role
from app.core.database import get_mongo_database
from app.core.pagination import PaginationParams, get_pagination, paginate_v1
from app.core.time import BusinessClock
from app.infrastructure.idempotency import IdempotencyContext, complete_idempotency, idempotent
from app.infrastructure.rate_limit import rate_limit_group
from app.models.coordination import (
    AcknowledgeDepartmentAlertDirectiveRequest,
    ApplyCoordinationRequest,
    CoordinationDirectiveResponse,
    CoordinationPlanResponse,
    CoordinationSuggestionResponse,
    DepartmentAlertDirectiveResponse,
    FulfillDirectiveRequest,
    IssueDepartmentAlertDirectiveRequest,
    ReviewDepartmentAlertDirectiveRequest,
    SubmitDepartmentAlertDirectiveRequest,
)
from app.models.overload import WorkloadCandidateResponse
from app.models.user import CurrentUser, UserRole
from app.repositories.coordination_repository import CoordinationRepository
from app.repositories.department_repository import DepartmentRepository
from app.services.coordination_service import CoordinationService

router = APIRouter(prefix="/coordination", tags=["Coordination"])


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
    dependencies=[Depends(rate_limit_group("read_light"))],
)
async def list_coordination_suggestions(
    request: Request,
    response: Response,
    pagination: PaginationParams = Depends(get_pagination),
    scope=Depends(get_department_scope),
    _: CurrentUser = Depends(get_current_user),
    service: CoordinationService = Depends(get_service),
) -> list[CoordinationSuggestionResponse]:
    if request.url.path.startswith("/api/v1/"):
        return paginate_v1(
            request,
            response,
            await service.list_suggestions_page(scope, pagination.offset, pagination.limit),
            pagination,
        )
    return paginate_v1(request, response, await service.list_suggestions(scope), pagination)


@router.post(
    "/alerts/{alert_id}/plans",
    response_model=CoordinationPlanResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Áp dụng hoặc chỉnh sửa gợi ý điều phối",
    name="apply_coordination_v1",
    dependencies=[Depends(rate_limit_group("mutation"))],
)
@router.post(
    "/alerts/{alert_id}/apply",
    response_model=CoordinationPlanResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Deprecated: áp dụng hoặc chỉnh sửa gợi ý điều phối",
    deprecated=True,
    name="apply_coordination_legacy",
    dependencies=[Depends(rate_limit_group("mutation"))],
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
    dependencies=[Depends(rate_limit_group("directive_action"))],
)
async def issue_department_alert_directive(
    department_id: str,
    request: IssueDepartmentAlertDirectiveRequest,
    current_user: CurrentUser = Depends(require_role(UserRole.LEADERSHIP)),
    service: CoordinationService = Depends(get_service),
    idempotency: IdempotencyContext | None = Depends(idempotent("alert_directive")),
) -> DepartmentAlertDirectiveResponse:
    result = await service.issue_department_directive(department_id, current_user.user_id, request)
    await complete_idempotency(idempotency, result, status_code=201)
    return result


@router.get(
    "/department-directives",
    response_model=list[DepartmentAlertDirectiveResponse],
    summary="Danh sách chỉ thị cảnh báo cấp phòng ban",
    dependencies=[Depends(rate_limit_group("read_light"))],
)
async def list_department_alert_directives(
    request: Request,
    response: Response,
    directive_status: str | None = Query(default=None, alias="status"),
    pagination: PaginationParams = Depends(get_pagination),
    scope=Depends(get_department_scope),
    _: CurrentUser = Depends(get_current_user),
    service: CoordinationService = Depends(get_service),
) -> list[DepartmentAlertDirectiveResponse]:
    if request.url.path.startswith("/api/v1/"):
        return paginate_v1(
            request,
            response,
            await service.list_department_directives_page(
                scope, directive_status, pagination.offset, pagination.limit
            ),
            pagination,
        )
    return paginate_v1(
        request, response, await service.list_department_directives(scope, directive_status), pagination
    )


@router.patch(
    "/department-directives/{directive_id}/acknowledgement",
    response_model=DepartmentAlertDirectiveResponse,
    summary="Manager xác nhận chỉ thị cảnh báo cấp phòng ban",
    name="acknowledge_department_alert_directive_v1",
    dependencies=[Depends(rate_limit_group("directive_action"))],
)
@router.post(
    "/department-directives/{directive_id}/acknowledge",
    response_model=DepartmentAlertDirectiveResponse,
    summary="Deprecated: Manager xác nhận chỉ thị cảnh báo cấp phòng ban",
    deprecated=True,
    name="acknowledge_department_alert_directive_legacy",
    dependencies=[Depends(rate_limit_group("directive_action"))],
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


@router.patch(
    "/department-directives/{directive_id}/submission",
    response_model=DepartmentAlertDirectiveResponse,
    summary="Manager gửi nghiệm thu chỉ thị cảnh báo",
    name="submit_department_alert_directive_v1",
    dependencies=[Depends(rate_limit_group("directive_action"))],
)
@router.post(
    "/department-directives/{directive_id}/submit",
    response_model=DepartmentAlertDirectiveResponse,
    summary="Deprecated: Manager gửi nghiệm thu chỉ thị cảnh báo",
    deprecated=True,
    name="submit_department_alert_directive_legacy",
    dependencies=[Depends(rate_limit_group("directive_action"))],
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


@router.patch(
    "/department-directives/{directive_id}/acceptance",
    response_model=DepartmentAlertDirectiveResponse,
    summary="Lãnh đạo nghiệm thu chỉ thị cảnh báo",
    name="accept_department_alert_directive_v1",
    dependencies=[Depends(rate_limit_group("directive_action"))],
)
@router.post(
    "/department-directives/{directive_id}/accept",
    response_model=DepartmentAlertDirectiveResponse,
    summary="Deprecated: Lãnh đạo nghiệm thu chỉ thị cảnh báo",
    deprecated=True,
    name="accept_department_alert_directive_legacy",
    dependencies=[Depends(rate_limit_group("directive_action"))],
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


@router.patch(
    "/department-directives/{directive_id}/revision-request",
    response_model=DepartmentAlertDirectiveResponse,
    summary="Yêu cầu xử lý lại chỉ thị cảnh báo",
    name="request_alert_directive_revision_v1",
    dependencies=[Depends(rate_limit_group("directive_action"))],
)
@router.post(
    "/department-directives/{directive_id}/request-revision",
    response_model=DepartmentAlertDirectiveResponse,
    summary="Deprecated: yêu cầu xử lý lại chỉ thị cảnh báo",
    deprecated=True,
    name="request_alert_directive_revision_legacy",
    dependencies=[Depends(rate_limit_group("directive_action"))],
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
    "/directives",
    response_model=list[CoordinationDirectiveResponse],
    summary="Danh sách chỉ thị điều phối",
    dependencies=[Depends(rate_limit_group("read_light"))],
)
async def list_directives(
    request: Request,
    response: Response,
    directive_status: str | None = Query(default=None, alias="status"),
    pagination: PaginationParams = Depends(get_pagination),
    scope=Depends(get_department_scope),
    _: CurrentUser = Depends(get_current_user),
    service: CoordinationService = Depends(get_service),
) -> list[CoordinationDirectiveResponse]:
    if request.url.path.startswith("/api/v1/"):
        return paginate_v1(
            request,
            response,
            await service.list_directives_page(
                scope, directive_status, pagination.offset, pagination.limit
            ),
            pagination,
        )
    return paginate_v1(
        request, response, await service.list_directives(scope, directive_status), pagination
    )


@router.get(
    "/directives/{directive_id}/candidates",
    response_model=list[WorkloadCandidateResponse],
    summary="Danh sách ứng viên tiếp nhận chỉ thị điều phối",
    dependencies=[Depends(rate_limit_group("read_light"))],
)
async def list_directive_candidates(
    directive_id: str,
    request: Request,
    response: Response,
    pagination: PaginationParams = Depends(get_pagination),
    scope=Depends(get_department_scope),
    _: CurrentUser = Depends(get_current_user),
    service: CoordinationService = Depends(get_service),
) -> list[WorkloadCandidateResponse]:
    if request.url.path.startswith("/api/v1/"):
        return paginate_v1(
            request,
            response,
            await service.list_directive_candidates_page(
                directive_id, scope, pagination.offset, pagination.limit
            ),
            pagination,
        )
    return paginate_v1(
        request, response, await service.list_directive_candidates(directive_id, scope), pagination
    )


@router.post(
    "/directives/{directive_id}/fulfillment",
    response_model=CoordinationPlanResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Manager tiếp nhận chỉ thị điều phối",
    name="fulfill_directive_v1",
    dependencies=[Depends(rate_limit_group("directive_action"))],
)
@router.post(
    "/directives/{directive_id}/fulfill",
    response_model=CoordinationPlanResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Deprecated: Manager tiếp nhận chỉ thị điều phối",
    deprecated=True,
    name="fulfill_directive_legacy",
    dependencies=[Depends(rate_limit_group("directive_action"))],
)
async def fulfill_directive(
    directive_id: str,
    request: FulfillDirectiveRequest,
    scope=Depends(get_department_scope),
    current_user: CurrentUser = Depends(get_current_user),
    service: CoordinationService = Depends(get_service),
    idempotency: IdempotencyContext | None = Depends(idempotent("coordination_fulfillment")),
) -> CoordinationPlanResponse:
    result = await service.fulfill_directive(directive_id, scope, current_user.user_id, request)
    await complete_idempotency(idempotency, result, status_code=201)
    return result


__all__ = ["router"]
