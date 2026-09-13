from datetime import date
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from app.api.v1.performance import update_daily_review_v1
from app.main import app
from app.models.task_execution import (
    DailyPerformanceReviewItem,
    DailyPerformanceReviewUpdateV1,
)
from app.models.user import CurrentUser, UserRole


def _manager() -> CurrentUser:
    return CurrentUser(
        user_id="507f1f77bcf86cd799439011",
        username="demo.manager",
        full_name="Quản lý kiểm thử",
        role=UserRole.MANAGER,
        department_id="507f1f77bcf86cd799012",
    )


def _items() -> list[DailyPerformanceReviewItem]:
    return [
        DailyPerformanceReviewItem(
            task_id="507f1f77bcf86cd799439013",
            score=85,
            missing_reason="Không có minh chứng bổ sung",
        )
    ]


def test_v1_patch_reason_is_required_and_rejects_whitespace() -> None:
    with pytest.raises(ValidationError):
        DailyPerformanceReviewUpdateV1(items=_items(), reason="   ")


@pytest.mark.asyncio
async def test_v1_patch_maps_path_resource_and_operation_reason_to_existing_service() -> None:
    service = AsyncMock()
    service.update_review.return_value = "updated-review"
    request = DailyPerformanceReviewUpdateV1(items=_items(), reason="Điều chỉnh sau khi rà soát")

    result = await update_daily_review_v1(
        "507f1f77bcf86cd799439014",
        date(2026, 9, 8),
        request,
        "507f1f77bcf86cd799012",
        _manager(),
        service,
    )

    assert result == "updated-review"
    service.update_review.assert_awaited_once()
    service_request, scope, reviewed_by = service.update_review.await_args.args
    assert service_request.employee_id == "507f1f77bcf86cd799439014"
    assert service_request.date == date(2026, 9, 8)
    assert service_request.items == request.items
    assert scope == "507f1f77bcf86cd799012"
    assert reviewed_by == _manager().user_id
    assert service.update_review.await_args.kwargs == {"reason": "Điều chỉnh sau khi rà soát"}


def test_v1_phase7_paths_are_resource_shaped_and_legacy_api_remains() -> None:
    paths = app.openapi()["paths"]

    assert "/api/v1/performance/daily-reviews/{employee_id}/{date}" in paths
    assert "/api/v1/performance/daily-reviews" in paths
    assert "/api/v1/department-evaluations/weekly-reviews/{department_id}/{week_start}" in paths
    assert "/api/v1/department-evaluations/weekly-evaluations" in paths
    assert "/api/v1/department-evaluations/{evaluation_id}" in paths
    assert "/api/department-evaluations/weekly-review" in paths
    assert "/api/performance/daily-review" in paths
    assert "/api/v1/department-evaluations/weekly-review" not in paths

    for path, method in (
        ("/api/v1/performance/daily-reviews/{employee_id}/{date}", "get"),
        ("/api/v1/performance/daily-reviews", "post"),
        ("/api/v1/performance/daily-reviews/{employee_id}/{date}", "patch"),
        (
            "/api/v1/department-evaluations/weekly-reviews/{department_id}/{week_start}",
            "get",
        ),
        ("/api/v1/department-evaluations/weekly-evaluations", "post"),
        ("/api/v1/department-evaluations/{evaluation_id}", "patch"),
    ):
        assert "429" in paths[path][method]["responses"]
