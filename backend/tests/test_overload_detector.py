from datetime import date, datetime, timedelta, timezone

import pytest
from bson import ObjectId

from app.events.event_bus import OVERLOAD_DETECTED, EventBus
from app.models.employee import EmployeeDocument
from app.models.overload import OverloadLogDocument, OverloadTriggerReason
from app.models.performance import PerformanceMetricDocument
from app.services.overload_detector import OverloadDetector
from tests.time_fixtures import FixedBusinessClock


def employee() -> EmployeeDocument:
    now = datetime.now(timezone.utc)
    return EmployeeDocument(
        _id=ObjectId(),
        employee_code="KD-NV-001",
        full_name="Nhân viên A",
        position="Chuyên viên",
        department_id=ObjectId(),
        created_at=now,
        updated_at=now,
    )


def metric(employee_id: ObjectId, metric_date: date, tasks: int, quality: float):
    now = datetime.now(timezone.utc)
    return PerformanceMetricDocument(
        _id=ObjectId(),
        employee_id=employee_id,
        date=metric_date,
        tasks_completed=tasks,
        quality_score=quality,
        reviewed_by=ObjectId(),
        performance_score=quality,
        created_at=now,
        updated_at=now,
    )


class FakeRepository:
    def __init__(self, metrics):
        self.metrics = metrics
        self.logs: list[OverloadLogDocument] = []

    async def find_metrics(self, _employee_id):
        return self.metrics

    async def find_by_fingerprint(self, employee_id, metric_date, reasons):
        return next(
            (
                log
                for log in self.logs
                if log.employee_id == employee_id
                and log.date == metric_date
                and all(reason in [item.value for item in log.trigger_reason] for reason in reasons)
            ),
            None,
        )

    async def insert_log(self, document):
        log = OverloadLogDocument.model_validate(document)
        self.logs.append(log)
        return log


@pytest.mark.asyncio
async def test_condition_a_creates_high_risk_overload_event():
    subject = employee()
    repository = FakeRepository([metric(subject.id, date(2026, 8, 29), 5, 90)])
    bus = EventBus()
    events = []

    async def capture(payload):
        events.append(payload)

    bus.subscribe(OVERLOAD_DETECTED, capture)
    detector = OverloadDetector(
        repository,
        bus,
        clock=FixedBusinessClock(datetime(2026, 9, 6, tzinfo=timezone.utc)),
    )

    created = await detector.detect_for_employee(subject)

    assert len(created) == 1
    assert created[0].trigger_reason == [OverloadTriggerReason.TASK_VOLUME]
    assert events[0]["log"] == created[0]


@pytest.mark.asyncio
async def test_condition_b_uses_seven_day_baseline_and_three_consecutive_days():
    subject = employee()
    first_day = date(2026, 8, 1)
    metrics = [metric(subject.id, first_day + timedelta(days=index), 3, 95) for index in range(7)]
    metrics.extend(
        [
            metric(subject.id, date(2026, 8, 8), 3, 75),
            metric(subject.id, date(2026, 8, 9), 3, 70),
            metric(subject.id, date(2026, 8, 10), 3, 60),
        ]
    )
    repository = FakeRepository(metrics)
    created = await OverloadDetector(
        repository, clock=FixedBusinessClock(datetime(2026, 9, 6, tzinfo=timezone.utc))
    ).detect_for_employee(subject)

    assert len(created) == 1
    assert created[0].trigger_reason == [OverloadTriggerReason.QUALITY_DROP]
    assert created[0].baseline_quality_avg == 95
    assert created[0].date == date(2026, 8, 10)


@pytest.mark.asyncio
async def test_detector_does_not_duplicate_existing_overload_log():
    subject = employee()
    repository = FakeRepository([metric(subject.id, date(2026, 8, 29), 6, 80)])
    detector = OverloadDetector(
        repository, clock=FixedBusinessClock(datetime(2026, 9, 6, tzinfo=timezone.utc))
    )

    assert len(await detector.detect_for_employee(subject)) == 1
    assert await detector.detect_for_employee(subject) == []
