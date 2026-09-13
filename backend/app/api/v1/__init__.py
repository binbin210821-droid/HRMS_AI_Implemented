"""API v1 walking skeleton và các alias tương thích hiện hữu."""

from typing import Any, cast

from fastapi import APIRouter
from fastapi.routing import APIRoute

from app.api.ai import router as ai_router
from app.api.alerts import router as alerts_router
from app.api.attachments import router as attachments_router
from app.api.auth import router as auth_router
from app.api.coordination import router as coordination_router
from app.api.dashboard import router as dashboard_router
from app.api.department_evaluations import router as department_evaluations_router
from app.api.departments import router as legacy_departments_router
from app.api.employees import router as employees_router
from app.api.health import router as health_router
from app.api.overload import router as overload_router
from app.api.performance import router as performance_router
from app.api.tasks import router as tasks_router
from app.api.thresholds import router as thresholds_router
from app.api.v1.alerts import router as alerts_v1_router
from app.api.v1.attachments import router as attachments_v1_router
from app.api.v1.coordination import router as coordination_v1_router
from app.api.v1.department_evaluations import router as department_evaluations_v1_router
from app.api.v1.departments import router as departments_router
from app.api.v1.employees import router as employees_v1_router
from app.api.v1.overload import router as overload_v1_router
from app.api.v1.performance import router as performance_v1_router
from app.api.v1.scans import router as scans_v1_router
from app.api.v1.tasks import router as tasks_v1_router
from app.api.v1.thresholds import router as thresholds_v1_router
from app.core.http_contract import V1_ERROR_RESPONSES


def _operation_id(route: APIRoute) -> str:
    return f"api_v1_{route.name}"


api_v1_router = APIRouter(
    prefix="/api/v1",
    responses=cast(dict[int | str, dict[str, Any]], V1_ERROR_RESPONSES),
    generate_unique_id_function=_operation_id,
)
api_v1_router.include_router(departments_router)
api_v1_router.include_router(employees_v1_router)
api_v1_router.include_router(tasks_v1_router)
api_v1_router.include_router(alerts_v1_router)
api_v1_router.include_router(overload_v1_router)
api_v1_router.include_router(performance_v1_router)
api_v1_router.include_router(department_evaluations_v1_router)
api_v1_router.include_router(coordination_v1_router)
api_v1_router.include_router(thresholds_v1_router)
api_v1_router.include_router(attachments_v1_router)
api_v1_router.include_router(scans_v1_router)


# Các alias này đã tồn tại trước walking skeleton và đang được frontend/smoke
# sử dụng. Giữ chúng trong cùng root v1 để tránh breaking change ngoài phạm vi.
def _compat_router_without_names(router: APIRouter, excluded_names: set[str]) -> APIRouter:
    compatibility_router = APIRouter()
    for route in router.routes:
        if isinstance(route, APIRoute) and route.name in excluded_names:
            continue
        compatibility_router.routes.append(route)
    return compatibility_router


for router in (
    health_router,
    auth_router,
    attachments_router,
    ai_router,
    coordination_router,
    dashboard_router,
    performance_router,
    _compat_router_without_names(thresholds_router, {"list_threshold_configs"}),
):
    api_v1_router.include_router(router)

api_v1_router.include_router(
    _compat_router_without_names(
        department_evaluations_router,
        {
            "get_weekly_department_review",
            "create_weekly_department_evaluation",
            "update_weekly_department_evaluation",
        },
    )
)


# Giữ mutation và read-model alias cũ, nhưng loại các GET collection/detail đã
# được thay bằng router v1 thật. Các endpoint cũ khác vẫn dùng nguyên service.
for legacy_router, excluded_names in (
    (
        legacy_departments_router,
        {
            "list_departments",
            "get_department",
            "create_department",
            "update_department",
            "delete_department",
        },
    ),
    (
        employees_router,
        {"list_employees", "get_employee", "create_employee", "update_employee", "delete_employee"},
    ),
    (
        tasks_router,
        {
            "list_tasks",
            "get_task",
            "list_department_task_directives",
            "create_task",
            "update_task",
            "delete_task",
        },
    ),
    (alerts_router, {"list_alerts", "resolve_alert_v1"}),
    (overload_router, {"list_overload_logs"}),
):
    api_v1_router.include_router(_compat_router_without_names(legacy_router, excluded_names))

__all__ = ["api_v1_router"]
