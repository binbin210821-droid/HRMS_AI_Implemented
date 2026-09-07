from datetime import datetime, timezone

import pytest
from bson import ObjectId

from app.models.threshold import (
    ThresholdConfigCreate,
    ThresholdConfigDocument,
    ThresholdConfigStatus,
)
from app.repositories.threshold_repository import ThresholdConfigRepository
from app.services.threshold_service import ThresholdConfigService


class FakeCollection:
    def __init__(self) -> None:
        self.index_calls: list[tuple[object, dict]] = []

    async def create_index(self, keys, **kwargs):
        self.index_calls.append((keys, kwargs))
        return kwargs.get("name", "index")


class FakeDatabase:
    def __init__(self) -> None:
        self.collection = FakeCollection()

    def __getitem__(self, name: str):
        assert name == "threshold_configs"
        return self.collection


class RecordingRepository:
    def __init__(self, document: ThresholdConfigDocument) -> None:
        self.document = document
        self.ensure_calls = 0

    async def ensure_indexes(self) -> None:
        self.ensure_calls += 1

    async def find_many(self, _department_id):
        return [self.document]

    async def insert(self, _document):
        return self.document

    async def find_by_id(self, _config_id):
        return self.document

    async def approve(self, _config_id, _approver_id, _updated_at):
        return self.document


def make_document() -> ThresholdConfigDocument:
    now = datetime(2026, 9, 6, tzinfo=timezone.utc)
    return ThresholdConfigDocument(
        _id=ObjectId(),
        department_id=ObjectId(),
        consecutive_days=3,
        quality_drop_percent=20,
        status=ThresholdConfigStatus.PROPOSED,
        proposed_by=ObjectId(),
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_repository_creates_threshold_lookup_indexes() -> None:
    database = FakeDatabase()
    await ThresholdConfigRepository(database).ensure_indexes()

    assert database.collection.index_calls == [
        (
            [("department_id", 1), ("status", 1), ("updated_at", -1)],
            {"name": "threshold_department_status_updated"},
        ),
        ([("created_at", -1)], {"name": "threshold_created_at"}),
    ]


@pytest.mark.asyncio
async def test_service_ensures_indexes_before_list_propose_and_approve() -> None:
    repository = RecordingRepository(make_document())
    service = ThresholdConfigService(repository)
    department_id = ObjectId()
    user_id = str(ObjectId())

    await service.list(department_id)
    assert repository.ensure_calls == 1

    await service.propose(
        request=ThresholdConfigCreate(),
        scope=department_id,
        proposed_by=user_id,
    )
    assert repository.ensure_calls == 2

    await service.approve(str(repository.document.id), user_id)
    assert repository.ensure_calls == 3
