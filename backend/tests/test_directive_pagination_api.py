from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.api.coordination import get_service as get_coordination_service
from app.api.dependencies import get_current_user, get_department_scope
from app.api.tasks import get_task_service
from app.core.config import Settings
from app.core.pagination import Page
from app.infrastructure.rate_limit import InMemoryRateLimiter, RateLimitKeyBuilder, RateLimitPolicy
from app.main import app
from app.models.user import CurrentUser, UserRole


def _task_directive(index: int) -> dict:
    return {
        "id": f"task-directive-{index}",
        "target_department_id": "department-1",
        "target_department_name": "Phòng Kinh doanh",
        "target_manager_id": "manager-1",
        "target_manager_name": "Quản lý Kinh doanh",
        "task_ids": [f"task-{index}"],
        "focus": "overdue",
        "selected_task_count": 1,
        "status": "pending",
        "issued_by": "leadership-1",
        "issued_at": datetime(2026, 9, 1, tzinfo=timezone.utc),
    }


def _alert_directive(index: int) -> dict:
    return {
        "id": f"alert-directive-{index}",
        "department_id": "department-1",
        "department_name": "Phòng Kinh doanh",
        "target_department_id": "department-1",
        "target_manager_id": "manager-1",
        "target_manager_name": "Quản lý Kinh doanh",
        "alert_ids": [f"alert-{index}"],
        "selected_alert_type": "all",
        "selected_severity": "all",
        "selected_alert_count": 1,
        "selected_open_count": 1,
        "total_count": 1,
        "open_count": 1,
        "resolved_count": 0,
        "early_warning_count": 0,
        "overload_count": 1,
        "high_count": 1,
        "status": "pending",
        "issued_by": "leadership-1",
        "issued_at": datetime(2026, 9, 1, tzinfo=timezone.utc),
    }


def _coordination_directive(index: int) -> dict:
    return {
        "id": f"coordination-directive-{index}",
        "alert_id": f"alert-{index}",
        "source_department_id": "department-1",
        "source_department_name": "Phòng Kinh doanh",
        "target_department_id": "department-2",
        "target_department_name": "Phòng Chăm sóc khách hàng",
        "status": "pending",
        "issued_by": "leadership-1",
        "issued_at": datetime(2026, 9, 1, tzinfo=timezone.utc),
    }


class StubTaskService:
    def __init__(self, items: list[dict]) -> None:
        self.items = items
        self.calls: list[tuple[str | None, int, int]] = []

    async def list_department_directives_page(
        self, _scope, status: str | None, offset: int, limit: int
    ) -> Page[dict]:
        self.calls.append((status, offset, limit))
        return Page(items=self.items[offset : offset + limit], total=len(self.items))


class StubCoordinationService:
    def __init__(self, alert_items: list[dict], coordination_items: list[dict]) -> None:
        self.alert_items = alert_items
        self.coordination_items = coordination_items
        self.alert_calls: list[tuple[str | None, int, int]] = []
        self.coordination_calls: list[tuple[str | None, int, int]] = []

    async def list_department_directives_page(
        self, _scope, status: str | None, offset: int, limit: int
    ) -> Page[dict]:
        self.alert_calls.append((status, offset, limit))
        return Page(items=self.alert_items[offset : offset + limit], total=len(self.alert_items))

    async def list_directives_page(
        self, _scope, status: str | None, offset: int, limit: int
    ) -> Page[dict]:
        self.coordination_calls.append((status, offset, limit))
        return Page(
            items=self.coordination_items[offset : offset + limit],
            total=len(self.coordination_items),
        )


def test_directive_v1_endpoints_accept_offset_limit_and_return_each_page() -> None:
    original_state = (
        app.state.settings,
        app.state.rate_limiter,
        app.state.rate_limit_policy,
        app.state.rate_limit_key_builder,
    )
    original_overrides = app.dependency_overrides.copy()
    task_service = StubTaskService([_task_directive(index) for index in range(3)])
    coordination_service = StubCoordinationService(
        [_alert_directive(index) for index in range(3)],
        [_coordination_directive(index) for index in range(3)],
    )
    app.state.settings = Settings(rate_limit_enabled=True, rate_limit_backend="memory")
    app.state.rate_limiter = InMemoryRateLimiter()
    app.state.rate_limit_policy = RateLimitPolicy(app.state.settings)
    app.state.rate_limit_key_builder = RateLimitKeyBuilder(app.state.settings)
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        user_id="leadership-1",
        username="leadership",
        full_name="Lãnh đạo",
        role=UserRole.LEADERSHIP,
    )
    app.dependency_overrides[get_department_scope] = lambda: None
    app.dependency_overrides[get_task_service] = lambda: task_service
    app.dependency_overrides[get_coordination_service] = lambda: coordination_service

    try:
        client = TestClient(app)
        responses = [
            client.get("/api/v1/tasks/department-directives?status=pending&offset=0&limit=2"),
            client.get(
                "/api/v1/coordination/department-directives?status=pending&offset=2&limit=2"
            ),
            client.get("/api/v1/coordination/directives?status=pending&offset=0&limit=2"),
        ]
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(original_overrides)
        (
            app.state.settings,
            app.state.rate_limiter,
            app.state.rate_limit_policy,
            app.state.rate_limit_key_builder,
        ) = original_state

    assert [response.status_code for response in responses] == [200, 200, 200]
    assert [item["id"] for item in responses[0].json()] == [
        "task-directive-0",
        "task-directive-1",
    ]
    assert [item["id"] for item in responses[1].json()] == ["alert-directive-2"]
    assert [item["id"] for item in responses[2].json()] == [
        "coordination-directive-0",
        "coordination-directive-1",
    ]
    for response in responses:
        assert response.headers["X-Total-Count"] == "3"
        assert response.headers["X-Limit"] == "2"
    assert responses[0].headers["X-Offset"] == "0"
    assert responses[1].headers["X-Offset"] == "2"
    assert responses[2].headers["X-Offset"] == "0"
    assert "offset=2" in responses[0].headers["Link"]
    assert "Link" not in responses[1].headers
    assert task_service.calls == [("pending", 0, 2)]
    assert coordination_service.alert_calls == [("pending", 2, 2)]
    assert coordination_service.coordination_calls == [("pending", 0, 2)]
