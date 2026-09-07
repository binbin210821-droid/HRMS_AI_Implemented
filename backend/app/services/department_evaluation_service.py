from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date as Date
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, ClassVar, List
from uuid import uuid4
from zoneinfo import ZoneInfo

from bson import ObjectId
from fastapi import HTTPException, status
from pymongo.errors import DuplicateKeyError

from app.core.config import Settings, get_settings
from app.core.time import BusinessClock
from app.infrastructure.evidence_storage import EvidenceStorage
from app.infrastructure.malware_scanner import (
    MalwareScanner,
    ScanResult,
    create_malware_scanner,
)
from app.models.department_evaluation import (
    DepartmentDirectiveEvidence,
    DepartmentDirectiveEvidenceItem,
    DepartmentEvaluationAttachment,
    DepartmentEvaluationAttachmentMetadata,
    DepartmentEvaluationDownloadUrlResponse,
    DepartmentEvaluationEvidenceSnapshot,
    DepartmentIndicatorDeltas,
    DepartmentStabilityEvidence,
    DepartmentWeeklyEvaluationDocument,
    DepartmentWeeklyEvaluationListItemResponse,
    DepartmentWeeklyEvaluationListResponse,
    DepartmentWeeklyEvaluationPayload,
    DepartmentWeeklyEvaluationResponse,
    DepartmentWeeklyEvaluationUpdatePayload,
    DepartmentWeeklyIndicators,
    DepartmentWeeklyReviewResponse,
    DirectiveTimingStatus,
    StabilityStatus,
)
from app.repositories.department_evaluation_repository import DepartmentEvaluationRepository
from app.services.attachment_upload_service import AttachmentUploadService
from app.services.department_service import parse_object_id


@dataclass(slots=True)
class EvaluationUpload:
    file_name: str
    content_type: str
    content: bytes


class DepartmentEvaluationService:
    """Weekly department evaluation backed by immutable evidence snapshots."""

    _ALLOWED_EXTENSIONS: ClassVar[set[str]] = {
        ".pdf",
        ".doc",
        ".docx",
        ".xls",
        ".xlsx",
        ".ppt",
        ".pptx",
        ".txt",
        ".png",
        ".jpg",
        ".jpeg",
    }
    _CONTENT_TYPES_BY_EXTENSION: ClassVar[dict[str, set[str]]] = {
        ".pdf": {"application/pdf"},
        ".doc": {"application/msword"},
        ".docx": {"application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
        ".xls": {"application/vnd.ms-excel"},
        ".xlsx": {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
        ".ppt": {"application/vnd.ms-powerpoint"},
        ".pptx": {"application/vnd.openxmlformats-officedocument.presentationml.presentation"},
        ".txt": {"text/plain"},
        ".png": {"image/png"},
        ".jpg": {"image/jpeg"},
        ".jpeg": {"image/jpeg"},
    }

    def __init__(
        self,
        repository: DepartmentEvaluationRepository,
        storage: EvidenceStorage,
        settings: Settings | None = None,
        clock: BusinessClock | None = None,
        scanner: MalwareScanner | None = None,
        upload_service: AttachmentUploadService | None = None,
    ) -> None:
        self.repository = repository
        self.storage = storage
        self.settings = settings or get_settings()
        self.scanner = scanner or create_malware_scanner(self.settings)
        self.upload_service = upload_service
        self.business_timezone = ZoneInfo(self.settings.business_timezone)
        self._clock = clock or BusinessClock()

    async def weekly_review(
        self, department_id: str, week_start: Date
    ) -> DepartmentWeeklyReviewResponse:
        department_object_id = parse_object_id(department_id, "Mã phòng ban")
        department, manager = await self._department_context(department_object_id)
        week_end, cutoff = self._validate_week(week_start)
        now = self._now()
        existing = await self.repository.find_evaluation(department_object_id, week_start)
        evidence = (
            existing.evidence_snapshot
            if existing
            else await self._build_evidence(department_object_id, week_start, week_end, cutoff)
        )
        return DepartmentWeeklyReviewResponse(
            department_id=str(department.id),
            department_name=department.name,
            department_code=department.code,
            manager_id=str(manager.id) if manager else None,
            manager_name=manager.full_name if manager else None,
            week_start=week_start,
            week_end=week_end,
            available_from=cutoff,
            can_evaluate=now >= cutoff,
            evaluation_delay_days=self._delay_days(now, week_end),
            evidence=evidence,
            existing_evaluation=(await self._response(existing) if existing else None),
        )

    async def list(
        self,
        scope: ObjectId | None,
        requested_department_id: str | None,
        page: int = 1,
        page_size: int = 12,
    ) -> DepartmentWeeklyEvaluationListResponse:
        requested = (
            parse_object_id(requested_department_id, "Mã phòng ban")
            if requested_department_id
            else None
        )
        if scope is not None and requested is not None and requested != scope:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bạn không có quyền xem định hướng của phòng ban khác",
            )
        department_id = scope if scope is not None else requested
        documents, total = await self.repository.list_evaluations(
            department_id, page, page_size
        )
        items = [self._list_item(item) for item in documents]
        return DepartmentWeeklyEvaluationListResponse(
            items=items,
            page=page,
            page_size=page_size,
            total=total,
            has_next=page * page_size < total,
        )

    async def get(
        self, evaluation_id: str, scope: ObjectId | None
    ) -> DepartmentWeeklyEvaluationResponse:
        object_id = parse_object_id(evaluation_id, "Mã đánh giá phòng ban")
        document = await self.repository.find_evaluation_by_id(object_id)
        if document is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Không tìm thấy đánh giá phòng ban",
            )
        self._ensure_scope(document.department_id, scope)
        return await self._response(document)

    async def get_attachment_download_url(
        self,
        evaluation_id: str,
        attachment_id: str,
        scope: ObjectId | None,
    ) -> DepartmentEvaluationDownloadUrlResponse:
        object_id = parse_object_id(evaluation_id, "Mã đánh giá phòng ban")
        document = await self.repository.find_evaluation_by_id(object_id)
        if document is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Không tìm thấy đánh giá phòng ban",
            )
        self._ensure_scope(document.department_id, scope)
        attachment = next(
            (item for item in document.attachments if item.attachment_id == attachment_id),
            None,
        )
        if attachment is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Không tìm thấy tài liệu đính kèm",
            )
        try:
            url = await self.storage.signed_url(attachment.storage_key)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Không thể tạo liên kết tải tài liệu, vui lòng thử lại sau",
            ) from exc
        if not url:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Kho lưu trữ chưa sẵn sàng để tải tài liệu",
            )
        return DepartmentEvaluationDownloadUrlResponse(
            url=url,
            expires_at=self._now()
            + timedelta(seconds=self.settings.storage_signed_url_ttl),
        )

    async def create(
        self,
        payload: DepartmentWeeklyEvaluationPayload,
        uploads: List[EvaluationUpload],
        evaluated_by: str,
    ) -> DepartmentWeeklyEvaluationResponse:
        await self.repository.ensure_indexes()
        department_id = parse_object_id(payload.department_id, "Mã phòng ban")
        department, manager = await self._department_context(department_id)
        week_end, cutoff = self._validate_week(payload.week_start)
        now = self._now()
        self._require_available(now, cutoff)
        if await self.repository.find_evaluation(department_id, payload.week_start):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Phòng ban đã được đánh giá trong tuần này",
            )

        actor_id = parse_object_id(evaluated_by, "Mã người đánh giá")
        direct_session_ids = payload.attachment_session_ids
        if direct_session_ids and uploads:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Không thể dùng đồng thời tải trực tiếp và biểu mẫu tải tệp",
            )
        if direct_session_ids:
            if self.upload_service is None:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Tải trực tiếp chưa được cấu hình",
                )
            attachment_values = await self.upload_service.resolve_for_department_evaluation(
                direct_session_ids, evaluated_by, department_id, payload.week_start
            )
            attachments = [DepartmentEvaluationAttachment.model_validate(item) for item in attachment_values]
        else:
            attachments = await self._upload_files(department_id, payload.week_start, uploads)
        try:
            evidence = await self._build_evidence(
                department_id, payload.week_start, week_end, cutoff
            )
            document = {
                "_id": ObjectId(),
                "department_id": department_id,
                "department_name": department.name,
                "department_code": department.code,
                "manager_id": manager.id if manager else None,
                "manager_name": manager.full_name if manager else None,
                "week_start": payload.week_start,
                "week_end": week_end,
                "evidence_cutoff_at": cutoff,
                "directive_execution_score": payload.directive_execution_score,
                "stability_score": payload.stability_score,
                "timeliness_score": payload.timeliness_score,
                "overall_score": self._overall_score(payload),
                "assessment_note": self._clean_note(payload.assessment_note),
                "evidence_snapshot": evidence.model_dump(mode="python"),
                "attachments": [item.model_dump(mode="python") for item in attachments],
                "evaluated_by": actor_id,
                "evaluated_at": now,
                "evaluation_delay_days": self._delay_days(now, week_end),
                "created_at": now,
                "updated_at": now,
            }
            created = await self.repository.insert(document)
        except DuplicateKeyError:
            if direct_session_ids and self.upload_service:
                await self.upload_service.discard(direct_session_ids, evaluated_by)
            else:
                await self._delete_files(attachments)
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Phòng ban vừa được đánh giá trong tuần này",
            ) from None
        except Exception:
            if direct_session_ids and self.upload_service:
                await self.upload_service.discard(direct_session_ids, evaluated_by)
            else:
                await self._delete_files(attachments)
            raise
        if direct_session_ids and self.upload_service:
            await self.upload_service.commit(direct_session_ids)
        await self.repository.insert_audit_log(
            {
                "action": "department_weekly_evaluation_created",
                "actor_id": created.evaluated_by,
                "evaluation_id": created.id,
                "department_id": created.department_id,
                "week_start": created.week_start,
                "overall_score": created.overall_score,
                "attachment_count": len(created.attachments),
                "created_at": now,
            }
        )
        return await self._response(created)

    async def update(
        self,
        evaluation_id: str,
        payload: DepartmentWeeklyEvaluationUpdatePayload,
        uploads: List[EvaluationUpload],
        evaluated_by: str,
    ) -> DepartmentWeeklyEvaluationResponse:
        object_id = parse_object_id(evaluation_id, "Mã đánh giá phòng ban")
        existing = await self.repository.find_evaluation_by_id(object_id)
        if existing is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Không tìm thấy đánh giá phòng ban",
            )
        actor_id = parse_object_id(evaluated_by, "Mã người đánh giá")
        direct_session_ids = payload.attachment_session_ids
        if direct_session_ids and uploads:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Không thể dùng đồng thời tải trực tiếp và biểu mẫu tải tệp",
            )
        if direct_session_ids:
            if self.upload_service is None:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Tải trực tiếp chưa được cấu hình",
                )
            attachment_values = await self.upload_service.resolve_for_department_evaluation(
                direct_session_ids, evaluated_by, existing.department_id, existing.week_start
            )
            replacement = [
                DepartmentEvaluationAttachment.model_validate(item) for item in attachment_values
            ]
        else:
            replacement = (
                await self._upload_files(existing.department_id, existing.week_start, uploads)
                if uploads
                else existing.attachments
            )
        now = self._now()
        values = {
            "directive_execution_score": payload.directive_execution_score,
            "stability_score": payload.stability_score,
            "timeliness_score": payload.timeliness_score,
            "overall_score": self._overall_score(payload),
            "assessment_note": self._clean_note(payload.assessment_note),
            "attachments": [item.model_dump(mode="python") for item in replacement],
            "evaluated_by": actor_id,
            "updated_at": now,
        }
        try:
            updated = await self.repository.update(object_id, values)
        except Exception:
            if direct_session_ids and self.upload_service:
                await self.upload_service.discard(direct_session_ids, evaluated_by)
            elif uploads:
                await self._delete_files(replacement)
            raise
        if updated is None:
            if direct_session_ids and self.upload_service:
                await self.upload_service.discard(direct_session_ids, evaluated_by)
            elif uploads:
                await self._delete_files(replacement)
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Không tìm thấy đánh giá phòng ban",
            )
        if direct_session_ids and self.upload_service:
            await self.upload_service.commit(direct_session_ids)
        if uploads or direct_session_ids:
            await self._delete_files(existing.attachments)
        await self.repository.insert_audit_log(
            {
                "action": "department_weekly_evaluation_updated",
                "actor_id": updated.evaluated_by,
                "evaluation_id": updated.id,
                "department_id": updated.department_id,
                "week_start": updated.week_start,
                "overall_score": updated.overall_score,
                "attachments_replaced": bool(uploads or direct_session_ids),
                "created_at": now,
            }
        )
        return await self._response(updated)

    async def _department_context(self, department_id: ObjectId):
        department = await self.repository.find_department(department_id)
        if department is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy phòng ban"
            )
        return department, await self.repository.find_active_manager(department_id)

    def _validate_week(self, week_start: Date) -> tuple[Date, datetime]:
        if week_start.weekday() != 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Ngày bắt đầu kỳ đánh giá phải là thứ Hai",
            )
        current_monday = self._now().astimezone(self.business_timezone).date()
        current_monday -= timedelta(days=current_monday.weekday())
        if week_start > current_monday:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Không thể đánh giá tuần trong tương lai",
            )
        week_end = week_start + timedelta(days=4)
        cutoff_local = datetime.combine(
            week_end,
            time(hour=self.settings.weekly_evaluation_cutoff_hour),
            tzinfo=self.business_timezone,
        )
        return week_end, cutoff_local.astimezone(timezone.utc)

    @staticmethod
    def _require_available(now: datetime, cutoff: datetime) -> None:
        if now < cutoff:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Đánh giá tuần chỉ được lưu từ 17:00 thứ Sáu",
            )

    def _delay_days(self, now: datetime, week_end: Date) -> int:
        return max(0, (now.astimezone(self.business_timezone).date() - week_end).days)

    async def _build_evidence(
        self, department_id: ObjectId, week_start: Date, week_end: Date, cutoff: datetime
    ) -> DepartmentEvaluationEvidenceSnapshot:
        previous_start = week_start - timedelta(days=7)
        previous_end = week_end - timedelta(days=7)
        previous_cutoff = cutoff - timedelta(days=7)
        current_metrics = await self.repository.list_performance_metrics(
            department_id, week_start, week_end
        )
        previous_metrics = await self.repository.list_performance_metrics(
            department_id, previous_start, previous_end
        )
        tasks = await self.repository.list_tasks(department_id)
        alerts = await self.repository.list_alerts(department_id)
        current = self._indicators(current_metrics, tasks, alerts, week_start, week_end, cutoff)
        previous = self._indicators(
            previous_metrics,
            tasks,
            alerts,
            previous_start,
            previous_end,
            previous_cutoff,
        )
        deltas = DepartmentIndicatorDeltas(
            performance_score=self._float_delta(
                current.average_performance_score, previous.average_performance_score
            ),
            quality_score=self._float_delta(
                current.average_quality_score, previous.average_quality_score
            ),
            performance_metric_days=(
                current.performance_metric_days - previous.performance_metric_days
            ),
            performance_tasks_completed=(
                current.performance_tasks_completed - previous.performance_tasks_completed
            ),
            completed_tasks=current.completed_task_count - previous.completed_task_count,
            overdue_tasks=current.overdue_task_count - previous.overdue_task_count,
            early_warnings=current.early_warning_count - previous.early_warning_count,
            overload_alerts=current.overload_count - previous.overload_count,
            open_overload_alerts=(current.open_overload_count - previous.open_overload_count),
            resolved_alerts=(current.resolved_alert_count - previous.resolved_alert_count),
            open_alerts=current.open_alert_count - previous.open_alert_count,
        )
        stability = DepartmentStabilityEvidence(
            status=self._stability_status(current, previous, deltas),
            current=current,
            previous=previous,
            deltas=deltas,
        )
        alert_directives = await self.repository.list_alert_directives(department_id)
        task_directives = await self.repository.list_task_directives(department_id)
        directives = self._directive_evidence(
            alert_directives,
            task_directives,
            tasks,
            alerts,
            week_start,
            week_end,
            cutoff,
        )
        return DepartmentEvaluationEvidenceSnapshot(stability=stability, directives=directives)

    def _indicators(
        self,
        metrics: List[dict[str, Any]],
        tasks: List[dict[str, Any]],
        alerts: List[dict[str, Any]],
        period_start: Date,
        period_end: Date,
        cutoff: datetime,
    ) -> DepartmentWeeklyIndicators:
        period_metrics = [
            item
            for item in metrics
            if self._date_in_period(item.get("date"), period_start, period_end, cutoff)
        ]
        performance_values = [float(item.get("performance_score", 0)) for item in period_metrics]
        quality_values = [float(item.get("quality_score", 0)) for item in period_metrics]
        completed_tasks = [
            item
            for item in tasks
            if self._date_in_period(item.get("completed_at"), period_start, period_end, cutoff)
        ]
        overdue_tasks = [
            item
            for item in tasks
            if self._exists_at(item, cutoff)
            and self._as_date(item.get("due_date")) < period_end
            and not self._completed_by(item, cutoff)
        ]
        created_alerts = [
            item
            for item in alerts
            if self._date_in_period(item.get("created_at"), period_start, period_end, cutoff)
        ]
        resolved_alerts = [
            item
            for item in alerts
            if self._date_in_period(item.get("resolved_at"), period_start, period_end, cutoff)
        ]
        open_alerts = [
            item
            for item in alerts
            if self._exists_at(item, cutoff) and not self._resolved_by(item, cutoff)
        ]
        return DepartmentWeeklyIndicators(
            average_performance_score=self._average(performance_values),
            average_quality_score=self._average(quality_values),
            performance_metric_days=len(
                {
                    metric_date
                    for item in period_metrics
                    if (metric_date := self._optional_date(item.get("date"))) is not None
                }
            ),
            performance_tasks_completed=sum(
                int(item.get("tasks_completed", 0)) for item in period_metrics
            ),
            completed_task_count=len(completed_tasks),
            overdue_task_count=len(overdue_tasks),
            early_warning_count=sum(
                item.get("alert_type") == "early_warning" for item in created_alerts
            ),
            overload_count=sum(item.get("alert_type") == "overload" for item in created_alerts),
            open_overload_count=sum(item.get("alert_type") == "overload" for item in open_alerts),
            resolved_alert_count=len(resolved_alerts),
            open_alert_count=len(open_alerts),
        )

    def _directive_evidence(
        self,
        alert_directives: List[dict[str, Any]],
        task_directives: List[dict[str, Any]],
        tasks: List[dict[str, Any]],
        alerts: List[dict[str, Any]],
        period_start: Date,
        period_end: Date,
        cutoff: datetime,
    ) -> DepartmentDirectiveEvidence:
        task_map = {item.get("_id"): item for item in tasks}
        alert_map = {item.get("_id"): item for item in alerts}
        candidates = [(item, "alert", "Chỉ thị cảnh báo") for item in alert_directives] + [
            (item, "task", "Chỉ thị công việc") for item in task_directives
        ]
        items: List[DepartmentDirectiveEvidenceItem] = []
        for document, source, label in candidates:
            if not self._directive_relevant(document, period_start, period_end, cutoff):
                continue
            status_at_cutoff = self._directive_status_at(document, cutoff)
            commitment = self._optional_date(document.get("commitment_date"))
            submitted = self._optional_datetime(document.get("submitted_at"))
            if submitted and submitted > cutoff:
                submitted = None
            timing_status, delay_hours = self._timing(commitment, submitted, cutoff)
            ids = (
                document.get("alert_ids", []) if source == "alert" else document.get("task_ids", [])
            )
            if source == "alert":
                completed = sum(
                    self._resolved_by(alert_map.get(item_id, {}), cutoff) for item_id in ids
                )
            else:
                completed = sum(
                    self._completed_by(task_map.get(item_id, {}), cutoff) for item_id in ids
                )
            progress = round(completed * 100 / len(ids)) if ids else 0
            items.append(
                DepartmentDirectiveEvidenceItem(
                    directive_id=str(document.get("_id")),
                    source=source,
                    source_label=label,
                    status=status_at_cutoff,
                    issued_at=self._as_datetime(document.get("issued_at")),
                    commitment_date=commitment,
                    submitted_at=submitted,
                    accepted_at=self._cutoff_datetime(document.get("accepted_at"), cutoff),
                    progress_percent=progress,
                    timing_status=timing_status,
                    delay_hours=delay_hours,
                )
            )
        items.sort(key=lambda item: item.issued_at, reverse=True)
        status_counts = {
            value: sum(item.status == value for item in items)
            for value in ("pending", "acknowledged", "submitted", "accepted", "needs_revision")
        }
        with_commitment = [
            item for item in items if item.timing_status != DirectiveTimingStatus.NO_COMMITMENT
        ]
        measured = [
            item
            for item in with_commitment
            if item.timing_status
            in {
                DirectiveTimingStatus.ON_TIME,
                DirectiveTimingStatus.LATE,
                DirectiveTimingStatus.OVERDUE,
            }
        ]
        delayed = [item.delay_hours for item in measured if item.delay_hours > 0]
        total = len(items)
        accepted = status_counts["accepted"]
        on_time = sum(item.timing_status == DirectiveTimingStatus.ON_TIME for item in measured)
        return DepartmentDirectiveEvidence(
            total_count=total,
            pending_count=status_counts["pending"],
            acknowledged_count=status_counts["acknowledged"],
            submitted_count=status_counts["submitted"],
            accepted_count=accepted,
            needs_revision_count=status_counts["needs_revision"],
            completed_count=accepted,
            completion_rate=round(accepted * 100 / total, 1) if total else None,
            with_commitment_count=len(with_commitment),
            on_time_count=on_time,
            late_count=sum(item.timing_status == DirectiveTimingStatus.LATE for item in measured),
            overdue_count=sum(
                item.timing_status == DirectiveTimingStatus.OVERDUE for item in measured
            ),
            no_commitment_count=sum(
                item.timing_status == DirectiveTimingStatus.NO_COMMITMENT for item in items
            ),
            on_time_rate=round(on_time * 100 / len(measured), 1) if measured else None,
            average_delay_hours=(round(sum(delayed) / len(delayed), 1) if delayed else None),
            maximum_delay_hours=round(max(delayed), 1) if delayed else None,
            items=items,
        )

    def _directive_relevant(
        self, document: dict, period_start: Date, period_end: Date, cutoff: datetime
    ) -> bool:
        dates = [
            document.get("issued_at"),
            document.get("acknowledged_at"),
            document.get("submitted_at"),
            document.get("accepted_at"),
            document.get("revision_requested_at"),
        ]
        if any(self._date_in_period(value, period_start, period_end, cutoff) for value in dates):
            return True
        commitment = self._optional_date(document.get("commitment_date"))
        if commitment and period_start <= commitment <= period_end:
            return True
        issued = self._optional_datetime(document.get("issued_at"))
        return bool(
            issued
            and issued <= cutoff
            and self._directive_status_at(document, cutoff)
            in {"pending", "acknowledged", "submitted", "needs_revision"}
        )

    def _directive_status_at(self, document: dict, cutoff: datetime) -> str:
        accepted = self._cutoff_datetime(document.get("accepted_at"), cutoff)
        submitted = self._cutoff_datetime(document.get("submitted_at"), cutoff)
        revision = self._cutoff_datetime(document.get("revision_requested_at"), cutoff)
        acknowledged = self._cutoff_datetime(document.get("acknowledged_at"), cutoff)
        if accepted:
            return "accepted"
        if submitted and (not revision or submitted >= revision):
            return "submitted"
        if revision:
            return "needs_revision"
        if acknowledged:
            return "acknowledged"
        return "pending"

    def _timing(
        self, commitment: Date | None, submitted: datetime | None, cutoff: datetime
    ) -> tuple[DirectiveTimingStatus, float]:
        if commitment is None:
            return DirectiveTimingStatus.NO_COMMITMENT, 0
        deadline = datetime.combine(commitment, time.max, tzinfo=self.business_timezone).astimezone(
            timezone.utc
        )
        if submitted:
            if submitted <= deadline:
                return DirectiveTimingStatus.ON_TIME, 0
            return DirectiveTimingStatus.LATE, self._hours(submitted - deadline)
        if cutoff > deadline:
            return DirectiveTimingStatus.OVERDUE, self._hours(cutoff - deadline)
        return DirectiveTimingStatus.NOT_DUE, 0

    async def _upload_files(
        self, department_id: ObjectId, week_start: Date, uploads: List[EvaluationUpload]
    ) -> List[DepartmentEvaluationAttachment]:
        if not uploads:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Vui lòng đính kèm ít nhất một tài liệu định hướng tuần mới",
            )
        if len(uploads) > self.settings.storage_max_files_per_evaluation:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Chỉ được đính kèm tối đa {self.settings.storage_max_files_per_evaluation} tệp",
            )
        attachments: List[DepartmentEvaluationAttachment] = []
        try:
            for upload in uploads:
                file_name = Path(upload.file_name).name
                suffix = Path(file_name).suffix.lower()
                if suffix not in self._ALLOWED_EXTENSIONS:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                        detail=f"Tệp {file_name} không thuộc định dạng được hỗ trợ",
                    )
                if upload.content_type not in self._CONTENT_TYPES_BY_EXTENSION.get(suffix, set()):
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                        detail=f"Loại nội dung của tệp {file_name} không được hỗ trợ",
                    )
                size = len(upload.content)
                if size <= 0 or size > self.settings.storage_max_file_size:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                        detail=f"Kích thước tệp {file_name} không hợp lệ",
                    )
                checksum = hashlib.sha256(upload.content).hexdigest()
                attachment_id = str(uuid4())
                storage_key = (
                    f"department-evaluations/{department_id}/{week_start.isoformat()}/"
                    f"{attachment_id}{suffix}"
                )
                await self.storage.upload_bytes(
                    storage_key, upload.content, upload.content_type, checksum
                )
                attachments.append(
                    DepartmentEvaluationAttachment(
                        attachment_id=attachment_id,
                        storage_key=storage_key,
                        file_name=file_name,
                        content_type=upload.content_type,
                        file_size=size,
                        checksum=checksum,
                    )
                )
                scan_result: ScanResult = await self.scanner.scan(upload.content)
                if not scan_result.clean:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                        detail=f"Tệp {file_name} không vượt qua kiểm tra an toàn",
                    )
        except HTTPException:
            await self._delete_files(attachments)
            raise
        except Exception as exc:
            await self._delete_files(attachments)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Không thể lưu tài liệu định hướng, vui lòng kiểm tra kho lưu trữ",
            ) from exc
        return attachments

    async def _delete_files(self, attachments) -> None:
        for attachment in attachments:
            try:
                await self.storage.delete(attachment.storage_key)
            except Exception:
                continue

    async def _response(
        self, document: DepartmentWeeklyEvaluationDocument
    ) -> DepartmentWeeklyEvaluationResponse:
        attachments = [
            DepartmentEvaluationAttachmentMetadata(
                attachment_id=item.attachment_id,
                file_name=item.file_name,
                content_type=item.content_type,
                file_size=item.file_size,
            )
            for item in document.attachments
        ]
        return DepartmentWeeklyEvaluationResponse(
            id=str(document.id),
            department_id=str(document.department_id),
            department_name=document.department_name,
            department_code=document.department_code,
            manager_id=str(document.manager_id) if document.manager_id else None,
            manager_name=document.manager_name,
            week_start=document.week_start,
            week_end=document.week_end,
            evidence_cutoff_at=document.evidence_cutoff_at,
            directive_execution_score=document.directive_execution_score,
            stability_score=document.stability_score,
            timeliness_score=document.timeliness_score,
            overall_score=document.overall_score,
            assessment_note=document.assessment_note,
            evidence_snapshot=document.evidence_snapshot,
            attachments=attachments,
            evaluated_by=str(document.evaluated_by),
            evaluated_at=document.evaluated_at,
            evaluation_delay_days=document.evaluation_delay_days,
            created_at=document.created_at,
            updated_at=document.updated_at,
        )

    @staticmethod
    def _list_item(
        document: DepartmentWeeklyEvaluationDocument,
    ) -> DepartmentWeeklyEvaluationListItemResponse:
        attachments = [
            DepartmentEvaluationAttachmentMetadata(
                attachment_id=item.attachment_id,
                file_name=item.file_name,
                content_type=item.content_type,
                file_size=item.file_size,
            )
            for item in document.attachments
        ]
        return DepartmentWeeklyEvaluationListItemResponse(
            id=str(document.id),
            department_id=str(document.department_id),
            department_name=document.department_name,
            department_code=document.department_code,
            week_start=document.week_start,
            week_end=document.week_end,
            directive_execution_score=document.directive_execution_score,
            stability_score=document.stability_score,
            timeliness_score=document.timeliness_score,
            overall_score=document.overall_score,
            assessment_note=document.assessment_note,
            attachment_count=len(attachments),
            attachments=attachments,
            evaluated_at=document.evaluated_at,
            evaluation_delay_days=document.evaluation_delay_days,
        )

    @staticmethod
    def _ensure_scope(department_id: ObjectId, scope: ObjectId | None) -> None:
        if scope is not None and department_id != scope:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bạn không có quyền xem dữ liệu của phòng ban khác",
            )

    @staticmethod
    def _overall_score(payload) -> float:
        return round(
            payload.directive_execution_score * 0.4
            + payload.stability_score * 0.4
            + payload.timeliness_score * 0.2,
            1,
        )

    @staticmethod
    def _average(values: List[float]) -> float | None:
        return round(sum(values) / len(values), 2) if values else None

    @staticmethod
    def _float_delta(current: float | None, previous: float | None) -> float | None:
        if current is None or previous is None:
            return None
        return round(current - previous, 2)

    @staticmethod
    def _stability_status(current, previous, deltas) -> StabilityStatus:
        if (
            current.average_performance_score is None
            or previous.average_performance_score is None
            or current.average_quality_score is None
            or previous.average_quality_score is None
        ):
            return StabilityStatus.INSUFFICIENT_DATA
        needs_attention = (
            (deltas.performance_score or 0) < -5
            or (deltas.quality_score or 0) < -5
            or deltas.overdue_tasks > 0
            or deltas.open_overload_alerts > 0
        )
        if needs_attention:
            return StabilityStatus.NEEDS_ATTENTION
        improving = (
            (deltas.performance_score or 0) > 0
            or (deltas.quality_score or 0) > 0
            or deltas.performance_tasks_completed > 0
            or deltas.completed_tasks > 0
            or deltas.overdue_tasks < 0
            or deltas.open_overload_alerts < 0
            or deltas.open_alerts < 0
        )
        return StabilityStatus.IMPROVING if improving else StabilityStatus.STABLE

    def _exists_at(self, document: dict, cutoff: datetime) -> bool:
        created = self._optional_datetime(document.get("created_at"))
        return created is None or created <= cutoff

    def _completed_by(self, document: dict, cutoff: datetime) -> bool:
        completed = self._optional_datetime(document.get("completed_at"))
        return bool(completed and completed <= cutoff)

    def _resolved_by(self, document: dict, cutoff: datetime) -> bool:
        resolved = self._optional_datetime(document.get("resolved_at"))
        return bool(resolved and resolved <= cutoff)

    def _date_in_period(
        self, value, period_start: Date, period_end: Date, cutoff: datetime
    ) -> bool:
        date_time = self._optional_datetime(value)
        if date_time is None or date_time > cutoff:
            return False
        local_date = date_time.astimezone(self.business_timezone).date()
        return period_start <= local_date <= period_end

    def _as_date(self, value) -> Date:
        result = self._optional_date(value)
        return result or Date.max

    def _optional_date(self, value) -> Date | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            return self._as_datetime(value).astimezone(self.business_timezone).date()
        return value

    def _cutoff_datetime(self, value, cutoff: datetime) -> datetime | None:
        result = self._optional_datetime(value)
        return result if result and result <= cutoff else None

    @staticmethod
    def _optional_datetime(value) -> datetime | None:
        if value is None:
            return None
        return DepartmentEvaluationService._as_datetime(value)

    @staticmethod
    def _as_datetime(value) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def _now(self) -> datetime:
        return self._clock.now()

    @staticmethod
    def _hours(value: timedelta) -> float:
        return round(max(0, value.total_seconds()) / 3600, 1)

    @staticmethod
    def _clean_note(value: str | None) -> str | None:
        return value.strip() if value and value.strip() else None


__all__ = ["DepartmentEvaluationService", "EvaluationUpload"]
