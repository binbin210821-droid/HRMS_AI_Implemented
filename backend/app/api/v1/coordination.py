from fastapi import APIRouter, Depends, status

from app.api.coordination import get_service
from app.api.dependencies import get_current_user, get_department_scope
from app.infrastructure.idempotency import IdempotencyContext, complete_idempotency, idempotent
from app.infrastructure.rate_limit import rate_limit_group
from app.models.coordination import CoordinationPlanResponse, FulfillDirectiveRequest
from app.models.user import CurrentUser
from app.services.coordination_service import CoordinationService

router = APIRouter(prefix="/coordination", tags=["Coordination v1"])


@router.post(
    "/directives/{directive_id}/fulfillments",
    response_model=CoordinationPlanResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Tiếp nhận chỉ thị điều phối phiên bản v1",
    dependencies=[Depends(rate_limit_group("directive_action"))],
)
async def fulfill_directive_resource_v1(
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
