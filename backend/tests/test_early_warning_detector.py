from datetime import date, datetime, timezone

import pytest
from bson import ObjectId

from app.events.event_bus import ALERT_CREATED, EventBus
from app.models.alert import AlertDocument
from app.models.employee import EmployeeDocument
from app.models.performance import PerformanceMetricDocument
from app.services.early_warning_detector import EarlyWarningDetector
from tests.time_fixtures import FixedBusinessClock


def make_employee() -> EmployeeDocument:
    now = datetime.now(timezone.utc)
    return EmployeeDocument(
        _id=ObjectId(),
        employee_code="KD-NV-003",
        full_name="Nhân viên cảnh báo C",
        position="Chuyên viên",
        department_id=ObjectId(),
        created_at=now,
        updated_at=now,
    )


def make_metric(
    employee_id: ObjectId, day: int, tasks: int, quality: float
) -> PerformanceMetricDocument:
    now = datetime.now(timezone.utc)
    return PerformanceMetricDocument(
        _id=ObjectId(),
        employee_id=employee_id,
        date=date(2026, 8, day),
        tasks_completed=tasks,
        quality_score=quality,
        reviewed_by=ObjectId(),
        performance_score=quality,
        created_at=now,
        updated_at=now,
    )


class FakePerformanceRepository:
    def __init__(self, metrics: list[PerformanceMetricDocument]) -> None:
        self.metrics = metrics

    async def find_employee_metrics(
        self, _employee_id: ObjectId
    ) -> list[PerformanceMetricDocument]:
        return self.metrics


class FakeAlertRepository:
    def __init__(self) -> None:
        self.alerts: list[AlertDocument] = []

    async def find_by_fingerprint(self, fingerprint: str) -> AlertDocument | None:
        return next((alert for alert in self.alerts if alert.fingerprint == fingerprint), None)

    async def insert(self, document: dict) -> AlertDocument:
        alert = AlertDocument.model_validate(document)
        self.alerts.append(alert)
        return alert


def warning_metrics(employee_id: ObjectId) -> list[PerformanceMetricDocument]:
    return [
        make_metric(employee_id, 26, 2, 88),
        make_metric(employee_id, 27, 3, 82),
        make_metric(employee_id, 28, 4, 78),
    ]


@pytest.mark.asyncio
async def test_detector_finds_three_day_early_warning_and_publishes_event() -> None:
    employee = make_employee()
    alerts = FakeAlertRepository()
    bus = EventBus()
    events: list[AlertDocument] = []

    async def capture(alert: AlertDocument) -> None:
        events.append(alert)

    bus.subscribe(ALERT_CREATED, capture)
    detector = EarlyWarningDetector(
        FakePerformanceRepository(warning_metrics(employee.id)),
        alerts,
        bus=bus,
        clock=FixedBusinessClock(datetime(2026, 9, 6, tzinfo=timezone.utc)),
    )

    created = await detector.detect_for_employee(employee, "Kinh doanh")
    repeated = await detector.detect_for_employee(employee, "Kinh doanh")

    assert len(created) == 1
    assert repeated == []
    assert created[0].severity.value == "medium"
    assert created[0].status.value == "open"
    assert events == created
    assert "Nên theo dõi" in created[0].suggested_action


def test_detector_requires_strict_trend_and_excludes_twenty_percent_drop() -> None:
    employee_id = ObjectId()
    warning = warning_metrics(employee_id)
    exact_drop = [
        make_metric(employee_id, 26, 2, 100),
        make_metric(employee_id, 27, 3, 90),
        make_metric(employee_id, 28, 4, 80),
    ]

    assert EarlyWarningDetector._is_consecutive(warning)
    assert EarlyWarningDetector._is_early_warning(warning, 20)
    assert not EarlyWarningDetector._is_early_warning(exact_drop, 20)
