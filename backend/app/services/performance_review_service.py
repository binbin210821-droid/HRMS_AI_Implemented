from datetime import date as Date
from datetime import datetime, timedelta, timezone
from typing import Any, ClassVar

from bson import ObjectId
from fastapi import HTTPException, status

from app.core.config import get_settings
from app.core.time import BusinessClock
from app.events.event_bus import PERFORMANCE_METRIC_CREATED, event_bus
from app.infrastructure.evidence_storage import EvidenceStorage
from app.models.task import TaskDocument, TaskStatus
from app.models.task_execution import (
    DailyPerformanceReviewCreate,
    DailyPerformanceReviewResponse,
    DailyPerformanceReviewSummary,
    DailyReviewAttachmentResponse,
    DailyReviewDownloadUrlResponse,
    DailyReviewEmployeeResponse,
    DailyReviewTaskResponse,
    EvidenceStatus,
    TaskExecutionOutcome,
)
from app.repositories.performance_repository import PerformanceRepository
from app.repositories.task_execution_repository import TaskExecutionRepository
from app.repositories.task_repository import TaskRepository
from app.services.department_service import parse_object_id
from app.services.performance_score_calculator import PerformanceScoreCalculator


class PerformanceReviewService:
    PRIORITY_WEIGHTS: ClassVar[dict[str, float]] = {"low": 1.0, "medium": 1.25, "high": 1.5}

    def __init__(
        self,
        task_repository: TaskRepository,
        report_repository: TaskExecutionRepository,
        performance_repository: PerformanceRepository,
        storage: EvidenceStorage,
        clock: BusinessClock | None = None,
    ) -> None:
        self.tasks = task_repository
        self.reports = report_repository
        self.performance = performance_repository
        self.storage = storage
        self._clock = clock or BusinessClock()
        self.storage_ttl = get_settings().storage_signed_url_ttl

    async def get_review(
        self, employee_id: str, review_date: Date, scope: ObjectId | None
    ) -> DailyPerformanceReviewResponse:
        await self.reports.ensure_indexes()
        employee_object_id = self._employee_id(employee_id)
        employee = await self.tasks.find_employee(employee_object_id, scope)
        if employee is None:
            raise self._not_found("Nhân viên không tồn tại hoặc ngoài phạm vi phòng ban")
        tasks = await self._review_tasks(employee_object_id, review_date)
        reports = await self.reports.list_for_employee_date(employee_object_id, review_date)
        return await self._response(employee, review_date, tasks, reports)

    async def get_attachment_download_url(
        self,
        employee_id: str,
        review_date: Date,
        attachment_id: str,
        scope: ObjectId | None,
    ) -> DailyReviewDownloadUrlResponse:
        employee_object_id = self._employee_id(employee_id)
        employee = await self.tasks.find_employee(employee_object_id, scope)
        if employee is None:
            raise self._not_found("Nhân viên không tồn tại hoặc ngoài phạm vi phòng ban")
        reports = await self.reports.list_for_employee_date(employee_object_id, review_date)
        attachment = next(
            (
                item
                for report in reports
                for item in report.attachments
                if item.attachment_id == attachment_id
                or (item.attachment_id is None and item.checksum == attachment_id)
            ),
            None,
        )
        if attachment is None:
            raise self._not_found("Không tìm thấy minh chứng công việc")
        try:
            url = await self.storage.signed_url(attachment.storage_key)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Không thể tạo liên kết tải minh chứng, vui lòng thử lại sau",
            ) from exc
        if not url:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Kho lưu trữ chưa sẵn sàng để tải minh chứng",
            )
        return DailyReviewDownloadUrlResponse(
            url=url,
            expires_at=self._clock.now() + timedelta(seconds=self.storage_ttl),
        )

    async def save_review(
        self,
        request: DailyPerformanceReviewCreate,
        scope: ObjectId | None,
        reviewed_by: str,
        *,
        allow_update: bool = False,
        reason: str | None = None,
    ) -> DailyPerformanceReviewResponse:
        if scope is None:
            raise self._forbidden("Lãnh đạo không trực tiếp nghiệm thu hiệu suất nhân viên")
        await self.reports.ensure_indexes()
        await self.performance.ensure_indexes()
        employee_id = self._employee_id(request.employee_id)
        employee = await self.tasks.find_employee(employee_id, scope)
        if employee is None:
            raise self._forbidden("Không thể nghiệm thu nhân viên ngoài phòng ban")

        tasks = await self._review_tasks(employee_id, request.date)
        task_by_id = {task.id: task for task in tasks}
        submitted_ids = [self._task_id(item.task_id) for item in request.items]
        if len(set(submitted_ids)) != len(submitted_ids):
            raise self._unprocessable("Mỗi công việc chỉ được đánh giá một lần")
        if set(submitted_ids) != set(task_by_id):
            raise self._unprocessable("Vui lòng đánh giá đầy đủ các công việc trong ngày")

        reports = {
            report.task_id: report
            for report in await self.reports.list_for_employee_date(employee_id, request.date)
        }
        has_existing_review = any(report.manager_review for report in reports.values())
        existing_metric = await self.performance.find_by_employee_date(employee_id, request.date)
        has_existing_review = has_existing_review or existing_metric is not None
        if has_existing_review and not allow_update:
            raise self._conflict(
                "Nhân viên đã được nghiệm thu trong ngày này; hãy chọn Thay đổi điểm nếu cần chỉnh sửa"
            )
        if allow_update and not has_existing_review:
            raise self._conflict("Chưa có lần nghiệm thu nào trong ngày này để thay đổi")
        reviewer_id = self._user_id(reviewed_by)
        now = self._clock.now()
        quality_total = 0.0
        weight_total = 0.0
        evidence_count = 0
        review_entries: list[dict] = []
        audit_entries: list[dict] = []
        operation_reason = reason.strip() if reason and reason.strip() else None
        for item, task_id in zip(request.items, submitted_ids, strict=True):
            report = reports.get(task_id)
            attachments = report.attachments if report else []
            existing_review = report.manager_review if report else None
            change_reason = item.change_reason.strip() if item.change_reason else None
            score_changed = bool(
                allow_update and existing_review is not None and item.score != existing_review.score
            )
            if score_changed and not change_reason:
                change_reason = operation_reason
            if score_changed and not change_reason:
                raise self._unprocessable(
                    f'Vui lòng nhập lý do thay đổi điểm cho công việc "{task_by_id[task_id].title}"'
                )
            reason = item.missing_reason.strip() if item.missing_reason else None
            if not attachments and not reason:
                raise self._unprocessable(
                    f'Vui lòng nhập lý do thiếu minh chứng cho công việc "{task_by_id[task_id].title}"'
                )
            if attachments:
                evidence_count += 1
            weight = self.PRIORITY_WEIGHTS.get(task_by_id[task_id].priority.value, 1.25)
            quality_total += item.score * weight
            weight_total += weight
            review_entries.append(
                {
                    "report": report,
                    "placeholder": self._placeholder_report(task_by_id[task_id], request.date, now),
                    "review": {
                        "score": item.score,
                        "note": item.note.strip() if item.note and item.note.strip() else None,
                        "change_reason": (
                            change_reason
                            if score_changed
                            else (existing_review.change_reason if existing_review else None)
                        ),
                        "evidence_status": (
                            EvidenceStatus.VERIFIED.value
                            if attachments
                            else EvidenceStatus.MISSING_WITH_REASON.value
                        ),
                        "missing_reason": reason,
                        "reviewed_by": reviewer_id,
                        "reviewed_at": now,
                    },
                    "updated_at": now,
                }
            )
            audit_entries.append(
                {
                    "action": (
                        "task_score_changed" if score_changed else "task_execution_review_updated"
                    ),
                    "actor_id": reviewer_id,
                    "task_id": task_id,
                    "employee_id": employee_id,
                    "department_id": employee.department_id,
                    "review_date": request.date,
                    "old_score": existing_review.score if existing_review else None,
                    "score": item.score,
                    "change_reason": change_reason if score_changed else None,
                    "created_at": now,
                }
            )

        async def persist(session: Any | None) -> Any:
            reviewed_reports = await self._repository_call(
                self.reports.bulk_update_manager_reviews,
                review_entries,
                session=session,
            )
            if any(task_id not in reviewed_reports for task_id in submitted_ids):
                raise self._conflict("Báo cáo thực thi vừa được cập nhật, vui lòng tải lại")

            tasks_completed = sum(
                task.status == TaskStatus.DONE
                and self._utc_date(task.completed_at) == request.date
                for task in tasks
            )
            quality_score = round(quality_total / weight_total, 2) if weight_total else 0.0
            metric = await self._repository_call(
                self.performance.upsert_daily_review,
                employee_id,
                request.date,
                {
                    "tasks_completed": tasks_completed,
                    "quality_score": quality_score,
                    "reviewed_by": reviewer_id,
                    "performance_score": PerformanceScoreCalculator.calculate(
                        tasks_completed, quality_score
                    ),
                    "note": "Đánh giá theo bằng chứng công việc",
                    "reviewed_task_count": len(tasks),
                    "evidence_task_count": evidence_count,
                    "total_review_task_count": len(tasks),
                    "updated_at": now,
                    "created_at": now,
                },
                session=session,
            )
            review_audit = {
                "action": (
                    "daily_performance_review_updated"
                    if allow_update
                    else "daily_performance_review_saved"
                ),
                "actor_id": reviewer_id,
                "employee_id": employee_id,
                "department_id": employee.department_id,
                "review_date": request.date,
                "metric_id": metric.id,
                "created_at": now,
            }
            if operation_reason:
                review_audit["change_reason"] = operation_reason
            audit_entries.append(review_audit)
            await self._repository_call(
                self.tasks.insert_audit_logs, audit_entries, session=session
            )
            return metric

        await self._run_write_transaction(persist)
        await event_bus.publish(PERFORMANCE_METRIC_CREATED, {"employee_id": employee_id})
        return await self.get_review(str(employee_id), request.date, scope)

    async def _run_write_transaction(self, operation: Any) -> Any:
        client = getattr(self.performance, "client", None)
        if client is None:
            return await operation(None)
        async with await client.start_session() as session:
            async with session.start_transaction():
                return await operation(session)

    async def _repository_call(
        self, method: Any, *args: Any, session: Any | None
    ) -> Any:
        if session is None:
            return await method(*args)
        return await method(*args, session=session)

    async def update_review(
        self,
        request: DailyPerformanceReviewCreate,
        scope: ObjectId | None,
        reviewed_by: str,
        *,
        reason: str | None = None,
    ) -> DailyPerformanceReviewResponse:
        return await self.save_review(request, scope, reviewed_by, allow_update=True, reason=reason)

    async def _review_tasks(self, employee_id: ObjectId, review_date: Date) -> list[TaskDocument]:
        tasks = await self.tasks.find_tasks_for_review(employee_id, review_date)
        reports = await self.reports.list_for_employee_date(employee_id, review_date)
        existing_ids = {task.id for task in tasks}
        report_ids = [report.task_id for report in reports if report.task_id not in existing_ids]
        if report_ids:
            tasks.extend(
                task
                for task in await self.tasks.find_tasks_by_ids(report_ids)
                if task.employee_id == employee_id
            )
        return sorted(tasks, key=lambda task: (task.due_date, task.created_at))

    async def _response(self, employee, review_date, tasks, reports):
        reports_by_task = {report.task_id: report for report in reports}
        response_tasks = []
        reviewed_count = 0
        missing_count = 0
        evidence_count = 0
        weighted_total = 0.0
        weight_total = 0.0
        for task in tasks:
            report = reports_by_task.get(task.id)
            review = report.manager_review if report else None
            attachments = []
            if report:
                for attachment in report.attachments:
                    attachments.append(
                        DailyReviewAttachmentResponse(
                            attachment_id=attachment.attachment_id or attachment.checksum,
                            file_name=attachment.file_name,
                            content_type=attachment.content_type,
                            file_size=attachment.file_size,
                            checksum=attachment.checksum,
                        )
                    )
            if review:
                reviewed_count += 1
                weight = self.PRIORITY_WEIGHTS.get(task.priority.value, 1.25)
                weighted_total += review.score * weight
                weight_total += weight
            if report and report.attachments:
                evidence_count += 1
            elif not report or not report.attachments:
                missing_count += 1
            response_tasks.append(
                DailyReviewTaskResponse(
                    id=str(task.id),
                    title=task.title,
                    description=task.description,
                    priority=task.priority.value,
                    status=task.status.value,
                    due_date=task.due_date,
                    subtask_count=len(task.subtasks),
                    completed_at=task.completed_at,
                    result_summary=report.result_summary if report else None,
                    progress_percent=report.progress_percent if report else 0,
                    outcome_status=(
                        report.outcome_status if report else TaskExecutionOutcome.IN_PROGRESS
                    ),
                    attachments=attachments,
                    evidence_status=review.evidence_status if review else None,
                    score=review.score if review else None,
                    note=review.note if review else None,
                    missing_reason=review.missing_reason if review else None,
                    change_reason=review.change_reason if review else None,
                )
            )
        tasks_completed = sum(
            task.status == TaskStatus.DONE and self._utc_date(task.completed_at) == review_date
            for task in tasks
        )
        quality_score = round(weighted_total / weight_total, 2) if weight_total else None
        can_finalize = (
            bool(tasks)
            and reviewed_count == len(tasks)
            and all(
                report.attachments
                or (report.manager_review and report.manager_review.missing_reason)
                for report in reports_by_task.values()
            )
        )
        performance_score = (
            PerformanceScoreCalculator.calculate(tasks_completed, quality_score)
            if quality_score is not None
            else None
        )
        return DailyPerformanceReviewResponse(
            employee=DailyReviewEmployeeResponse(
                id=str(employee.id),
                full_name=employee.full_name,
                employee_code=employee.employee_code,
            ),
            date=review_date,
            tasks=response_tasks,
            summary=DailyPerformanceReviewSummary(
                tasks_completed=tasks_completed,
                reviewed_task_count=reviewed_count,
                missing_evidence_count=missing_count,
                quality_score=quality_score,
                performance_score=performance_score,
                can_finalize=can_finalize,
            ),
        )

    @staticmethod
    def _placeholder_report(task: TaskDocument, work_date: Date, now: datetime) -> dict:
        return {
            "_id": ObjectId(),
            "task_id": task.id,
            "employee_id": task.employee_id,
            "department_id": task.department_id,
            "work_date": work_date,
            "result_summary": None,
            "progress_percent": 100 if task.status == TaskStatus.DONE else 0,
            "outcome_status": (
                TaskExecutionOutcome.COMPLETED.value
                if task.status == TaskStatus.DONE
                else TaskExecutionOutcome.IN_PROGRESS.value
            ),
            "attachments": [],
            "created_at": now,
            "updated_at": now,
        }

    def _utc_date(self, value: datetime | None) -> Date | None:
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(self._clock.timezone).date()

    @staticmethod
    def _employee_id(value: str) -> ObjectId:
        return parse_object_id(value, "Mã nhân viên")

    @staticmethod
    def _task_id(value: str) -> ObjectId:
        return parse_object_id(value, "Mã công việc")

    @staticmethod
    def _user_id(value: str) -> ObjectId:
        return parse_object_id(value, "Mã người chấm")

    @staticmethod
    def _not_found(message: str) -> HTTPException:
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=message)

    @staticmethod
    def _forbidden(message: str) -> HTTPException:
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=message)

    @staticmethod
    def _unprocessable(message: str) -> HTTPException:
        return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=message)

    @staticmethod
    def _conflict(message: str) -> HTTPException:
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=message)


__all__ = ["PerformanceReviewService"]
