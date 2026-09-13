from datetime import date, datetime, timezone

import pytest
from bson import ObjectId
from fastapi import HTTPException

from app.core.config import Settings
from app.models.department import DepartmentDocument
from app.models.department_evaluation import (
    DepartmentWeeklyEvaluationDocument,
    DepartmentWeeklyEvaluationPayload,
    DepartmentWeeklyEvaluationUpdatePayload,
)
from app.models.user import UserDocument, UserRole
from app.services.department_evaluation_service import (
    DepartmentEvaluationService,
    EvaluationUpload,
)
from tests.time_fixtures import FixedBusinessClock


class FakeStorage:
    def __init__(self) -> None:
        self.objects = {}
        self.signed_calls = []

    async def upload_bytes(self, storage_key, content, content_type, checksum):
        self.objects[storage_key] = (content, content_type, checksum)

    async def delete(self, storage_key):
        self.objects.pop(storage_key, None)

    async def signed_url(self, storage_key):
        self.signed_calls.append(storage_key)
        return f"https://storage.test/{storage_key}"


class FakeRepository:
    def __init__(self, department_id: ObjectId) -> None:
        now = datetime(2026, 9, 1, tzinfo=timezone.utc)
        self.department = DepartmentDocument(
            _id=department_id,
            name="Kinh doanh",
            code="KD",
            specialty="Kinh doanh",
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        self.manager = UserDocument(
            _id=ObjectId(),
            username="manager.kd",
            password_hash="hash",
            full_name="Quản lý Kinh doanh",
            role=UserRole.MANAGER,
            department_id=department_id,
            is_active=True,
            created_at=now,
        )
        self.evaluation = None
        self.audit_logs = []
        self.alert_directives = []
        self.task_directives = []
        self.tasks = []
        self.alerts = []

    async def ensure_indexes(self):
        return None

    async def find_department(self, _department_id):
        return self.department

    async def find_active_manager(self, _department_id):
        return self.manager

    async def list_performance_metrics(self, _department_id, start_date, _end_date):
        if start_date == date(2026, 8, 31):
            return [
                {
                    "date": datetime(2026, 9, 1, tzinfo=timezone.utc),
                    "performance_score": 88,
                    "quality_score": 90,
                    "tasks_completed": 4,
                },
                {
                    "date": datetime(2026, 9, 1, tzinfo=timezone.utc),
                    "performance_score": 84,
                    "quality_score": 86,
                    "tasks_completed": 3,
                },
                {
                    "date": datetime(2026, 9, 7, tzinfo=timezone.utc),
                    "performance_score": 100,
                    "quality_score": 100,
                    "tasks_completed": 99,
                },
            ]
        return [
            {
                "date": datetime(2026, 8, 25, tzinfo=timezone.utc),
                "performance_score": 80,
                "quality_score": 82,
                "tasks_completed": 3,
            }
        ]

    async def list_tasks(self, _department_id):
        return self.tasks

    async def list_alerts(self, _department_id):
        return self.alerts

    async def list_alert_directives(self, _department_id):
        return self.alert_directives

    async def list_task_directives(self, _department_id):
        return self.task_directives

    async def find_evaluation(self, _department_id, _week_start):
        return self.evaluation

    async def find_evaluation_by_id(self, evaluation_id):
        if self.evaluation and self.evaluation.id == evaluation_id:
            return self.evaluation
        return None

    async def list_evaluations(self, _department_id=None, _page=1, _page_size=12):
        items = [self.evaluation] if self.evaluation else []
        return items, len(items)

    async def insert(self, values):
        self.evaluation = DepartmentWeeklyEvaluationDocument.model_validate(values)
        return self.evaluation

    async def update(self, evaluation_id, values):
        if not self.evaluation or self.evaluation.id != evaluation_id:
            return None
        document = self.evaluation.model_dump(by_alias=True)
        document.update(values)
        self.evaluation = DepartmentWeeklyEvaluationDocument.model_validate(document)
        return self.evaluation

    async def insert_audit_log(self, values):
        self.audit_logs.append(values)


class FailingEvidenceRepository(FakeRepository):
    async def list_performance_metrics(self, _department_id, _start_date, _end_date):
        raise RuntimeError("Không thể đọc dữ liệu hiệu suất")


def settings() -> Settings:
    return Settings(
        _env_file=None,
        storage_bucket="test",
        storage_allowed_content_types={"application/pdf"},
    )


def payload(department_id: ObjectId) -> DepartmentWeeklyEvaluationPayload:
    return DepartmentWeeklyEvaluationPayload(
        department_id=str(department_id),
        week_start=date(2026, 8, 31),
        directive_execution_score=80,
        stability_score=90,
        timeliness_score=90,
        assessment_note="  Có cải thiện rõ rệt.  ",
    )


@pytest.mark.asyncio
async def test_create_weekly_evaluation_calculates_score_and_keeps_one_snapshot():
    department_id = ObjectId()
    repository = FakeRepository(department_id)
    storage = FakeStorage()
    service = DepartmentEvaluationService(
        repository,
        storage,
        settings(),
        clock=FixedBusinessClock(datetime(2026, 9, 5, 3, tzinfo=timezone.utc)),
    )

    result = await service.create(
        payload(department_id),
        [EvaluationUpload("dinh-huong.pdf", "application/pdf", b"%PDF-test")],
        str(ObjectId()),
    )

    assert result.overall_score == 86
    assert result.evaluation_delay_days == 1
    assert result.assessment_note == "Có cải thiện rõ rệt."
    assert result.evidence_snapshot.stability.current.performance_metric_days == 1
    assert result.evidence_snapshot.stability.current.performance_tasks_completed == 7
    assert result.evidence_snapshot.stability.current.average_performance_score == 86
    assert not hasattr(result.attachments[0], "signed_url")
    assert storage.signed_calls == []
    assert len(storage.objects) == 1

    download = await service.get_attachment_download_url(
        result.id,
        repository.evaluation.attachments[0].attachment_id,
        None,
    )
    assert download.url.startswith("https://storage.test/")
    assert len(storage.signed_calls) == 1
    assert repository.audit_logs[-1]["action"] == "department_weekly_evaluation_created"

    with pytest.raises(HTTPException) as duplicate:
        await service.create(
            payload(department_id),
            [EvaluationUpload("khac.pdf", "application/pdf", b"%PDF-other")],
            str(ObjectId()),
        )
    assert duplicate.value.status_code == 409
    assert len(storage.objects) == 1


@pytest.mark.asyncio
async def test_weekly_review_normalizes_any_date_to_monday():
    department_id = ObjectId()
    service = DepartmentEvaluationService(
        FakeRepository(department_id),
        FakeStorage(),
        settings(),
        clock=FixedBusinessClock(datetime(2026, 9, 12, 3, tzinfo=timezone.utc)),
    )

    review = await service.weekly_review(str(department_id), date(2026, 9, 12))

    assert review.week_start == date(2026, 9, 7)
    assert review.week_end == date(2026, 9, 11)


@pytest.mark.asyncio
async def test_weekly_evidence_uses_manager_submission_for_lateness_not_acceptance():
    department_id = ObjectId()
    repository = FakeRepository(department_id)
    alert_id = ObjectId()
    repository.alerts = [
        {
            "_id": alert_id,
            "department_id": department_id,
            "alert_type": "overload",
            "status": "resolved",
            "created_at": datetime(2026, 9, 1, 2, tzinfo=timezone.utc),
            "resolved_at": datetime(2026, 9, 4, 1, tzinfo=timezone.utc),
        }
    ]
    repository.alert_directives = [
        {
            "_id": ObjectId(),
            "target_department_id": department_id,
            "alert_ids": [alert_id],
            "status": "accepted",
            "issued_at": datetime(2026, 9, 1, 1, tzinfo=timezone.utc),
            "acknowledged_at": datetime(2026, 9, 1, 2, tzinfo=timezone.utc),
            "commitment_date": date(2026, 9, 3),
            "submitted_at": datetime(2026, 9, 4, 1, tzinfo=timezone.utc),
            "accepted_at": datetime(2026, 9, 5, 4, tzinfo=timezone.utc),
        }
    ]
    service = DepartmentEvaluationService(
        repository,
        FakeStorage(),
        settings(),
        clock=FixedBusinessClock(datetime(2026, 9, 5, 3, tzinfo=timezone.utc)),
    )

    review = await service.weekly_review(str(department_id), date(2026, 8, 31))
    item = review.evidence.directives.items[0]

    assert item.status == "submitted"
    assert item.timing_status == "late"
    assert item.delay_hours == 8
    assert item.accepted_at is None
    assert review.evidence.directives.late_count == 1


@pytest.mark.asyncio
async def test_weekly_evaluation_is_blocked_before_friday_cutoff():
    department_id = ObjectId()
    repository = FakeRepository(department_id)
    storage = FakeStorage()
    service = DepartmentEvaluationService(
        repository,
        storage,
        settings(),
        clock=FixedBusinessClock(datetime(2026, 9, 4, 9, 59, tzinfo=timezone.utc)),
    )

    with pytest.raises(HTTPException) as blocked:
        await service.create(
            payload(department_id),
            [EvaluationUpload("dinh-huong.pdf", "application/pdf", b"%PDF-test")],
            str(ObjectId()),
        )

    assert blocked.value.status_code == 409
    assert storage.objects == {}


@pytest.mark.asyncio
async def test_update_reuses_document_and_replaces_all_attachments():
    department_id = ObjectId()
    repository = FakeRepository(department_id)
    storage = FakeStorage()
    service = DepartmentEvaluationService(
        repository,
        storage,
        settings(),
        clock=FixedBusinessClock(datetime(2026, 9, 5, 3, tzinfo=timezone.utc)),
    )
    created = await service.create(
        payload(department_id),
        [EvaluationUpload("dinh-huong.pdf", "application/pdf", b"%PDF-old")],
        str(ObjectId()),
    )
    old_key = repository.evaluation.attachments[0].storage_key

    updated = await service.update(
        created.id,
        DepartmentWeeklyEvaluationUpdatePayload(
            directive_execution_score=90,
            stability_score=90,
            timeliness_score=100,
            assessment_note="Kế hoạch đã được cập nhật.",
        ),
        [EvaluationUpload("dinh-huong-moi.pdf", "application/pdf", b"%PDF-new")],
        str(ObjectId()),
    )

    assert updated.id == created.id
    assert updated.overall_score == 92
    assert old_key not in storage.objects
    assert len(storage.objects) == 1
    assert repository.audit_logs[-1]["action"] == "department_weekly_evaluation_updated"


@pytest.mark.asyncio
async def test_invalid_or_missing_attachment_is_rejected_without_evaluation():
    department_id = ObjectId()
    repository = FakeRepository(department_id)
    storage = FakeStorage()
    service = DepartmentEvaluationService(
        repository,
        storage,
        settings(),
        clock=FixedBusinessClock(datetime(2026, 9, 5, 3, tzinfo=timezone.utc)),
    )

    with pytest.raises(HTTPException) as missing:
        await service.create(payload(department_id), [], str(ObjectId()))
    assert missing.value.status_code == 422

    with pytest.raises(HTTPException) as invalid:
        await service.create(
            payload(department_id),
            [EvaluationUpload("script.exe", "application/octet-stream", b"invalid")],
            str(ObjectId()),
        )
    assert invalid.value.status_code == 422
    assert repository.evaluation is None
    assert storage.objects == {}


@pytest.mark.asyncio
async def test_uploaded_files_are_removed_when_evidence_snapshot_fails():
    department_id = ObjectId()
    repository = FailingEvidenceRepository(department_id)
    storage = FakeStorage()
    service = DepartmentEvaluationService(
        repository,
        storage,
        settings(),
        clock=FixedBusinessClock(datetime(2026, 9, 5, 3, tzinfo=timezone.utc)),
    )

    with pytest.raises(RuntimeError):
        await service.create(
            payload(department_id),
            [EvaluationUpload("dinh-huong.pdf", "application/pdf", b"%PDF-test")],
            str(ObjectId()),
        )

    assert repository.evaluation is None
    assert storage.objects == {}
