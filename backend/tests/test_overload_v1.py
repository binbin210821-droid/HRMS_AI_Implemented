from datetime import date, datetime, timezone
from unittest.mock import AsyncMock

import pytest
from bson import ObjectId

from app.api.v1.overload import list_overload_logs_v1
from app.core.pagination import DateRangeParams, ListQueryParams, Page
from app.models.overload import OverloadLogDocument, OverloadTriggerReason
from app.repositories.overload_repository import OverloadRepository
from app.services.overload_service import OverloadService


def _log() -> OverloadLogDocument:
    employee_id = ObjectId()
    return OverloadLogDocument(
        _id=ObjectId(),
        employee_id=employee_id,
        department_id=ObjectId(),
        date=date(2026, 9, 5),
        trigger_reason=[OverloadTriggerReason.TASK_VOLUME],
        tasks_completed=5,
        quality_score=80,
        created_at=datetime(2026, 9, 5, tzinfo=timezone.utc),
    )


def test_overload_response_exposes_department_and_trigger_reason() -> None:
    log = _log()
    response = OverloadService._response(log, [])

    assert response.department_id == str(log.department_id)
    assert response.trigger_reason == [OverloadTriggerReason.TASK_VOLUME]
    assert response.trigger_reason_labels == ["Khối lượng công việc cao"]


@pytest.mark.asyncio
async def test_overload_v1_passes_date_range_and_exposes_all_pages() -> None:
    service = AsyncMock()
    first_page = Page(items=[{"id": f"overload-{index}"} for index in range(100)], total=101)
    second_page = Page(items=[{"id": "overload-100"}], total=101)
    service.list_logs_page_v1.side_effect = [first_page, second_page]
    date_range = DateRangeParams(from_date=date(2026, 9, 1), to_date=date(2026, 9, 30))

    first = await list_overload_logs_v1(
        ListQueryParams(page=1, page_size=100, sort=None), date_range, None, None, service
    )
    second = await list_overload_logs_v1(
        ListQueryParams(page=2, page_size=100, sort=None), date_range, None, None, service
    )

    assert len(first.items) == 100
    assert first.total == 101
    assert first.has_next is True
    assert len(second.items) == 1
    assert second.has_next is False
    assert service.list_logs_page_v1.await_args_list[0].args[:3] == (
        None,
        date(2026, 9, 1),
        date(2026, 9, 30),
    )


@pytest.mark.asyncio
async def test_overload_repository_filters_mongo_query_by_date_before_pagination() -> None:
    captured = {}

    class Cursor:
        async def to_list(self, length):
            return [{"data": [_log() for _ in range(100)], "total": [{"count": 101}]}]

    class Collection:
        def aggregate(self, pipeline):
            captured["pipeline"] = pipeline
            return Cursor()

    repository = OverloadRepository.__new__(OverloadRepository)
    repository.logs = Collection()

    result = await repository.list_logs_page_v1(
        None,
        date(2026, 9, 1),
        date(2026, 9, 30),
        {"date": -1},
        1,
        100,
    )

    assert result.total == 101
    assert len(result.items) == 100
    assert captured["pipeline"][0]["$match"]["date"]["$gte"] == datetime(
        2026, 9, 1, tzinfo=timezone.utc
    )
    assert captured["pipeline"][0]["$match"]["date"]["$lt"] == datetime(
        2026, 10, 1, tzinfo=timezone.utc
    )
