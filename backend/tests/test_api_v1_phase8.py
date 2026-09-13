from datetime import date, timedelta
from unittest.mock import AsyncMock

import pytest
from bson import ObjectId
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api.coordination import get_service as get_coordination_service
from app.api.dependencies import get_current_user, get_department_scope
from app.api.tasks import get_task_service
from app.api.v1.alerts import resolve_alert_v1
from app.api.v1.coordination import fulfill_directive_resource_v1
from app.api.v1.tasks import acknowledge_department_task_directive_resource_v1
from app.api.v1.thresholds import approve_threshold_config_resource_v1
from app.core.config import Settings
from app.infrastructure.rate_limit import (
    InMemoryRateLimiter,
    RateLimitKeyBuilder,
    RateLimitPolicy,
)
from app.main import app
from app.models.alert import AlertResolveV1Request
from app.models.coordination import (
    FulfillDirectiveRequest,
    IssueDepartmentAlertDirectiveRequest,
)
from app.models.task import (
    AcknowledgeDepartmentTaskDirectiveRequest,
    IssueDepartmentTaskDirectiveRequest,
    TaskDirectiveFocus,
)
from app.models.user import CurrentUser, UserRole
from app.services.coordination_service import CoordinationService
from app.services.task_service import TaskService


def _user(role: UserRole) -> CurrentUser:
    return CurrentUser(
        user_id="507f1f77bcf86cd799439011",
        username="phase8.test",
        full_name="Người dùng kiểm thử",
        role=role,
        department_id="507f1f77bcf86cd799439012",
    )


@pytest.mark.asyncio
async def test_task_directive_acknowledgement_uses_existing_service_contract() -> None:
    service = AsyncMock()
    service.acknowledge_department_directive.return_value = "updated"
    request = AcknowledgeDepartmentTaskDirectiveRequest(
        action_note="Đã tiếp nhận chỉ thị",
        commitment_date=date(2026, 9, 20),
    )

    result = await acknowledge_department_task_directive_resource_v1(
        "507f1f77bcf86cd799439013",
        request,
        "507f1f77bcf86cd799439012",
        _user(UserRole.MANAGER),
        service,
    )

    assert result == "updated"
    service.acknowledge_department_directive.assert_awaited_once_with(
        "507f1f77bcf86cd799439013",
        "507f1f77bcf86cd799439012",
        "507f1f77bcf86cd799439011",
        request,
    )


@pytest.mark.asyncio
async def test_resolve_alert_v1_adapts_status_contract_without_changing_service() -> None:
    service = AsyncMock()
    service.resolve.return_value = "resolved"
    request = AlertResolveV1Request(status="resolved", resolution_note="Đã xử lý")

    result = await resolve_alert_v1(
        "507f1f77bcf86cd799439013",
        request,
        "507f1f77bcf86cd799439012",
        _user(UserRole.MANAGER),
        service,
    )

    assert result == "resolved"
    service.resolve.assert_awaited_once()
    alert_id, scope, user_id, service_request = service.resolve.await_args.args
    assert (alert_id, scope, user_id) == (
        "507f1f77bcf86cd799439013",
        "507f1f77bcf86cd799439012",
        "507f1f77bcf86cd799439011",
    )
    assert service_request.resolution_note == "Đã xử lý"


@pytest.mark.asyncio
async def test_coordination_fulfillment_and_threshold_approval_reuse_services() -> None:
    coordination = AsyncMock()
    coordination.fulfill_directive.return_value = "plan"
    request = FulfillDirectiveRequest(target_employee_id="507f1f77bcf86cd799439013")
    result = await fulfill_directive_resource_v1(
        "507f1f77bcf86cd799439014",
        request,
        "507f1f77bcf86cd799439012",
        _user(UserRole.MANAGER),
        coordination,
    )
    assert result == "plan"
    coordination.fulfill_directive.assert_awaited_once_with(
        "507f1f77bcf86cd799439014",
        "507f1f77bcf86cd799439012",
        "507f1f77bcf86cd799439011",
        request,
    )

    threshold = AsyncMock()
    threshold.approve.return_value = "approved"
    result = await approve_threshold_config_resource_v1(
        "507f1f77bcf86cd799439015",
        _user(UserRole.LEADERSHIP),
        threshold,
    )
    assert result == "approved"
    threshold.approve.assert_awaited_once_with(
        "507f1f77bcf86cd799439015", "507f1f77bcf86cd799439011"
    )


def test_phase8_routes_and_legacy_compatibility_paths_are_separate() -> None:
    paths = app.openapi()["paths"]
    expected = {
        "/api/v1/tasks/department-directives/{directive_id}/acknowledgements",
        "/api/v1/tasks/department-directives/{directive_id}/submissions",
        "/api/v1/tasks/department-directives/{directive_id}/acceptances",
        "/api/v1/tasks/department-directives/{directive_id}/revision-requests",
        "/api/v1/alerts/department-directives/{directive_id}/acknowledgements",
        "/api/v1/alerts/department-directives/{directive_id}/submissions",
        "/api/v1/alerts/department-directives/{directive_id}/acceptances",
        "/api/v1/alerts/department-directives/{directive_id}/revision-requests",
        "/api/v1/coordination/directives/{directive_id}/fulfillments",
        "/api/v1/alerts/{alert_id}",
        "/api/v1/threshold-configs/{config_id}/approvals",
    }
    assert expected <= paths.keys()
    assert "/api/alerts/{alert_id}/resolve" in paths
    assert "/api/threshold-configs/{config_id}/approve" in paths
    assert "/api/v1/alerts/{alert_id}/resolve" in paths
    assert "/api/v1/threshold-configs/{config_id}/approve" in paths

    for path in expected - {"/api/v1/alerts/{alert_id}"}:
        method = "patch" if path == "/api/v1/alerts/{alert_id}" else "post"
        assert "429" in paths[path][method]["responses"]


def test_legacy_personal_coordination_flow_is_removed() -> None:
    paths = app.openapi()["paths"]
    removed_paths = {
        "/api/coordination/alerts/{alert_id}/direct",
        "/api/coordination/alerts/{alert_id}/directive-targets",
        "/api/v1/coordination/alerts/{alert_id}/direct",
        "/api/v1/coordination/alerts/{alert_id}/directive-targets",
    }
    assert removed_paths.isdisjoint(paths)


def test_alert_resolve_v1_rejects_any_status_other_than_resolved() -> None:
    with pytest.raises(ValidationError):
        AlertResolveV1Request(status="open")


@pytest.mark.asyncio
async def test_v1_task_and_alert_directive_action_routes_reach_real_services() -> None:
    """The frontend v1 action contracts must not stop at a legacy 404 route."""

    from app.models.alert import AlertSeverity
    from app.models.overload import WorkloadCandidateResponse
    from tests.test_coordination_service import FakeDepartmentDirectiveRepository, make_alert
    from tests.test_task_service import (
        FakeTaskRepository,
        make_department,
        make_employee,
        make_manager,
        task_request,
    )
    department_id = ObjectId()
    manager_id = ObjectId()
    employee = make_employee(department_id)
    task_repository = FakeTaskRepository([employee])
    task_repository.departments[department_id] = make_department(department_id)
    task_repository.users[manager_id] = make_manager(department_id, manager_id)
    task_service = TaskService(task_repository)
    task = await task_service.create(
        task_request(employee.id, due_date=date(2020, 1, 1)),
        department_id,
        str(manager_id),
    )
    task_directive = await task_service.issue_department_directive(
        str(department_id),
        str(ObjectId()),
        IssueDepartmentTaskDirectiveRequest(
            focus=TaskDirectiveFocus.OVERDUE, task_ids=[task.id]
        ),
    )

    alert = make_alert(department_id).model_copy(update={"severity": AlertSeverity.HIGH})
    candidate = WorkloadCandidateResponse(
        employee_id=str(employee.id),
        employee_code=employee.employee_code,
        employee_name=employee.full_name,
        tasks_completed=1,
        quality_score=90,
    )
    alert_repository = FakeDepartmentDirectiveRepository(department_id, [alert])
    alert_repository.candidate = candidate
    alert_service = CoordinationService(alert_repository)
    alert_directive = await alert_service.issue_department_directive(
        str(department_id),
        str(ObjectId()),
        IssueDepartmentAlertDirectiveRequest(alert_type="overload", severity="high"),
    )

    manager = CurrentUser(
        user_id=str(manager_id),
        username="phase8.manager",
        full_name="Quản lý kiểm thử",
        role=UserRole.MANAGER,
        department_id=str(department_id),
    )
    app.dependency_overrides[get_current_user] = lambda: manager
    app.dependency_overrides[get_department_scope] = lambda: department_id
    app.dependency_overrides[get_task_service] = lambda: task_service
    app.dependency_overrides[get_coordination_service] = lambda: alert_service
    original_rate_state = (
        app.state.settings,
        app.state.rate_limiter,
        app.state.rate_limit_policy,
        app.state.rate_limit_key_builder,
    )
    rate_settings = Settings(rate_limit_enabled=True, rate_limit_backend="memory")
    app.state.settings = rate_settings
    app.state.rate_limiter = InMemoryRateLimiter()
    app.state.rate_limit_policy = RateLimitPolicy(rate_settings)
    app.state.rate_limit_key_builder = RateLimitKeyBuilder(rate_settings)
    try:
        client = TestClient(app)
        task_response = client.post(
            f"/api/v1/tasks/department-directives/{task_directive.id}/acknowledgements",
            json={
                "action_note": "Đã tiếp nhận",
                "commitment_date": str(date.today() + timedelta(days=1)),
            },
        )
        alert_response = client.post(
            f"/api/v1/alerts/department-directives/{alert_directive.id}/acknowledgements",
            json={
                "note": "Đã tiếp nhận",
                "commitment_date": str(date.today() + timedelta(days=1)),
            },
        )
    finally:
        app.dependency_overrides.clear()
        (
            app.state.settings,
            app.state.rate_limiter,
            app.state.rate_limit_policy,
            app.state.rate_limit_key_builder,
        ) = original_rate_state

    assert task_response.status_code == 201, task_response.text
    assert alert_response.status_code == 201, alert_response.text


@pytest.mark.asyncio
async def test_v1_task_directive_append_duplicate_returns_409() -> None:
    from tests.test_task_service import (
        AppendDuplicateTaskRepository,
        make_department,
        make_employee,
        make_manager,
        task_request,
    )

    department_id = ObjectId()
    manager_id = ObjectId()
    employee = make_employee(department_id)
    repository = AppendDuplicateTaskRepository([employee])
    repository.departments[department_id] = make_department(department_id)
    repository.users[manager_id] = make_manager(department_id, manager_id)
    service = TaskService(repository)
    first_task = await service.create(
        task_request(employee.id, title="Công việc quá hạn 1", due_date=date(2020, 1, 1)),
        department_id,
        str(manager_id),
    )
    await service.issue_department_directive(
        str(department_id),
        str(ObjectId()),
        IssueDepartmentTaskDirectiveRequest(
            focus=TaskDirectiveFocus.OVERDUE, task_ids=[first_task.id]
        ),
    )
    second_task = await service.create(
        task_request(employee.id, title="Công việc quá hạn 2", due_date=date(2020, 1, 1)),
        department_id,
        str(manager_id),
    )
    leadership = CurrentUser(
        user_id=str(ObjectId()),
        username="phase8.leadership",
        full_name="Lãnh đạo kiểm thử",
        role=UserRole.LEADERSHIP,
    )
    app.dependency_overrides[get_current_user] = lambda: leadership
    app.dependency_overrides[get_task_service] = lambda: service
    original_rate_state = (
        app.state.settings,
        app.state.rate_limiter,
        app.state.rate_limit_policy,
        app.state.rate_limit_key_builder,
    )
    rate_settings = Settings(rate_limit_enabled=True, rate_limit_backend="memory")
    app.state.settings = rate_settings
    app.state.rate_limiter = InMemoryRateLimiter()
    app.state.rate_limit_policy = RateLimitPolicy(rate_settings)
    app.state.rate_limit_key_builder = RateLimitKeyBuilder(rate_settings)
    try:
        response = TestClient(app).post(
            f"/api/v1/tasks/department-directives/{department_id}",
            json={"focus": "overdue", "task_ids": [second_task.id]},
        )
    finally:
        app.dependency_overrides.clear()
        (
            app.state.settings,
            app.state.rate_limiter,
            app.state.rate_limit_policy,
            app.state.rate_limit_key_builder,
        ) = original_rate_state

    assert response.status_code == 409, response.text
    payload = response.json()
    assert "vui lòng tải lại" in (payload.get("detail") or payload.get("message", ""))
