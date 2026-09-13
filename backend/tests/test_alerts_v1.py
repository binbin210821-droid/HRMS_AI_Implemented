from datetime import date
from unittest.mock import AsyncMock

import pytest

from app.api.v1.alerts import list_alerts_v1
from app.core.pagination import DateRangeParams, ListQueryParams, Page


@pytest.mark.asyncio
async def test_alerts_v1_passes_date_range_and_exposes_all_pages() -> None:
    service = AsyncMock()
    first_page = Page(items=[{"id": f"alert-{index}"} for index in range(100)], total=101)
    second_page = Page(items=[{"id": "alert-100"}], total=101)
    service.list_alerts_page_v1.side_effect = [first_page, second_page]
    date_range = DateRangeParams(from_date=date(2026, 9, 1), to_date=date(2026, 9, 30))

    first = await list_alerts_v1(
        ListQueryParams(page=1, page_size=100, sort=None),
        date_range,
        None,
        "all",
        None,
        None,
        None,
        None,
        service,
    )
    second = await list_alerts_v1(
        ListQueryParams(page=2, page_size=100, sort=None),
        date_range,
        None,
        "all",
        None,
        None,
        None,
        None,
        service,
    )

    assert len(first.items) == 100
    assert first.total == 101
    assert first.has_next is True
    assert len(second.items) == 1
    assert second.has_next is False
    assert service.list_alerts_page_v1.await_args_list[0].args[:7] == (
        None,
        None,
        None,
        None,
        None,
        date(2026, 9, 1),
        date(2026, 9, 30),
    )
