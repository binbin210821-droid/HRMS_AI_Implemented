from datetime import date, datetime, timezone

import pytest
from bson import ObjectId

from app.models.alert import AlertDocument, AlertSeverity, AlertStatus
from app.models.overload import WorkloadCandidateResponse
from app.services.coordination_service import CoordinationService


def _alert(department_id: ObjectId, employee_id: ObjectId, alert_date: date) -> AlertDocument:
    now = datetime.now(timezone.utc)
    return AlertDocument(
        _id=ObjectId(),
        alert_type="overload",
        severity=AlertSeverity.HIGH,
        status=AlertStatus.OPEN,
        employee_id=employee_id,
        department_id=department_id,
        employee_code="NV-NGUON",
        employee_name="Nhân viên nguồn",
        title="Cảnh báo quá tải",
        message="Khối lượng công việc cao.",
        suggested_action="Phân bổ bớt công việc.",
        detected_dates=[alert_date],
        fingerprint=str(ObjectId()),
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_list_suggestions_batches_plans_and_rebalance_groups() -> None:
    departments = [ObjectId(), ObjectId()]
    dates = [date(2026, 9, 1), date(2026, 9, 2)]
    alerts = [
        _alert(departments[index % 2], ObjectId(), dates[(index // 2) % 2])
        for index in range(40)
    ]
    group_candidates = {
        (department_id, alert_date): [
            WorkloadCandidateResponse(
                employee_id=str(ObjectId()),
                employee_code="NV-NHAN",
                employee_name="Nhân viên nhận việc",
                tasks_completed=1,
                quality_score=90,
            )
        ]
        for department_id in departments
        for alert_date in dates
    }

    class SpyRepository:
        def __init__(self) -> None:
            self.plan_calls = 0
            self.group_calls: list[tuple[ObjectId, date]] = []

        async def ensure_indexes(self) -> None:
            return None

        async def list_alerts(self, _scope):
            return alerts

        async def find_plans(self, _alert_ids):
            self.plan_calls += 1
            return {}

        async def find_rebalance_candidates_for_group(self, department_id, alert_date):
            self.group_calls.append((department_id, alert_date))
            return group_candidates[(department_id, alert_date)]

    repository = SpyRepository()
    responses = await CoordinationService(repository).list_suggestions(None)

    assert len(responses) == 40
    assert repository.plan_calls == 1
    assert len(repository.group_calls) == 4
    assert len(set(repository.group_calls)) == 4
    assert all(response.candidates for response in responses)
