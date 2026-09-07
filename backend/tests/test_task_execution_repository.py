from datetime import date, datetime, timezone
from types import SimpleNamespace

import pytest
from bson import ObjectId

from app.models.task_execution import EvidenceStatus, TaskExecutionOutcome
from app.repositories.task_execution_repository import TaskExecutionRepository


class FakeCursor:
    def __init__(self, documents: list[dict]) -> None:
        self.documents = documents

    def sort(self, *_args):
        return self

    async def to_list(self, _length=None):
        return list(self.documents)


class FakeCollection:
    def __init__(self) -> None:
        self.documents: dict[ObjectId, dict] = {}
        self.indexes = []

    @staticmethod
    def matches(document: dict, query: dict) -> bool:
        for key, expected in query.items():
            actual = document.get(key)
            if isinstance(expected, dict) and "$in" in expected:
                if actual not in expected["$in"]:
                    return False
            elif actual != expected:
                return False
        return True

    async def create_index(self, keys, **kwargs):
        self.indexes.append((keys, kwargs))

    def find(self, query):
        return FakeCursor(
            [document for document in self.documents.values() if self.matches(document, query)]
        )

    async def find_one(self, query):
        return next(
            (document for document in self.documents.values() if self.matches(document, query)),
            None,
        )

    async def insert_one(self, document):
        self.documents[document["_id"]] = dict(document)

    async def update_one(self, query, update, upsert=False):
        document = await self.find_one(query)
        if document is None:
            if not upsert:
                return
            document = {key: value for key, value in query.items() if not isinstance(value, dict)}
            document.update(update.get("$setOnInsert", {}))
            document["_id"] = document.get("_id", ObjectId())
            self.documents[document["_id"]] = document
        document.update(update.get("$set", {}))
        return SimpleNamespace(modified_count=1)


class FakeDatabase:
    def __init__(self) -> None:
        self.collection = FakeCollection()

    def __getitem__(self, name: str):
        assert name == "task_execution_reports"
        return self.collection


def report_values(employee_id: ObjectId, task_id: ObjectId, report_id: ObjectId) -> dict:
    now = datetime(2026, 9, 7, tzinfo=timezone.utc)
    department_id = ObjectId()
    return {
        "_id": report_id,
        "task_id": task_id,
        "employee_id": employee_id,
        "department_id": department_id,
        "work_date": date(2026, 9, 7),
        "result_summary": "Đã hoàn thành",
        "progress_percent": 100,
        "outcome_status": TaskExecutionOutcome.COMPLETED.value,
        "attachments": [],
        "created_at": now,
        "updated_at": now,
    }


@pytest.mark.asyncio
async def test_task_execution_repository_crud_and_employee_date_query():
    database = FakeDatabase()
    repository = TaskExecutionRepository(database)
    employee_id = ObjectId()
    task_id = ObjectId()
    report_id = ObjectId()

    await repository.ensure_indexes()
    created = await repository.upsert_report(report_values(employee_id, task_id, report_id))
    assert created.id == report_id
    assert await repository.find_by_task_date(task_id, date(2026, 9, 7)) == created
    assert await repository.find_by_task_date(ObjectId(), date(2026, 9, 7)) is None

    reviewed = await repository.update_manager_review(
        report_id,
        {
            "score": 92,
            "note": "Tốt",
            "evidence_status": EvidenceStatus.MISSING_WITH_REASON.value,
            "missing_reason": "Không phát sinh tệp",
            "reviewed_by": ObjectId(),
            "reviewed_at": datetime(2026, 9, 7, tzinfo=timezone.utc),
        },
        datetime(2026, 9, 7, tzinfo=timezone.utc),
    )
    assert reviewed is not None
    assert reviewed.manager_review is not None
    assert reviewed.manager_review.score == 92
    assert [item.id for item in await repository.list_for_employee_date(employee_id, date(2026, 9, 7))] == [report_id]
    assert len(database.collection.indexes) == 4


@pytest.mark.asyncio
async def test_task_execution_repository_repairs_legacy_non_sparse_seed_index() -> None:
    class IndexCursor:
        async def to_list(self, _length=None):
            return [
                {"name": "_id_", "key": {"_id": 1}},
                {"name": "seed_key_1", "key": {"seed_key": 1}, "unique": True},
            ]

    class MigratingCollection:
        def __init__(self):
            self.dropped = []
            self.created = []

        def list_indexes(self):
            return IndexCursor()

        async def drop_index(self, name):
            self.dropped.append(name)

        async def create_index(self, keys, **kwargs):
            self.created.append((keys, kwargs))

    repository = TaskExecutionRepository.__new__(TaskExecutionRepository)
    repository.collection = MigratingCollection()

    await repository.ensure_indexes()

    assert repository.collection.dropped == ["seed_key_1"]
    assert repository.collection.created[0] == (
        "seed_key",
        {
            "unique": True,
            "partialFilterExpression": {"seed_key": {"$type": "string"}},
        },
    )
