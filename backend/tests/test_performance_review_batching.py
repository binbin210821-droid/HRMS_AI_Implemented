from datetime import date, datetime, timezone
from types import SimpleNamespace

import pytest
from bson import ObjectId

from app.models.task import TaskDocument, TaskPriority, TaskStatus
from app.models.task_execution import DailyPerformanceReviewCreate, DailyPerformanceReviewItem
from app.repositories.task_execution_repository import TaskExecutionRepository
from app.services.performance_review_service import PerformanceReviewService
from tests.time_fixtures import FixedBusinessClock


@pytest.mark.asyncio
async def test_save_review_batches_report_and_audit_writes_for_large_fixture() -> None:
    review_date = date(2026, 9, 1)
    now = datetime(2026, 9, 1, 12, tzinfo=timezone.utc)
    employee_id = ObjectId()
    department_id = ObjectId()
    tasks = [
        TaskDocument(
            _id=ObjectId(),
            title=f"Công việc {index}",
            employee_id=employee_id,
            department_id=department_id,
            priority=TaskPriority.MEDIUM,
            status=TaskStatus.DONE,
            due_date=review_date,
            completed_at=now,
            created_by=ObjectId(),
            created_at=now,
            updated_at=now,
        )
        for index in range(30)
    ]
    reviewed_reports = {task.id: SimpleNamespace(task_id=task.id) for task in tasks}

    class FakeTaskRepository:
        async def find_employee(self, _employee_id, _scope):
            return SimpleNamespace(id=employee_id, department_id=department_id)

        async def find_tasks_for_review(self, _employee_id, _review_date):
            return tasks

        async def find_tasks_by_ids(self, _task_ids):
            return []

        async def insert_audit_logs(self, documents):
            self.audit_calls = getattr(self, "audit_calls", 0) + 1
            self.audit_documents = documents

    class FakeReportRepository:
        async def ensure_indexes(self):
            return None

        async def list_for_employee_date(self, _employee_id, _review_date):
            return []

        async def bulk_update_manager_reviews(self, entries):
            self.bulk_calls = getattr(self, "bulk_calls", 0) + 1
            self.entries = entries
            return reviewed_reports

    class FakePerformanceRepository:
        async def ensure_indexes(self):
            return None

        async def find_by_employee_date(self, _employee_id, _review_date):
            return None

        async def upsert_daily_review(self, _employee_id, _review_date, values):
            self.values = values
            return SimpleNamespace(id=ObjectId())

    task_repository = FakeTaskRepository()
    report_repository = FakeReportRepository()
    performance_repository = FakePerformanceRepository()
    service = PerformanceReviewService(
        task_repository,
        report_repository,
        performance_repository,
        SimpleNamespace(),
        clock=FixedBusinessClock(now),
    )

    async def fake_get_review(*_args, **_kwargs):
        return "response-from-get-review"

    service.get_review = fake_get_review
    request = DailyPerformanceReviewCreate(
        employee_id=str(employee_id),
        date=review_date,
        items=[
            DailyPerformanceReviewItem(
                task_id=str(task.id), score=80, missing_reason="Không có minh chứng"
            )
            for task in tasks
        ],
    )

    response = await service.save_review(request, department_id, str(ObjectId()))

    assert response == "response-from-get-review"
    assert report_repository.bulk_calls == 1
    assert len(report_repository.entries) == 30
    assert task_repository.audit_calls == 1
    assert len(task_repository.audit_documents) == 31
    assert performance_repository.values["quality_score"] == 80.0


@pytest.mark.asyncio
async def test_bulk_manager_review_does_not_conflict_on_upsert_timestamps() -> None:
    now = datetime(2026, 9, 7, 12, tzinfo=timezone.utc)
    task_id = ObjectId()
    employee_id = ObjectId()
    department_id = ObjectId()
    report_id = ObjectId()

    class FakeCursor:
        async def to_list(self, _limit):
            return [
                {
                    "_id": report_id,
                    "task_id": task_id,
                    "employee_id": employee_id,
                    "department_id": department_id,
                    "work_date": datetime(2026, 9, 7, tzinfo=timezone.utc),
                    "attachments": [],
                    "progress_percent": 100,
                    "outcome_status": "completed",
                    "manager_review": {
                        "score": 88,
                        "evidence_status": "missing_with_reason",
                        "missing_reason": "Đã xem kết quả trên hệ thống",
                        "reviewed_by": employee_id,
                        "reviewed_at": now,
                    },
                    "created_at": now,
                    "updated_at": now,
                }
            ]

    class FakeCollection:
        async def bulk_write(self, operations, ordered):
            self.operations = operations
            self.ordered = ordered

        def find(self, _query):
            return FakeCursor()

    repository = TaskExecutionRepository.__new__(TaskExecutionRepository)
    repository.collection = FakeCollection()
    reviewed = await repository.bulk_update_manager_reviews(
        [
            {
                "report": None,
                "placeholder": {
                    "_id": report_id,
                    "task_id": task_id,
                    "employee_id": employee_id,
                    "department_id": department_id,
                    "work_date": datetime(2026, 9, 7, tzinfo=timezone.utc),
                    "attachments": [],
                    "progress_percent": 100,
                    "outcome_status": "completed",
                    "created_at": now,
                    "updated_at": now,
                },
                "review": {
                    "score": 88,
                    "evidence_status": "missing_with_reason",
                    "missing_reason": "Đã xem kết quả trên hệ thống",
                    "reviewed_by": employee_id,
                    "reviewed_at": now,
                },
                "updated_at": now,
            }
        ]
    )

    operation = repository.collection.operations[0]
    assert operation._doc["$set"]["updated_at"] == now
    assert "updated_at" not in operation._doc["$setOnInsert"]
    assert reviewed[task_id].manager_review is not None
