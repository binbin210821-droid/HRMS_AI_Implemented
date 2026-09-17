from datetime import date as Date
from typing import Any

from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from app.core.time import BusinessClock
from app.core.workload_policy import DAILY_WORKLOAD_CAPACITY
from app.events.event_bus import OVERLOAD_DETECTED, EventBus, event_bus
from app.models.employee import EmployeeDocument
from app.models.overload import OverloadLogDocument, OverloadTriggerReason
from app.models.performance import PerformanceMetricDocument
from app.repositories.overload_repository import OverloadRepository


class OverloadDetector:
    """Detects hard overload rules without creating alerts or using WebSockets."""

    TASK_VOLUME_LIMIT = DAILY_WORKLOAD_CAPACITY
    QUALITY_DROP_PERCENT = 20.0
    BASELINE_DAYS = 7
    QUALITY_WINDOW_DAYS = 3

    def __init__(
        self,
        repository: OverloadRepository,
        bus: EventBus = event_bus,
        clock: BusinessClock | None = None,
    ) -> None:
        self.repository = repository
        self.bus = bus
        self._clock = clock or BusinessClock()

    async def detect_for_employee(self, employee: EmployeeDocument) -> list[OverloadLogDocument]:
        metrics = await self.repository.find_metrics(employee.id)
        events = self._find_overload_events(employee, metrics)
        created: list[OverloadLogDocument] = []
        for event in events:
            reasons = [reason.value for reason in event["trigger_reason"]]
            if await self.repository.find_by_fingerprint(employee.id, event["date"], reasons):
                continue
            document: dict[str, Any] = {
                "_id": ObjectId(),
                "employee_id": employee.id,
                "department_id": employee.department_id,
                "date": event["date"],
                "trigger_reason": reasons,
                "tasks_completed": event["tasks_completed"],
                "quality_score": event["quality_score"],
                "baseline_quality_avg": event["baseline_quality_avg"],
                "created_at": self._clock.now(),
            }
            try:
                log = await self.repository.insert_log(document)
            except DuplicateKeyError:
                continue
            created.append(log)
            await self.bus.publish(
                OVERLOAD_DETECTED,
                {"log": log, "employee": employee},
            )
        return created

    async def detect_for_scope(self, department_id: ObjectId | None) -> list[OverloadLogDocument]:
        created: list[OverloadLogDocument] = []
        for employee in await self.repository.list_employees(department_id):
            created.extend(await self.detect_for_employee(employee))
        return created

    @classmethod
    def _find_overload_events(
        cls, employee: EmployeeDocument, metrics: list[PerformanceMetricDocument]
    ) -> list[dict[str, Any]]:
        events: dict[Date, dict[str, Any]] = {}
        for metric in metrics:
            if metric.tasks_completed > cls.TASK_VOLUME_LIMIT:
                event = events.setdefault(
                    metric.date,
                    {
                        "date": metric.date,
                        "trigger_reason": [],
                        "tasks_completed": metric.tasks_completed,
                        "quality_score": metric.quality_score,
                        "baseline_quality_avg": None,
                    },
                )
                event["trigger_reason"].append(OverloadTriggerReason.TASK_VOLUME)

        for index in range(cls.BASELINE_DAYS, len(metrics) - cls.QUALITY_WINDOW_DAYS + 1):
            baseline = metrics[index - cls.BASELINE_DAYS : index]
            window = metrics[index : index + cls.QUALITY_WINDOW_DAYS]
            if not cls._is_quality_drop_window(baseline, window):
                continue
            last = window[-1]
            baseline_average = round(
                sum(metric.quality_score for metric in baseline) / len(baseline), 2
            )
            event = events.setdefault(
                last.date,
                {
                    "date": last.date,
                    "trigger_reason": [],
                    "tasks_completed": last.tasks_completed,
                    "quality_score": last.quality_score,
                    "baseline_quality_avg": baseline_average,
                },
            )
            if OverloadTriggerReason.QUALITY_DROP not in event["trigger_reason"]:
                event["trigger_reason"].append(OverloadTriggerReason.QUALITY_DROP)
            event["baseline_quality_avg"] = baseline_average
        return sorted(events.values(), key=lambda event: event["date"])

    @classmethod
    def _is_quality_drop_window(
        cls,
        baseline: list[PerformanceMetricDocument],
        window: list[PerformanceMetricDocument],
    ) -> bool:
        if len(baseline) != cls.BASELINE_DAYS or len(window) != cls.QUALITY_WINDOW_DAYS:
            return False
        if not cls._is_consecutive(baseline) or not cls._is_consecutive(window):
            return False
        if (window[0].date - baseline[-1].date).days != 1:
            return False
        baseline_average = sum(metric.quality_score for metric in baseline) / len(baseline)
        threshold = baseline_average * (1 - cls.QUALITY_DROP_PERCENT / 100)
        return all(metric.quality_score <= threshold for metric in window)

    @staticmethod
    def _is_consecutive(metrics: list[PerformanceMetricDocument]) -> bool:
        return all(
            (metrics[index].date - metrics[index - 1].date).days == 1
            for index in range(1, len(metrics))
        )


__all__ = ["OverloadDetector"]
