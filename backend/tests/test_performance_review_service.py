from datetime import date, datetime, timezone
from types import SimpleNamespace

import pytest
from bson import ObjectId
from fastapi import HTTPException

from app.models.task import TaskDocument, TaskPriority, TaskStatus
from app.models.task_execution import (
    DailyPerformanceReviewCreate,
    DailyPerformanceReviewItem,
    EvidenceStatus,
)
from app.services.performance_review_service import PerformanceReviewService
from tests.time_fixtures import FixedBusinessClock


def make_task(employee_id: ObjectId, department_id: ObjectId, task_id: ObjectId | None = None):
    now = datetime(2026, 9, 7, 12, tzinfo=timezone.utc)
    return TaskDocument(
        _id=task_id or ObjectId(),
        title="Công việc kiểm thử",
        employee_id=employee_id,
        department_id=department_id,
        priority=TaskPriority.MEDIUM,
        status=TaskStatus.DONE,
        due_date=date(2026, 9, 7),
        completed_at=now,
        created_by=ObjectId(),
        created_at=now,
        updated_at=now,
    )


class FakeTaskRepository:
    def __init__(self, employee_id: ObjectId, department_id: ObjectId, tasks: list[TaskDocument]):
        self.employee = SimpleNamespace(
            id=employee_id,
            department_id=department_id,
            full_name="Nhân viên kiểm thử",
            employee_code="TEST-001",
        )
        self.tasks = tasks
        self.audit_documents: list[dict] = []
        self.audit_calls = 0

    async def find_employee(self, _employee_id, _scope):
        return self.employee

    async def find_tasks_for_review(self, _employee_id, _review_date):
        return list(self.tasks)

    async def find_tasks_by_ids(self, _task_ids):
        return []

    async def insert_audit_logs(self, documents, session=None):
        self.audit_calls += 1
        self.audit_documents.extend(documents)
        self.session = session


class FakeReportRepository:
    def __init__(self, reports=None, fail=False):
        self.reports = {report.task_id: report for report in (reports or [])}
        self.fail = fail
        self.bulk_calls = 0
        self.entries = []

    async def ensure_indexes(self):
        return None

    async def list_for_employee_date(self, _employee_id, _review_date):
        return list(self.reports.values())

    async def bulk_update_manager_reviews(self, entries, session=None):
        self.bulk_calls += 1
        self.entries = entries
        self.session = session
        if self.fail:
            raise RuntimeError("partial bulk failure")
        return {entry["placeholder"]["task_id"]: SimpleNamespace() for entry in entries}


class FakePerformanceRepository:
    def __init__(self):
        self.metric_calls = 0
        self.client = None

    async def ensure_indexes(self):
        return None

    async def find_by_employee_date(self, _employee_id, _review_date):
        return None

    async def upsert_daily_review(self, *_args, session=None):
        self.metric_calls += 1
        self.session = session
        return SimpleNamespace(id=ObjectId())


class FakeTransaction:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False


class FakeSession:
    def __init__(self):
        self.transaction = FakeTransaction()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False

    def start_transaction(self):
        return self.transaction


class FakeMongoClient:
    def __init__(self):
        self.session = FakeSession()

    async def start_session(self):
        return self.session


def make_service(tasks, reports=None, report_failure=False):
    employee_id = tasks[0].employee_id
    department_id = tasks[0].department_id
    task_repository = FakeTaskRepository(employee_id, department_id, tasks)
    report_repository = FakeReportRepository(reports, fail=report_failure)
    performance_repository = FakePerformanceRepository()
    service = PerformanceReviewService(
        task_repository,
        report_repository,
        performance_repository,
        SimpleNamespace(),
        clock=FixedBusinessClock(datetime(2026, 9, 7, 12, tzinfo=timezone.utc)),
    )
    return service, task_repository, report_repository, performance_repository


@pytest.mark.asyncio
async def test_get_review_serializes_attachment_response_model():
    employee_id = ObjectId()
    department_id = ObjectId()
    task = make_task(employee_id, department_id)
    report = SimpleNamespace(
        task_id=task.id,
        attachments=[
            SimpleNamespace(
                attachment_id=None,
                checksum="a" * 64,
                storage_key="evidence/test.txt",
                file_name="test.txt",
                content_type="text/plain",
                file_size=4,
            )
        ],
        manager_review=SimpleNamespace(
            score=90,
            note=None,
            change_reason=None,
            evidence_status=EvidenceStatus.VERIFIED,
            missing_reason=None,
        ),
        result_summary="Kết quả kiểm thử",
        progress_percent=100,
        outcome_status="completed",
    )
    service, _task_repository, _report_repository, _performance_repository = make_service(
        [task], reports=[report]
    )

    result = await service.get_review(str(employee_id), date(2026, 9, 7), department_id)

    assert result.tasks[0].attachments[0].attachment_id == "a" * 64
    assert result.tasks[0].attachments[0].file_name == "test.txt"


def request_for(tasks, reason="Không có minh chứng"):
    return DailyPerformanceReviewCreate(
        employee_id=str(tasks[0].employee_id),
        date=date(2026, 9, 7),
        items=[
            DailyPerformanceReviewItem(task_id=str(task.id), score=88, missing_reason=reason)
            for task in tasks
        ],
    )


@pytest.mark.asyncio
async def test_save_review_batches_new_report_reviews_and_audit_log():
    tasks = [make_task(ObjectId(), ObjectId())]
    service, task_repository, report_repository, performance_repository = make_service(tasks)

    async def response(*_args, **_kwargs):
        return "review-response"

    service.get_review = response
    result = await service.save_review(request_for(tasks), tasks[0].department_id, str(ObjectId()))

    assert result == "review-response"
    assert report_repository.bulk_calls == 1
    assert report_repository.entries[0]["report"] is None
    assert task_repository.audit_calls == 1
    assert [item["action"] for item in task_repository.audit_documents] == [
        "task_execution_review_updated",
        "daily_performance_review_saved",
    ]
    assert performance_repository.metric_calls == 1


@pytest.mark.asyncio
async def test_save_review_propagates_one_mongo_transaction_session_to_all_writes():
    tasks = [make_task(ObjectId(), ObjectId())]
    service, task_repository, report_repository, performance_repository = make_service(tasks)
    performance_repository.client = FakeMongoClient()

    async def response(*_args, **_kwargs):
        return "review-response"

    service.get_review = response
    result = await service.save_review(request_for(tasks), tasks[0].department_id, str(ObjectId()))

    assert result == "review-response"
    session = performance_repository.client.session
    assert report_repository.session is session
    assert performance_repository.session is session
    assert task_repository.session is session


@pytest.mark.asyncio
async def test_save_review_updates_existing_report_and_requires_missing_reason():
    task = make_task(ObjectId(), ObjectId())
    service, task_repository, report_repository, _performance_repository = make_service([task])
    request = request_for([task], reason=None)

    with pytest.raises(HTTPException) as error:
        await service.save_review(request, task.department_id, str(ObjectId()))
    assert error.value.status_code == 422
    assert "lý do thiếu minh chứng" in str(error.value.detail)
    assert report_repository.bulk_calls == 0
    assert task_repository.audit_documents == []


@pytest.mark.asyncio
async def test_save_review_uses_existing_report_and_records_review_audit():
    task = make_task(ObjectId(), ObjectId())
    existing = SimpleNamespace(task_id=task.id, manager_review=None, attachments=[])
    service, task_repository, report_repository, _performance_repository = make_service(
        [task], reports=[existing]
    )

    async def response(*_args, **_kwargs):
        return "review-response"

    service.get_review = response

    result = await service.save_review(request_for([task]), task.department_id, str(ObjectId()))

    assert result == "review-response"
    assert report_repository.entries[0]["report"] is existing
    assert report_repository.entries[0]["review"]["score"] == 88
    assert task_repository.audit_documents[0]["action"] == "task_execution_review_updated"


@pytest.mark.asyncio
async def test_update_review_requires_reason_when_task_score_changes():
    task = make_task(ObjectId(), ObjectId())
    existing_review = SimpleNamespace(score=80, change_reason=None)
    existing = SimpleNamespace(task_id=task.id, manager_review=existing_review, attachments=[])
    service, _task_repository, report_repository, _performance_repository = make_service(
        [task], reports=[existing]
    )
    request = DailyPerformanceReviewCreate(
        employee_id=str(task.employee_id),
        date=date(2026, 9, 7),
        items=[
            DailyPerformanceReviewItem(
                task_id=str(task.id),
                score=90,
                missing_reason="Đã xem kết quả trên hệ thống",
            )
        ],
    )

    with pytest.raises(HTTPException) as error:
        await service.update_review(request, task.department_id, str(ObjectId()))

    assert error.value.status_code == 422
    assert "lý do thay đổi điểm" in str(error.value.detail)
    assert report_repository.bulk_calls == 0


@pytest.mark.asyncio
async def test_update_review_stores_reason_for_changed_task_score():
    task = make_task(ObjectId(), ObjectId())
    existing_review = SimpleNamespace(score=80, change_reason=None)
    existing = SimpleNamespace(task_id=task.id, manager_review=existing_review, attachments=[])
    service, task_repository, report_repository, _performance_repository = make_service(
        [task], reports=[existing]
    )

    async def response(*_args, **_kwargs):
        return "review-response"

    service.get_review = response
    request = DailyPerformanceReviewCreate(
        employee_id=str(task.employee_id),
        date=date(2026, 9, 7),
        items=[
            DailyPerformanceReviewItem(
                task_id=str(task.id),
                score=90,
                missing_reason="Đã xem kết quả trên hệ thống",
                change_reason="Bổ sung kết quả nghiệm thu sau khi rà soát lại.",
            )
        ],
    )

    result = await service.update_review(request, task.department_id, str(ObjectId()))

    assert result == "review-response"
    assert report_repository.entries[0]["review"]["change_reason"] == (
        "Bổ sung kết quả nghiệm thu sau khi rà soát lại."
    )
    assert task_repository.audit_documents[0]["action"] == "task_score_changed"
    assert task_repository.audit_documents[0]["old_score"] == 80


@pytest.mark.asyncio
async def test_update_review_uses_operation_reason_as_task_and_summary_audit_reason():
    task = make_task(ObjectId(), ObjectId())
    existing_review = SimpleNamespace(score=80, change_reason=None)
    existing = SimpleNamespace(task_id=task.id, manager_review=existing_review, attachments=[])
    service, task_repository, report_repository, _performance_repository = make_service(
        [task], reports=[existing]
    )

    async def response(*_args, **_kwargs):
        return "review-response"

    service.get_review = response
    request = DailyPerformanceReviewCreate(
        employee_id=str(task.employee_id),
        date=date(2026, 9, 7),
        items=[
            DailyPerformanceReviewItem(
                task_id=str(task.id),
                score=90,
                missing_reason="Đã xem kết quả trên hệ thống",
            )
        ],
    )

    result = await service.update_review(
        request,
        task.department_id,
        str(ObjectId()),
        reason="Điều chỉnh sau khi rà soát toàn bộ kết quả",
    )

    assert result == "review-response"
    assert report_repository.entries[0]["review"]["change_reason"] == (
        "Điều chỉnh sau khi rà soát toàn bộ kết quả"
    )
    assert task_repository.audit_documents[0]["change_reason"] == (
        "Điều chỉnh sau khi rà soát toàn bộ kết quả"
    )
    assert task_repository.audit_documents[-1]["change_reason"] == (
        "Điều chỉnh sau khi rà soát toàn bộ kết quả"
    )


@pytest.mark.asyncio
async def test_save_review_stops_downstream_writes_when_batch_fails_midway():
    tasks = [make_task(ObjectId(), ObjectId())]
    service, task_repository, report_repository, performance_repository = make_service(
        tasks, report_failure=True
    )

    with pytest.raises(RuntimeError, match="partial bulk failure"):
        await service.save_review(request_for(tasks), tasks[0].department_id, str(ObjectId()))

    assert report_repository.bulk_calls == 1
    assert performance_repository.metric_calls == 0
    assert task_repository.audit_documents == []
