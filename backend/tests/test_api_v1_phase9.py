from datetime import date, datetime, timezone
from unittest.mock import AsyncMock

import pytest
from bson import ObjectId
from fastapi import Response

from app.api.v1.alerts import get_alert_ai_proposal_v1
from app.api.v1.attachments import (
    cancel_upload_session_v1,
    complete_upload_session_resource_v1,
    complete_upload_session_v1_compat,
    create_upload_session_v1,
)
from app.api.v1.department_evaluations import get_department_evaluation_attachment_url_v1
from app.api.v1.performance import get_daily_review_attachment_url_v1
from app.api.v1.scans import scan_alerts_v1, scan_overload_v1
from app.api.v1.tasks import get_overdue_task_ai_proposal_v1
from app.models.ai_proposal import AiAlertProposalResponse
from app.models.alert import AlertDocument, AlertSeverity, AlertStatus
from app.models.attachment import CompleteUploadSessionResponse, UploadSessionResponse
from app.models.overload import WorkloadCandidateResponse
from app.models.task_planning import OverdueTaskPlanningResponse
from app.models.user import CurrentUser, UserRole


def _alert() -> AlertDocument:
    now = datetime.now(timezone.utc)
    return AlertDocument(
        _id=ObjectId(),
        alert_type="overload",
        severity=AlertSeverity.HIGH,
        status=AlertStatus.OPEN,
        employee_id=ObjectId(),
        department_id=ObjectId(),
        employee_code="KD-NV-001",
        employee_name="Nhân viên nguồn",
        title="Cảnh báo quá tải",
        message="Khối lượng cao.",
        suggested_action="Phân bớt việc.",
        detected_dates=[date(2026, 9, 9)],
        fingerprint="api-proposal-test",
        created_at=now,
        updated_at=now,
    )


def _user() -> CurrentUser:
    return CurrentUser(
        user_id="manager-1",
        username="manager",
        full_name="Quản lý kiểm thử",
        role=UserRole.MANAGER,
        department_id="department-1",
    )


@pytest.mark.asyncio
async def test_upload_session_v1_routes_reuse_service_and_location() -> None:
    service = AsyncMock()
    service.create.return_value = UploadSessionResponse(
        id="session-1",
        upload_url="https://storage.test/upload/1",
        expires_at="2026-09-08T10:00:00Z",
        required_headers={"Content-Type": "application/pdf"},
    )
    response = Response()
    request = object()

    created = await create_upload_session_v1(request, response, "department-1", _user(), service)

    assert created.id == "session-1"
    assert response.headers["Location"] == "/api/v1/upload-sessions/session-1"
    service.create.assert_awaited_once_with(request, _user(), "department-1")


@pytest.mark.asyncio
async def test_upload_session_patch_mirrors_legacy_complete_without_body() -> None:
    service = AsyncMock()
    completed = CompleteUploadSessionResponse(
        id="session-1",
        status="uploaded",
        file_name="bao-cao.pdf",
        content_type="application/pdf",
        file_size=10,
    )
    service.complete.return_value = completed

    result = await complete_upload_session_v1_compat("session-1", _user(), service)

    assert result == completed
    service.complete.assert_awaited_once_with("session-1", _user())


@pytest.mark.asyncio
async def test_upload_session_completion_and_cancel_use_existing_service_methods() -> None:
    service = AsyncMock()
    service.complete.return_value = CompleteUploadSessionResponse(
        id="session-1",
        status="uploaded",
        file_name="bao-cao.pdf",
        content_type="application/pdf",
        file_size=10,
    )

    completed = await complete_upload_session_resource_v1("session-1", _user(), service)
    cancelled = await cancel_upload_session_v1("session-1", _user(), service)

    assert completed.id == "session-1"
    assert cancelled.status_code == 204
    service.complete.assert_awaited_once_with("session-1", _user())
    service.cancel.assert_awaited_once_with("session-1", _user())


@pytest.mark.asyncio
async def test_scan_v1_routes_reuse_legacy_services() -> None:
    alert_service = AsyncMock()
    overload_service = AsyncMock()
    alert_service.scan_all.return_value = []
    overload_service.scan.return_value = {"created_count": 0, "logs": []}

    assert await scan_alerts_v1("department-1", _user(), alert_service) == []
    overload_result = await scan_overload_v1("department-1", _user(), overload_service)

    assert overload_result == {"created_count": 0, "logs": []}
    alert_service.scan_all.assert_awaited_once_with("department-1")
    overload_service.scan.assert_awaited_once_with("department-1")


@pytest.mark.asyncio
async def test_alert_ai_proposal_route_reuses_coordination_scope_and_ai_service() -> None:
    alert = _alert()
    candidate = WorkloadCandidateResponse(
        employee_id="candidate-1",
        employee_code="KD-NV-002",
        employee_name="Nhân viên nhận việc",
        tasks_completed=1,
        quality_score=90,
    )
    coordination_service = AsyncMock()
    coordination_service.get_rebalance_candidates_for_alert.return_value = (alert, [candidate])
    ai_service = AsyncMock()
    ai_service.generate_alert_action_proposal.return_value = AiAlertProposalResponse(
        alert_id=str(alert.id), summary="Đề xuất", actions=[]
    )

    result = await get_alert_ai_proposal_v1(
        str(alert.id), alert.department_id, _user(), coordination_service, ai_service
    )

    assert result.summary == "Đề xuất"
    coordination_service.get_rebalance_candidates_for_alert.assert_awaited_once_with(
        str(alert.id), alert.department_id
    )
    ai_service.generate_alert_action_proposal.assert_awaited_once_with(
        alert, alert.department_id, [candidate], "manager-1"
    )


@pytest.mark.asyncio
async def test_overdue_task_ai_proposal_route_uses_deterministic_plan_before_ai() -> None:
    task_service = AsyncMock()
    planning_service = AsyncMock()
    ai_service = AsyncMock()
    task = object()
    plan = OverdueTaskPlanningResponse(
        task_id="task-1",
        summary="Đã tính phương án.",
        options=[],
        data_as_of=date(2026, 9, 10),
        plan_version="plan-1",
    )
    task_service.get.return_value = task
    planning_service.build_plan.return_value = plan
    ai_service.generate_overdue_task_action_proposal.return_value = plan

    result = await get_overdue_task_ai_proposal_v1(
        "task-1",
        ObjectId("507f1f77bcf86cd799439011"),
        _user(),
        task_service,
        planning_service,
        ai_service,
    )

    assert result.plan_version == "plan-1"
    task_service.get.assert_awaited_once()
    planning_service.build_plan.assert_awaited_once_with(
        task, ObjectId("507f1f77bcf86cd799439011")
    )
    ai_service.generate_overdue_task_action_proposal.assert_awaited_once_with(
        plan, ObjectId("507f1f77bcf86cd799439011"), "manager-1"
    )


@pytest.mark.asyncio
async def test_download_url_v1_routes_preserve_contextual_service_calls() -> None:
    performance_service = AsyncMock()
    department_service = AsyncMock()
    performance_result = object()
    department_result = object()
    performance_service.get_attachment_download_url.return_value = performance_result
    department_service.get_attachment_download_url.return_value = department_result

    assert (
        await get_daily_review_attachment_url_v1(
            "employee-1", date(2026, 9, 8), "attachment-1", "department-1", _user(), performance_service
        )
        is performance_result
    )
    assert (
        await get_department_evaluation_attachment_url_v1(
            "evaluation-1", "attachment-1", "department-1", _user(), department_service
        )
        is department_result
    )
    performance_service.get_attachment_download_url.assert_awaited_once_with(
        "employee-1", date(2026, 9, 8), "attachment-1", "department-1"
    )
    department_service.get_attachment_download_url.assert_awaited_once_with(
        "evaluation-1", "attachment-1", "department-1"
    )
