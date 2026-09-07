import logging
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from bson import ObjectId
from fastapi import HTTPException, status
from pymongo.errors import PyMongoError

from app.core.time import BusinessClock
from app.events.event_bus import ALERT_CREATED, event_bus
from app.models.alert import (
    AlertDocument,
    AlertResolveRequest,
    AlertResponse,
    AlertStatus,
    DepartmentAlertSummaryResponse,
)
from app.models.employee import EmployeeDocument
from app.models.overload import OverloadLogDocument
from app.repositories.alert_repository import AlertRepository
from app.repositories.performance_repository import PerformanceRepository
from app.repositories.threshold_repository import ThresholdConfigRepository
from app.services.department_service import parse_object_id
from app.services.early_warning_detector import EarlyWarningDetector

logger = logging.getLogger(__name__)


class EarlyWarningService:
    def __init__(
        self,
        alert_repository: AlertRepository,
        performance_repository: PerformanceRepository,
        threshold_repository: ThresholdConfigRepository,
        clock: BusinessClock | None = None,
    ) -> None:
        self.alert_repository = alert_repository
        self.performance_repository = performance_repository
        self.threshold_repository = threshold_repository
        self._clock = clock or BusinessClock()

    @staticmethod
    def _response(document: AlertDocument) -> AlertResponse:
        return AlertResponse(
            id=str(document.id),
            alert_type=document.alert_type,
            severity=document.severity,
            status=document.status,
            employee_id=str(document.employee_id),
            department_id=str(document.department_id),
            employee_code=document.employee_code,
            employee_name=document.employee_name,
            title=document.title,
            message=document.message,
            suggested_action=document.suggested_action,
            detected_dates=document.detected_dates,
            resolution_note=document.resolution_note,
            resolved_by=str(document.resolved_by) if document.resolved_by else None,
            resolved_at=document.resolved_at,
            created_at=document.created_at,
            updated_at=document.updated_at,
        )

    async def list_alerts(
        self,
        scope: ObjectId | None,
        alert_status: str | None = None,
        alert_type: str | None = "early_warning",
    ) -> list[AlertResponse]:
        return [
            self._response(document)
            for document in await self.alert_repository.find_many(scope, alert_status, alert_type)
        ]

    async def list_department_summaries(self) -> list[DepartmentAlertSummaryResponse]:
        return [
            DepartmentAlertSummaryResponse.model_validate(document)
            for document in await self.alert_repository.list_department_summaries()
        ]

    async def resolve(
        self,
        alert_id: str,
        scope: ObjectId | None,
        resolved_by: str,
        request: AlertResolveRequest,
    ) -> AlertResponse:
        object_id = parse_object_id(alert_id, "Mã cảnh báo")
        alert = await self.alert_repository.find_by_id(object_id)
        if alert is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy cảnh báo"
            )
        if scope is not None and alert.department_id != scope:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bạn không có quyền xử lý cảnh báo ngoài phòng ban",
            )
        if alert.status == AlertStatus.RESOLVED:
            return self._response(alert)
        now = self._clock.now()
        updated = await self.alert_repository.update(
            object_id,
            {
                "status": AlertStatus.RESOLVED.value,
                "resolution_note": (
                    request.resolution_note.strip() if request.resolution_note else None
                ),
                "resolved_by": parse_object_id(resolved_by, "Mã người xử lý"),
                "resolved_at": now,
                "updated_at": now,
            },
        )
        if updated is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy cảnh báo"
            )
        return self._response(updated)

    async def scan_all(self, scope: ObjectId | None) -> list[AlertResponse]:
        await self.alert_repository.ensure_indexes()
        employees = await self.performance_repository.list_employees(scope)
        created: list[AlertResponse] = []
        for employee in employees:
            alerts = await self.scan_employee(employee)
            created.extend(self._response(alert) for alert in alerts)
        return created

    async def scan_employee(self, employee: EmployeeDocument) -> list[AlertDocument]:
        department = await self.performance_repository.find_department(employee.department_id)
        if department is None:
            return []
        config = await self.threshold_repository.find_approved(employee.department_id)
        detector = EarlyWarningDetector(
            self.performance_repository, self.alert_repository, clock=self._clock
        )
        return await detector.detect_for_employee(employee, department.name, config)

    async def handle_metric_created(self, payload: dict) -> None:
        employee_id = payload.get("employee_id")
        if not isinstance(employee_id, ObjectId):
            return
        try:
            await self.alert_repository.ensure_indexes()
            employee = await self.performance_repository.find_employee(employee_id)
            if employee:
                await self.scan_employee(employee)
        except (PyMongoError, ValueError, TypeError):
            logger.exception("Không thể xử lý employee_id từ event hiệu suất")


def create_metric_event_handler(
    database_provider: Callable[[], Any], clock: BusinessClock | None = None
):
    async def handle(payload: dict) -> None:
        database = database_provider()
        service = EarlyWarningService(
            AlertRepository(database),
            PerformanceRepository(database),
            ThresholdConfigRepository(database),
            clock=clock or BusinessClock(),
        )
        await service.handle_metric_created(payload)

    return handle


def create_overload_alert_event_handler(
    database_provider: Callable[[], Any], clock: BusinessClock | None = None
):
    """Translate overload events into high alerts; Change Stream handles delivery."""

    async def handle(payload: dict[str, Any]) -> None:
        log = payload.get("log")
        employee = payload.get("employee")
        if not isinstance(log, OverloadLogDocument) or not isinstance(employee, EmployeeDocument):
            return
        try:
            repository = AlertRepository(database_provider())
            await repository.ensure_indexes()
            reasons = [reason.value for reason in log.trigger_reason]
            fingerprint = (
                f"overload:{log.employee_id}:{log.date.isoformat()}:{','.join(sorted(reasons))}"
            )
            if await repository.find_by_fingerprint(fingerprint):
                return
            reason_labels = {
                "task_volume": "khối lượng công việc trong ngày vượt mức 4 công việc",
                "quality_drop": "chất lượng công việc giảm ít nhất 20% trong 3 ngày liên tiếp",
            }
            reason_text = " và ".join(reason_labels.get(reason, reason) for reason in reasons)
            now = (clock or BusinessClock()).now()
            document = {
                "_id": ObjectId(),
                "alert_type": "overload",
                "severity": "high",
                "status": AlertStatus.OPEN.value,
                "employee_id": employee.id,
                "department_id": employee.department_id,
                "employee_code": employee.employee_code,
                "employee_name": employee.full_name,
                "title": "Cảnh báo quá tải công việc",
                "message": f"{employee.full_name} có dấu hiệu quá tải vì {reason_text}.",
                "suggested_action": (
                    "Nên rà soát ngay khối lượng công việc và phân bớt công việc cho nhân viên "
                    "cùng phòng đang còn khả năng tiếp nhận."
                ),
                "detected_dates": [
                    datetime.combine(log.date, datetime.min.time(), tzinfo=timezone.utc)
                ],
                "fingerprint": fingerprint,
                "created_at": now,
                "updated_at": now,
            }
            created = await repository.insert(document)
            await event_bus.publish(ALERT_CREATED, created)
        except (PyMongoError, ValueError, TypeError):
            # Keep metric ingestion available if alert persistence is temporarily unavailable.
            logger.exception("Không thể tạo cảnh báo quá tải từ event")

    return handle


__all__ = [
    "EarlyWarningService",
    "create_metric_event_handler",
    "create_overload_alert_event_handler",
]
