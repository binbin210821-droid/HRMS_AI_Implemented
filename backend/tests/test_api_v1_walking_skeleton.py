from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.api.departments import get_department_service
from app.api.dependencies import get_current_user, get_department_scope
from app.api.tasks import get_task_service
from app.core.config import Settings
from app.core.pagination import Page
from app.infrastructure.rate_limit import (
    InMemoryRateLimiter,
    RateLimitKeyBuilder,
    RateLimitPolicy,
)
from app.main import app
from app.models.department import DepartmentResponse
from app.models.user import CurrentUser, UserRole


class StubDepartmentService:
    def __init__(self, items: list[DepartmentResponse]) -> None:
        self.items = items

    async def list(self, _scope) -> list[DepartmentResponse]:
        return self.items

    async def list_page_v1(self, _scope, _page: int, _page_size: int) -> Page[DepartmentResponse]:
        return Page(items=self.items, total=len(self.items))


class StubTaskService:
    async def leadership_overview(self, range_preset):
        return {
            "range": range_preset,
            "period_start": "2026-01-01",
            "period_end": "2026-03-31",
            "departments_with_tasks": 0,
            "departments_need_attention": 0,
            "departments_overdue": 0,
            "departments_due_soon": 0,
            "completion_trend": [],
            "departments": [],
        }

    async def department_portfolio(self, department_id, range_preset, focus):
        return {
            "department_id": department_id,
            "department_name": "Phòng Kinh doanh",
            "department_code": "KD",
            "manager_name": "Quản lý Kinh doanh",
            "range": range_preset,
            "period_start": "2026-01-01",
            "period_end": "2026-03-31",
            "overdue": [],
            "due_soon": [],
            "high_priority": [],
            "on_track": [],
            "completed_in_period": [],
        }

    async def list_department_directives(self, _scope, _status):
        return []

    async def list_department_directives_page(self, _scope, _status, _offset, _limit) -> Page:
        return Page(items=[], total=0)


def _departments() -> list[DepartmentResponse]:
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return [
        DepartmentResponse(
            id=f"department-{index}",
            name=f"Phòng {index}",
            code=f"P{index}",
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        for index in range(1, 4)
    ]


def test_v1_pagination_and_legacy_department_response_are_both_available() -> None:
    original_state = (
        app.state.settings,
        app.state.rate_limiter,
        app.state.rate_limit_policy,
        app.state.rate_limit_key_builder,
    )
    settings = Settings(rate_limit_enabled=True, rate_limit_backend="memory")
    app.state.settings = settings
    app.state.rate_limiter = InMemoryRateLimiter()
    app.state.rate_limit_policy = RateLimitPolicy(settings)
    app.state.rate_limit_key_builder = RateLimitKeyBuilder(settings)
    service = StubDepartmentService(_departments())
    app.dependency_overrides[get_department_service] = lambda: service
    app.dependency_overrides[get_department_scope] = lambda: None

    try:
        client = TestClient(app)
        legacy = client.get("/api/departments")
        current = client.get("/api/v1/departments?page=1&page_size=2")

        assert legacy.status_code == 200
        assert isinstance(legacy.json(), list)
        assert len(legacy.json()) == 3
        assert current.status_code == 200
        assert current.json()["items"][0]["code"] == "P1"
        assert current.json()["page"] == 1
        assert current.json()["page_size"] == 2
        assert current.json()["total"] == 3
        assert current.json()["has_next"] is True
        for header in ("X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Reset"):
            assert header in current.headers
    finally:
        app.dependency_overrides.clear()
        (
            app.state.settings,
            app.state.rate_limiter,
            app.state.rate_limit_policy,
            app.state.rate_limit_key_builder,
        ) = original_state


def test_v1_pagination_validation_uses_v1_error_contract() -> None:
    original_scope = app.dependency_overrides.get(get_department_scope)
    original_service = app.dependency_overrides.get(get_department_service)
    app.dependency_overrides[get_department_scope] = lambda: None
    app.dependency_overrides[get_department_service] = lambda: StubDepartmentService([])
    try:
        response = TestClient(app).get("/api/v1/departments?page=0")
    finally:
        if original_scope is None:
            app.dependency_overrides.pop(get_department_scope, None)
        else:
            app.dependency_overrides[get_department_scope] = original_scope
        if original_service is None:
            app.dependency_overrides.pop(get_department_service, None)
        else:
            app.dependency_overrides[get_department_service] = original_service

    assert response.status_code == 422
    payload = response.json()
    assert payload["code"] == "validation_error"
    assert isinstance(payload["details"], dict)
    assert payload["request_id"] == response.headers["X-Request-ID"]


def test_v1_openapi_has_separate_paginated_department_contract() -> None:
    schema = app.openapi()

    assert set(schema["paths"]["/api/v1/departments"]) >= {"get", "post"}
    assert schema["paths"]["/api/v1/departments"]["get"]["responses"]["200"]["content"][
        "application/json"
    ]["schema"]["$ref"].endswith("PageResponse_DepartmentResponse_")
    assert schema["paths"]["/api/departments"]["get"]["responses"]["200"]["content"][
        "application/json"
    ]["schema"]["type"] == "array"
    assert schema["paths"]["/api/v1/departments"]["get"]["responses"]["422"]["content"][
        "application/json"
    ]["schema"]["$ref"].endswith("V1ApiError")


def test_v1_static_department_directives_route_precedes_task_id_route() -> None:
    original_state = (
        app.state.settings,
        app.state.rate_limiter,
        app.state.rate_limit_policy,
        app.state.rate_limit_key_builder,
    )
    settings = Settings(rate_limit_enabled=True, rate_limit_backend="memory")
    app.state.settings = settings
    app.state.rate_limiter = InMemoryRateLimiter()
    app.state.rate_limit_policy = RateLimitPolicy(settings)
    app.state.rate_limit_key_builder = RateLimitKeyBuilder(settings)
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        user_id="leadership-1",
        username="leadership",
        full_name="Lãnh đạo",
        role=UserRole.LEADERSHIP,
    )
    app.dependency_overrides[get_department_scope] = lambda: None
    app.dependency_overrides[get_task_service] = lambda: StubTaskService()

    try:
        response = TestClient(app).get("/api/v1/tasks/department-directives")
    finally:
        app.dependency_overrides.clear()
        (
            app.state.settings,
            app.state.rate_limiter,
            app.state.rate_limit_policy,
            app.state.rate_limit_key_builder,
        ) = original_state

    assert response.status_code == 200
    assert response.json() == []
    assert response.headers["X-RateLimit-Limit"] == "120"


def test_v1_static_leadership_overview_route_accepts_90d() -> None:
    original_state = (
        app.state.settings,
        app.state.rate_limiter,
        app.state.rate_limit_policy,
        app.state.rate_limit_key_builder,
    )
    settings = Settings(rate_limit_enabled=True, rate_limit_backend="memory")
    app.state.settings = settings
    app.state.rate_limiter = InMemoryRateLimiter()
    app.state.rate_limit_policy = RateLimitPolicy(settings)
    app.state.rate_limit_key_builder = RateLimitKeyBuilder(settings)
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        user_id="leadership-1",
        username="leadership",
        full_name="Lãnh đạo",
        role=UserRole.LEADERSHIP,
    )
    app.dependency_overrides[get_task_service] = lambda: StubTaskService()

    try:
        response = TestClient(app).get("/api/v1/tasks/leadership-overview?range=90d")
    finally:
        app.dependency_overrides.clear()
        (
            app.state.settings,
            app.state.rate_limiter,
            app.state.rate_limit_policy,
            app.state.rate_limit_key_builder,
        ) = original_state

    assert response.status_code == 200
    assert response.json()["range"] == "90d"


def test_v1_leadership_department_portfolio_route_accepts_overdue_focus() -> None:
    original_state = (
        app.state.settings,
        app.state.rate_limiter,
        app.state.rate_limit_policy,
        app.state.rate_limit_key_builder,
    )
    settings = Settings(rate_limit_enabled=True, rate_limit_backend="memory")
    app.state.settings = settings
    app.state.rate_limiter = InMemoryRateLimiter()
    app.state.rate_limit_policy = RateLimitPolicy(settings)
    app.state.rate_limit_key_builder = RateLimitKeyBuilder(settings)
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        user_id="leadership-1",
        username="leadership",
        full_name="Lãnh đạo",
        role=UserRole.LEADERSHIP,
    )
    app.dependency_overrides[get_task_service] = lambda: StubTaskService()

    try:
        response = TestClient(app).get(
            "/api/v1/tasks/departments/department-1/portfolio?range=90d&focus=overdue"
        )
    finally:
        app.dependency_overrides.clear()
        (
            app.state.settings,
            app.state.rate_limiter,
            app.state.rate_limit_policy,
            app.state.rate_limit_key_builder,
        ) = original_state

    assert response.status_code == 200
    assert response.json()["department_id"] == "department-1"
    assert response.json()["range"] == "90d"
