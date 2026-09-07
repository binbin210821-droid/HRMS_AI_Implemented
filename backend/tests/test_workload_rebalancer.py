from datetime import date, datetime, timezone

import pytest
from bson import ObjectId

from app.models.overload import (
    OverloadLogDocument,
    OverloadTriggerReason,
    WorkloadCandidateResponse,
)
from app.services.workload_rebalancer import WorkloadRebalancer


@pytest.mark.asyncio
async def test_rebalancer_returns_same_department_low_work_stable_quality_candidates():
    expected = WorkloadCandidateResponse(
        employee_id=str(ObjectId()),
        employee_code="KD-NV-002",
        employee_name="Nhân viên B",
        tasks_completed=2,
        quality_score=85,
    )

    class FakeRepository:
        async def find_rebalance_candidates(self, department_id, metric_date, excluded_employee_id):
            assert department_id is not None
            assert metric_date == date(2026, 8, 29)
            assert excluded_employee_id is not None
            return [expected]

    log = OverloadLogDocument(
        _id=ObjectId(),
        employee_id=ObjectId(),
        department_id=ObjectId(),
        date=date(2026, 8, 29),
        trigger_reason=[OverloadTriggerReason.TASK_VOLUME],
        tasks_completed=5,
        quality_score=80,
        created_at=datetime.now(timezone.utc),
    )
    assert await WorkloadRebalancer(FakeRepository()).suggest(log) == [expected]
