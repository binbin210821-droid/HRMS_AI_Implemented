from datetime import datetime, timezone
from typing import Any

from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from app.core.time import BusinessClock
from app.events.event_bus import ALERT_CREATED, EventBus, event_bus
from app.models.alert import AlertDocument, AlertSeverity, AlertStatus
from app.models.employee import EmployeeDocument
from app.models.performance import PerformanceMetricDocument
from app.models.threshold import ThresholdConfigDocument
from app.repositories.alert_repository import AlertRepository
from app.repositories.performance_repository import PerformanceRepository


class EarlyWarningDetector:
    """Nhận diện xu hướng task tăng và chất lượng giảm trước khi quá tải cứng."""

    DEFAULT_CONSECUTIVE_DAYS = 3
    DEFAULT_QUALITY_DROP_PERCENT = 20.0

    def __init__(
        self,
        performance_repository: PerformanceRepository,
        alert_repository: AlertRepository,
        bus: EventBus = event_bus,
        clock: BusinessClock | None = None,
    ) -> None:
        self.performance_repository = performance_repository
        self.alert_repository = alert_repository
        self.bus = bus
        self._clock = clock or BusinessClock()

    async def detect_for_employee(
        self,
        employee: EmployeeDocument,
        department_name: str,
        config: ThresholdConfigDocument | None = None,
    ) -> list[AlertDocument]:
        consecutive_days = config.consecutive_days if config else self.DEFAULT_CONSECUTIVE_DAYS
        quality_drop_percent = (
            config.quality_drop_percent if config else self.DEFAULT_QUALITY_DROP_PERCENT
        )
        metrics = await self.performance_repository.find_employee_metrics(employee.id)
        if len(metrics) < consecutive_days:
            return []

        created_alerts: list[AlertDocument] = []
        for start in range(len(metrics) - consecutive_days + 1):
            window = metrics[start : start + consecutive_days]
            if not self._is_consecutive(window):
                continue
            if not self._is_early_warning(window, quality_drop_percent):
                continue
            alert = await self._create_alert(employee, department_name, window)
            if alert is not None:
                created_alerts.append(alert)
        return created_alerts

    @staticmethod
    def _is_consecutive(window: list[PerformanceMetricDocument]) -> bool:
        return all(
            (window[index].date - window[index - 1].date).days == 1
            for index in range(1, len(window))
        )

    @staticmethod
    def _is_early_warning(window: list[PerformanceMetricDocument], drop_percent: float) -> bool:
        tasks_increase = all(
            window[index - 1].tasks_completed < window[index].tasks_completed
            for index in range(1, len(window))
        )
        quality_decrease = all(
            window[index - 1].quality_score > window[index].quality_score
            for index in range(1, len(window))
        )
        first_quality = window[0].quality_score
        quality_drop = (
            ((first_quality - window[-1].quality_score) / first_quality * 100)
            if first_quality > 0
            else 100.0
        )
        return tasks_increase and quality_decrease and quality_drop < drop_percent

    async def _create_alert(
        self,
        employee: EmployeeDocument,
        department_name: str,
        window: list[PerformanceMetricDocument],
    ) -> AlertDocument | None:
        first_date = window[0].date
        last_date = window[-1].date
        fingerprint = (
            f"early_warning:{employee.id}:{first_date.isoformat()}:{last_date.isoformat()}"
        )
        if await self.alert_repository.find_by_fingerprint(fingerprint):
            return None

        now = self._clock.now()
        document: dict[str, Any] = {
            "_id": ObjectId(),
            "alert_type": "early_warning",
            "severity": AlertSeverity.MEDIUM.value,
            "status": AlertStatus.OPEN.value,
            "employee_id": employee.id,
            "department_id": employee.department_id,
            "employee_code": employee.employee_code,
            "employee_name": employee.full_name,
            "title": "Dấu hiệu tiềm ẩn quá tải",
            "message": (
                f"{employee.full_name} đang tăng số công việc nhưng chất lượng giảm "
                f"liên tiếp {len(window)} ngày ({first_date} đến {last_date}) tại {department_name}."
            ),
            "suggested_action": "Nên theo dõi khối lượng công việc và cân nhắc phân bớt việc nếu xu hướng tiếp diễn.",
            "detected_dates": [
                datetime.combine(metric.date, datetime.min.time(), tzinfo=timezone.utc)
                for metric in window
            ],
            "fingerprint": fingerprint,
            "created_at": now,
            "updated_at": now,
        }
        try:
            created = await self.alert_repository.insert(document)
        except DuplicateKeyError:
            return None
        await self.bus.publish(ALERT_CREATED, created)
        return created


__all__ = ["EarlyWarningDetector"]
