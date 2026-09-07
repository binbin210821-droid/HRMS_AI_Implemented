from fastapi import APIRouter, Depends

from app.api.dependencies import get_current_user, get_department_scope
from app.core.database import get_mongo_database
from app.core.time import BusinessClock
from app.models.dashboard_attention import AttentionSummaryResponse
from app.models.user import CurrentUser
from app.repositories.alert_repository import AlertRepository
from app.repositories.department_directive_repository import DepartmentDirectiveRepository
from app.repositories.department_repository import DepartmentRepository
from app.repositories.employee_repository import EmployeeRepository
from app.repositories.task_repository import TaskRepository
from app.services.dashboard_attention_service import DashboardAttentionService

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


def get_dashboard_attention_service() -> DashboardAttentionService:
    database = get_mongo_database().get_database()
    return DashboardAttentionService(
        AlertRepository(database),
        TaskRepository(database),
        EmployeeRepository(database),
        DepartmentRepository(database),
        DepartmentDirectiveRepository(database),
        clock=BusinessClock(),
    )


@router.get(
    "/attention-summary",
    response_model=AttentionSummaryResponse,
    summary="Tổng hợp việc cần theo dõi",
)
async def get_attention_summary(
    scope=Depends(get_department_scope),
    _: CurrentUser = Depends(get_current_user),
    service: DashboardAttentionService = Depends(get_dashboard_attention_service),
) -> AttentionSummaryResponse:
    return await service.get_summary(scope)


__all__ = ["router"]
