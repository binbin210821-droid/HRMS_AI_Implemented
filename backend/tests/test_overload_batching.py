from datetime import date, datetime, timezone

import pytest
from bson import ObjectId

from app.models.employee import EmployeeDocument
from app.models.overload import (
    OverloadLogDocument,
    OverloadTriggerReason,
    WorkloadCandidateResponse,
)
from app.services.overload_service import OverloadService


def _log(department_id: ObjectId, employee_id: ObjectId, log_date: date) -> OverloadLogDocument:
    return OverloadLogDocument(
        _id=ObjectId(),
        employee_id=employee_id,
        department_id=department_id,
        date=log_date,
        trigger_reason=[OverloadTriggerReason.TASK_VOLUME],
        tasks_completed=5,
        quality_score=80,
        created_at=datetime.now(timezone.utc),
    )


@pytest.mark.asyncio
async def test_list_logs_batches_employees_and_rebalance_groups() -> None:
    departments = [ObjectId(), ObjectId()]
    dates = [date(2026, 9, 1), date(2026, 9, 2)]
    logs = [
        _log(departments[index % 2], ObjectId(), dates[(index // 2) % 2])
        for index in range(40)
    ]
    employees = {
        log.employee_id: EmployeeDocument(
            _id=log.employee_id,
            employee_code=f"NV-{index:03d}",
            full_name=f"Nhân viên {index}",
            position="Chuyên viên",
            department_id=log.department_id,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        for index, log in enumerate(logs)
    }
    group_candidates = {
        (department_id, log_date): [
            WorkloadCandidateResponse(
                employee_id=str(ObjectId()),
                employee_code="NV-NHAN",
                employee_name="Nhân viên nhận việc",
                tasks_completed=1,
                quality_score=90,
            )
        ]
        for department_id in departments
        for log_date in dates
    }

    class SpyRepository:
        def __init__(self) -> None:
            self.employee_calls = 0
            self.group_calls: list[tuple[ObjectId, date]] = []

        async def list_logs(self, _scope):
            return logs

        async def find_employees(self, _employee_ids):
            self.employee_calls += 1
            return employees

        async def find_rebalance_candidates_for_group(self, department_id, log_date):
            self.group_calls.append((department_id, log_date))
            return group_candidates[(department_id, log_date)]

    repository = SpyRepository()
    responses = await OverloadService(repository).list_logs(None)

    assert len(responses) == 40
    assert repository.employee_calls == 1
    assert len(repository.group_calls) == 4
    assert len(set(repository.group_calls)) == 4
    assert all(response.employee_code for response in responses)
    assert all(response.suggested_candidates for response in responses)
