import logging
from collections.abc import Callable
from typing import Any

from bson import ObjectId
from fastapi import HTTPException, status
from pymongo.errors import PyMongoError

from app.core.time import BusinessClock
from app.models.overload import (
    OverloadLogDocument,
    OverloadLogResponse,
    OverloadScanResponse,
)
from app.repositories.overload_repository import OverloadRepository
from app.services.overload_detector import OverloadDetector
from app.services.workload_rebalancer import WorkloadRebalancer

logger = logging.getLogger(__name__)

TRIGGER_REASON_LABELS = {
    "task_volume": "Khối lượng công việc cao",
    "quality_drop": "Chất lượng công việc giảm mạnh",
}


class OverloadService:
    def __init__(self, repository: OverloadRepository, clock: BusinessClock | None = None) -> None:
        self.repository = repository
        self._clock = clock or BusinessClock()
        self.rebalancer = WorkloadRebalancer(repository)

    @staticmethod
    def _response(log: OverloadLogDocument, suggestions) -> OverloadLogResponse:
        reasons = [reason.value for reason in log.trigger_reason]
        return OverloadLogResponse(
            id=str(log.id),
            employee_id=str(log.employee_id),
            department_id=str(log.department_id),
            employee_code="",
            employee_name="",
            date=log.date,
            trigger_reason=log.trigger_reason,
            trigger_reason_labels=[TRIGGER_REASON_LABELS.get(reason, reason) for reason in reasons],
            tasks_completed=log.tasks_completed,
            quality_score=log.quality_score,
            baseline_quality_avg=log.baseline_quality_avg,
            suggested_candidates=suggestions,
            created_at=log.created_at,
        )

    async def _response_with_employee(self, log: OverloadLogDocument) -> OverloadLogResponse:
        employee = await self.repository.find_employee(log.employee_id)
        if employee is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy nhân viên"
            )
        suggestions = await self.rebalancer.suggest(log)
        response = self._response(log, suggestions)
        response.employee_code = employee.employee_code
        response.employee_name = employee.full_name
        return response

    async def _responses_with_context(
        self, logs: list[OverloadLogDocument]
    ) -> list[OverloadLogResponse]:
        if not logs:
            return []
        employees = await self.repository.find_employees(list({log.employee_id for log in logs}))
        candidates_by_group = await self.rebalancer.suggest_many(logs)
        responses: list[OverloadLogResponse] = []
        for log in logs:
            employee = employees.get(log.employee_id)
            if employee is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy nhân viên"
                )
            candidates = [
                candidate
                for candidate in candidates_by_group[(log.department_id, log.date)]
                if candidate.employee_id != str(log.employee_id)
            ]
            response = self._response(log, candidates)
            response.employee_code = employee.employee_code
            response.employee_name = employee.full_name
            responses.append(response)
        return responses

    async def list_logs(self, scope: ObjectId | None) -> list[OverloadLogResponse]:
        logs = await self.repository.list_logs(scope)
        return await self._responses_with_context(logs)

    async def scan(self, scope: ObjectId | None) -> OverloadScanResponse:
        await self.repository.ensure_indexes()
        detector = OverloadDetector(self.repository, clock=self._clock)
        created = await detector.detect_for_scope(scope)
        return OverloadScanResponse(
            created_count=len(created),
            logs=await self._responses_with_context(created),
        )

    async def handle_metric_created(self, payload: dict[str, Any]) -> None:
        employee_id = payload.get("employee_id")
        if not isinstance(employee_id, ObjectId):
            return
        try:
            employee = await self.repository.find_employee(employee_id)
            if employee is not None:
                await OverloadDetector(self.repository, clock=self._clock).detect_for_employee(employee)
        except (PyMongoError, ValueError, TypeError):
            logger.exception("Không thể phân tích quá tải từ event hiệu suất")


def create_overload_metric_event_handler(
    database_provider: Callable[[], Any], clock: BusinessClock | None = None
):
    async def handle(payload: dict[str, Any]) -> None:
        service = OverloadService(OverloadRepository(database_provider()), clock=clock or BusinessClock())
        await service.handle_metric_created(payload)

    return handle


__all__ = ["OverloadService", "create_overload_metric_event_handler"]
