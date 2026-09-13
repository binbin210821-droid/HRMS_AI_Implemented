from datetime import datetime, timezone

import pytest
from bson import ObjectId
from fastapi import HTTPException

from app.models.alert import AlertDocument, AlertResolveRequest, AlertSeverity, AlertStatus
from app.services.alert_service import EarlyWarningService


def make_alert(department_id: ObjectId) -> AlertDocument:
    now = datetime.now(timezone.utc)
    return AlertDocument(
        _id=ObjectId(),
        alert_type="early_warning",
        severity=AlertSeverity.MEDIUM,
        status=AlertStatus.OPEN,
        employee_id=ObjectId(),
        department_id=department_id,
        employee_code="KD-NV-003",
        employee_name="Nhân viên cảnh báo C",
        title="Dấu hiệu tiềm ẩn quá tải",
        message="Xu hướng nghịch ba ngày liên tiếp.",
        suggested_action="Nên theo dõi.",
        detected_dates=[],
        fingerprint="fingerprint",
        created_at=now,
        updated_at=now,
    )


class FakeAlertRepository:
    def __init__(self, alert: AlertDocument) -> None:
        self.alert = alert
        self.updated: dict = {}

    async def find_by_id(self, _alert_id: ObjectId) -> AlertDocument | None:
        return self.alert

    async def resolve_if_open(self, _alert_id: ObjectId, values: dict) -> AlertDocument:
        self.updated = values
        self.alert = self.alert.model_copy(update=values)
        return self.alert

    async def update(self, _alert_id: ObjectId, values: dict) -> AlertDocument:
        return await self.resolve_if_open(_alert_id, values)


class UnusedRepository:
    pass


@pytest.mark.asyncio
async def test_resolve_alert_updates_status_and_note() -> None:
    department_id = ObjectId()
    repository = FakeAlertRepository(make_alert(department_id))
    service = EarlyWarningService(repository, UnusedRepository(), UnusedRepository())

    resolved = await service.resolve(
        str(repository.alert.id),
        department_id,
        str(ObjectId()),
        AlertResolveRequest(resolution_note="  Đã phân bổ lại công việc  "),
    )

    assert resolved.status == AlertStatus.RESOLVED
    assert resolved.resolution_note == "Đã phân bổ lại công việc"
    assert repository.updated["status"] == AlertStatus.RESOLVED.value


@pytest.mark.asyncio
async def test_manager_cannot_resolve_alert_outside_department() -> None:
    alert_department = ObjectId()
    repository = FakeAlertRepository(make_alert(alert_department))
    service = EarlyWarningService(repository, UnusedRepository(), UnusedRepository())

    with pytest.raises(HTTPException) as forbidden:
        await service.resolve(
            str(repository.alert.id),
            ObjectId(),
            str(ObjectId()),
            AlertResolveRequest(),
        )

    assert forbidden.value.status_code == 403


@pytest.mark.asyncio
async def test_resolve_returns_committed_state_when_another_request_wins_race() -> None:
    class RaceRepository(FakeAlertRepository):
        async def resolve_if_open(self, _alert_id: ObjectId, values: dict):
            self.alert = self.alert.model_copy(update=values)
            return None

    department_id = ObjectId()
    repository = RaceRepository(make_alert(department_id))
    service = EarlyWarningService(repository, UnusedRepository(), UnusedRepository())

    resolved = await service.resolve(
        str(repository.alert.id),
        department_id,
        str(ObjectId()),
        AlertResolveRequest(resolution_note="Đã xử lý ở request đồng thời"),
    )

    assert resolved.status == AlertStatus.RESOLVED
