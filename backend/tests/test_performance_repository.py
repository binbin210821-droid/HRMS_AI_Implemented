from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from bson import ObjectId

from app.repositories.performance_repository import PerformanceRepository


@pytest.mark.asyncio
async def test_weekly_average_aggregates_quality_alongside_performance() -> None:
    captured = {}

    class Cursor:
        async def to_list(self, length):
            return [
                {
                    "weeks": [
                        {
                            "_id": date(2026, 9, 7),
                            "performance": 86.25,
                            "quality": 82.5,
                        }
                    ],
                    "overall": [{"average": 86.25}],
                }
            ]

    class Collection:
        def aggregate(self, pipeline):
            captured["pipeline"] = pipeline
            return Cursor()

    department_id = ObjectId()
    repository = PerformanceRepository.__new__(PerformanceRepository)
    repository.collection = Collection()
    repository.list_department_employees = AsyncMock(
        return_value=[SimpleNamespace(id=ObjectId())]
    )

    result = await repository.aggregate_weekly_average(
        department_id, date(2026, 9, 1), date(2026, 9, 9)
    )

    weeks_stage = captured["pipeline"][1]["$facet"]["weeks"][0]["$group"]
    assert weeks_stage["performance"] == {"$avg": "$performance_score"}
    assert weeks_stage["quality"] == {"$avg": "$quality_score"}
    assert result["weeks"][0]["quality"] == 82.5
