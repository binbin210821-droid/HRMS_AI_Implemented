import asyncio
from collections.abc import AsyncIterator
from datetime import date, datetime, timezone

import pytest
from bson import ObjectId

from app.ai.base import JSON_OBJECT_MODE_MARKER
from app.ai.cache import AiProposalCache, AiSummaryCache
from app.ai.factory import SAFE_AI_FALLBACK_MESSAGE
from app.models.alert import AlertDocument, AlertSeverity, AlertStatus
from app.models.overload import WorkloadCandidateResponse
from app.models.task_planning import (
    OverdueTaskPlanningResponse,
    TaskActionOption,
    TaskActionType,
)
from app.services.ai_service import AiService


class EmptyPerformanceRepository:
    def __init__(self) -> None:
        self.scope = None

    async def find_many(self, scope: ObjectId | None):
        self.scope = scope
        return []


class EmptyAlertRepository:
    async def find_many(self, scope, status=None, alert_type=None):
        return []


class EmptyOverloadRepository:
    async def list_logs(self, scope):
        return []


class CapturingFactory:
    def __init__(self) -> None:
        self.prompt = ""

    async def generate_insight_stream(self, prompt: str) -> AsyncIterator[str]:
        self.prompt = prompt
        yield "tasks_com"
        yield "pleted và quality_score đang được theo dõi."


class ProviderFallbackFactory:
    async def generate_insight_stream(self, _prompt: str) -> AsyncIterator[str]:
        yield SAFE_AI_FALLBACK_MESSAGE


class SlowSummaryFactory:
    def __init__(self) -> None:
        self.calls = 0

    async def generate_insight_stream(self, _prompt: str) -> AsyncIterator[str]:
        self.calls += 1
        await asyncio.sleep(0.01)
        yield "Tóm tắt dùng chung cho các tab."


class ProposalFactory:
    def __init__(self, *chunks: str) -> None:
        self.prompt = ""
        self.chunks = chunks

    async def generate_insight_stream(self, prompt: str) -> AsyncIterator[str]:
        self.prompt = prompt
        for chunk in self.chunks:
            yield chunk


class SlowProposalFactory:
    async def generate_insight_stream(self, _prompt: str) -> AsyncIterator[str]:
        await asyncio.sleep(0.05)
        yield '{"actions": []}'


class CountingProposalFactory:
    def __init__(self, employee_id: str) -> None:
        self.employee_id = employee_id
        self.calls = 0

    async def generate_insight_stream(self, _prompt: str) -> AsyncIterator[str]:
        self.calls += 1
        yield (
            '{"alert_id":"ignored","summary":"Có thể điều phối.","actions":['
            f'{{"type":"apply_coordination","target_employee_id":"{self.employee_id}",'
            '"tasks_to_transfer":1,"note":null,"rationale":"Có sức chứa."}]}'
        )


def make_alert() -> AlertDocument:
    now = datetime.now(timezone.utc)
    return AlertDocument(
        _id=ObjectId(),
        alert_type="overload",
        severity=AlertSeverity.HIGH,
        status=AlertStatus.OPEN,
        employee_id=ObjectId(),
        department_id=ObjectId(),
        employee_code="KD-NV-001",
        employee_name="Nguyễn An",
        title="Cảnh báo quá tải",
        message="Khối lượng công việc tăng cao.",
        suggested_action="Phân bổ bớt công việc.",
        detected_dates=[date(2026, 9, 9)],
        fingerprint="ai-proposal-test",
        created_at=now,
        updated_at=now,
    )


def make_candidate(employee_id: ObjectId) -> WorkloadCandidateResponse:
    return WorkloadCandidateResponse(
        employee_id=str(employee_id),
        employee_code="KD-NV-002",
        employee_name="Trần Bình",
        tasks_completed=1,
        quality_score=92,
    )


def make_overdue_planning() -> OverdueTaskPlanningResponse:
    return OverdueTaskPlanningResponse(
        task_id="task-1",
        summary="Đã tính 1 phương án.",
        options=[
            TaskActionOption(
                option_id="opt-1",
                type=TaskActionType.KEEP_AND_EXTEND,
                target_employee_id="employee-1",
                target_employee_name="Nguyễn An",
                due_date=date(2026, 9, 15),
                fit_score=78,
                confidence=0.8,
                rationale="Lý do do backend tính.",
            )
        ],
        data_as_of=date(2026, 9, 10),
        plan_version="plan-1",
    )


@pytest.mark.asyncio
async def test_ai_service_only_explains_backend_ranked_overdue_task_options() -> None:
    factory = ProposalFactory(
        '{"summary":"Nên gia hạn sau khi rà soát tiến độ.",'
        '"explanations":[{"option_id":"opt-1",'
        '"rationale":"Công việc vẫn đang được thực hiện."}]}'
    )
    service = AiService(
        EmptyPerformanceRepository(),
        EmptyAlertRepository(),
        EmptyOverloadRepository(),
        factory,
    )

    result = await service.generate_overdue_task_action_proposal(
        make_overdue_planning(), ObjectId(), "manager-1"
    )

    assert result.task_id == "task-1"
    assert result.options[0].fit_score == 78
    assert result.options[0].rationale == "Công việc vẫn đang được thực hiện."
    assert "Điểm phù hợp do backend tính" in factory.prompt


@pytest.mark.asyncio
async def test_ai_service_ignores_explanation_for_unknown_option() -> None:
    factory = ProposalFactory(
        '{"summary":"Đề xuất.","explanations":['
        '{"option_id":"option-foreign","rationale":"Không khớp phương án."}]}'
    )
    service = AiService(
        EmptyPerformanceRepository(),
        EmptyAlertRepository(),
        EmptyOverloadRepository(),
        factory,
    )

    result = await service.generate_overdue_task_action_proposal(
        make_overdue_planning(), ObjectId(), "manager-1"
    )

    assert result.options[0].rationale == "Lý do do backend tính."
    assert result.summary == "Đề xuất."


@pytest.mark.asyncio
async def test_ai_service_passes_scoped_vietnamese_context_and_sanitizes_stream() -> None:
    performance = EmptyPerformanceRepository()
    factory = CapturingFactory()
    service = AiService(
        performance,
        EmptyAlertRepository(),
        EmptyOverloadRepository(),
        factory,
    )
    department_id = ObjectId()

    chunks = [chunk async for chunk in service.stream_response("Ai cần theo dõi?", department_id)]
    result = "".join(chunks)

    assert performance.scope == department_id
    assert "phòng ban của người dùng" in factory.prompt
    assert "tasks_completed" not in factory.prompt
    assert "tasks_completed" not in result
    assert "Số công việc hoàn thành" in result
    assert "Điểm chất lượng công việc" in result


@pytest.mark.asyncio
async def test_ai_service_summary_uses_compact_context_and_cache() -> None:
    factory = CapturingFactory()
    service = AiService(
        EmptyPerformanceRepository(),
        EmptyAlertRepository(),
        EmptyOverloadRepository(),
        factory,
        summary_cache=AiSummaryCache(ttl_seconds=60),
    )
    department_id = ObjectId()

    first = "".join(
        [
            chunk
            async for chunk in service.stream_response(
                "Tóm tắt hôm nay", department_id, "manager-id", mode="summary"
            )
        ]
    )
    second = "".join(
        [
            chunk
            async for chunk in service.stream_response(
                "Tóm tắt hôm nay", department_id, "manager-id", mode="summary"
            )
        ]
    )

    assert first == second
    assert factory.prompt.startswith("[[WORKMIND_AI_SUMMARY_MODE]]")
    assert "Dữ liệu hiệu suất" not in factory.prompt
    assert "performance_metrics" not in factory.prompt


@pytest.mark.asyncio
async def test_ai_context_reads_are_bounded_before_slicing() -> None:
    class BoundedPerformanceRepository:
        def __init__(self):
            self.limit = None

        async def find_many(self, _scope, *, limit=None):
            self.limit = limit
            return []

    class BoundedAlertRepository:
        def __init__(self):
            self.limit = None

        async def find_many(self, _scope, status=None, *, limit=None):
            self.limit = limit
            assert status == "open"
            return []

    class BoundedOverloadRepository:
        def __init__(self):
            self.limit = None

        async def list_logs(self, _scope, *, limit=None):
            self.limit = limit
            return []

    performance = BoundedPerformanceRepository()
    alerts = BoundedAlertRepository()
    overload = BoundedOverloadRepository()
    service = AiService(performance, alerts, overload, CapturingFactory())

    await service.build_scoped_context(ObjectId())

    assert performance.limit == 60
    assert alerts.limit == 30
    assert overload.limit == 30


@pytest.mark.asyncio
async def test_ai_service_summary_coalesces_concurrent_tabs() -> None:
    factory = SlowSummaryFactory()
    service = AiService(
        EmptyPerformanceRepository(),
        EmptyAlertRepository(),
        EmptyOverloadRepository(),
        factory,
        summary_cache=AiSummaryCache(ttl_seconds=60),
    )
    department_id = ObjectId()

    results = await asyncio.gather(
        *(
            service.stream_response(
                "Tóm tắt hôm nay", department_id, "manager-id", mode="summary"
            ).__anext__()
            for _ in range(3)
        )
    )

    assert results == ["Tóm tắt dùng chung cho các tab."] * 3
    assert factory.calls == 1


@pytest.mark.asyncio
async def test_grounded_response_uses_authorized_department_summary_when_provider_fails() -> None:
    service = AiService(
        EmptyPerformanceRepository(),
        EmptyAlertRepository(),
        EmptyOverloadRepository(),
        ProviderFallbackFactory(),
        provider_name="cloudflare",
        model="test-model",
    )
    tool_data = {
        "co_du_lieu": True,
        "cong_cu": "get_department_performance",
        "tong_quan": {
            "Phòng ban": "Phòng Kinh doanh",
            "Điểm hiệu suất trung bình": 84.25,
            "Điểm chất lượng trung bình": 87.5,
            "Số nhân viên có ghi nhận": 6,
            "Số ngày có ghi nhận": 32,
        },
        "du_lieu": [],
    }

    result = "".join(
        [
            chunk
            async for chunk in service.stream_grounded_response(
                "Điểm hiệu suất trung bình của phòng tôi là bao nhiêu?",
                ObjectId(),
                "manager-id",
                "get_department_performance",
                tool_data,
            )
        ]
    )

    assert "Đã đọc được dữ liệu" not in result
    assert "Điểm hiệu suất trung bình: 84.25" in result
    assert "Điểm chất lượng trung bình: 87.5" in result


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("tool_name", "tool_data", "expected"),
    [
        (
            "get_manager_evaluations",
            {
                "tong_quan": {"Số kỳ đánh giá": 1},
                "ky_du_lieu": {"tu_ngay": "2026-09-01", "den_ngay": "2026-09-10"},
                "du_lieu": [
                    {
                        "Quản lý": "Nguyễn An",
                        "Phòng ban": "Kinh doanh",
                        "Điểm đánh giá tổng thể": 88,
                        "Điểm hiệu suất trung bình phòng ban": 84,
                        "Điểm đúng hạn": 91,
                    }
                ],
            },
            "Nguyễn An",
        ),
        (
            "get_overdue_work_summary",
            {
                "tong_quan": {
                    "Số phòng ban có việc quá hạn": 1,
                    "Tổng số công việc quá hạn": 3,
                    "Tổng số công việc quá hạn chưa gửi chỉ thị": 2,
                },
                "du_lieu": [
                    {
                        "Phòng ban": "Kinh doanh",
                        "Số công việc quá hạn": 3,
                        "Số nhân viên liên quan": 2,
                        "Số ngày quá hạn lớn nhất": 4,
                    }
                ],
            },
            "Toàn công ty có 3 công việc quá hạn",
        ),
    ],
)
async def test_grounded_leadership_fallback_uses_authorized_aggregate_data(
    tool_name, tool_data, expected
) -> None:
    service = AiService(
        EmptyPerformanceRepository(),
        EmptyAlertRepository(),
        EmptyOverloadRepository(),
        ProviderFallbackFactory(),
    )

    result = "".join(
        [
            chunk
            async for chunk in service.stream_grounded_response(
                "Đánh giá dữ liệu gần đây", ObjectId(), "leadership-id", tool_name, tool_data
            )
        ]
    )

    assert "Đã đọc được dữ liệu trong phạm vi" not in result
    assert expected in result
    assert "Mã phòng ban" not in result


@pytest.mark.asyncio
async def test_alert_action_proposal_validates_and_filters_unknown_candidate() -> None:
    alert = make_alert()
    candidate = make_candidate(ObjectId())
    factory = ProposalFactory(
        "```json\n",
        '{"alert_id":"wrong-id","summary":"Nên xử lý ngay.","actions":['
        '{"type":"apply_coordination","target_employee_id":"unknown",'
        '"tasks_to_transfer":1,"note":"Chuyển việc nhẹ.","rationale":"Có sức chứa."},',
        '{"type":"apply_coordination","target_employee_id":"',
        candidate.employee_id,
        '","tasks_to_transfer":2,"note":null,"rationale":"Có thể nhận thêm."}',
        "]}\n```",
    )
    service = AiService(
        EmptyPerformanceRepository(),
        EmptyAlertRepository(),
        EmptyOverloadRepository(),
        factory,
    )

    result = await service.generate_alert_action_proposal(alert, alert.department_id, [candidate])

    assert result.alert_id == str(alert.id)
    assert len(result.actions) == 1
    assert result.actions[0].target_employee_id == candidate.employee_id
    assert "performance_metrics" not in factory.prompt
    assert "tasks_completed" not in factory.prompt
    assert factory.prompt.startswith(f"{JSON_OBJECT_MODE_MARKER}\n")


@pytest.mark.asyncio
async def test_alert_action_proposal_returns_safe_fallback_for_invalid_json() -> None:
    alert = make_alert()
    service = AiService(
        EmptyPerformanceRepository(),
        EmptyAlertRepository(),
        EmptyOverloadRepository(),
        ProposalFactory("Đây là câu trả lời thông thường, không phải JSON."),
    )

    result = await service.generate_alert_action_proposal(alert, alert.department_id, [])

    assert result.alert_id == str(alert.id)
    assert result.actions == []
    assert result.summary == "Chưa đủ dữ liệu để đề xuất phương án lúc này."


@pytest.mark.asyncio
async def test_alert_action_proposal_has_total_timeout_and_safe_fallback() -> None:
    alert = make_alert()
    service = AiService(
        EmptyPerformanceRepository(),
        EmptyAlertRepository(),
        EmptyOverloadRepository(),
        SlowProposalFactory(),
        total_timeout_seconds=0.01,
    )

    result = await service.generate_alert_action_proposal(alert, alert.department_id, [])

    assert result.actions == []
    assert result.summary == "Chưa đủ dữ liệu để đề xuất phương án lúc này."


@pytest.mark.asyncio
async def test_alert_action_proposal_rejects_tasks_above_existing_limit() -> None:
    alert = make_alert()
    candidate = make_candidate(ObjectId())
    factory = ProposalFactory(
        '{"alert_id":"',
        str(alert.id),
        '","summary":"Có thể điều phối.","actions":[',
        '{"type":"apply_coordination","target_employee_id":"',
        candidate.employee_id,
        '","tasks_to_transfer":3,"note":null,"rationale":"Có sức chứa."}]}',
    )
    service = AiService(
        EmptyPerformanceRepository(),
        EmptyAlertRepository(),
        EmptyOverloadRepository(),
        factory,
    )

    result = await service.generate_alert_action_proposal(alert, alert.department_id, [candidate])

    assert result.actions == []


@pytest.mark.asyncio
async def test_alert_action_proposal_uses_cache_for_same_alert_snapshot() -> None:
    alert = make_alert()
    candidate = make_candidate(ObjectId())
    factory = CountingProposalFactory(candidate.employee_id)
    service = AiService(
        EmptyPerformanceRepository(),
        EmptyAlertRepository(),
        EmptyOverloadRepository(),
        factory,
        proposal_cache=AiProposalCache(ttl_seconds=60),
    )

    first = await service.generate_alert_action_proposal(alert, alert.department_id, [candidate])
    second = await service.generate_alert_action_proposal(alert, alert.department_id, [candidate])

    assert first.actions and second.actions
    assert factory.calls == 1
    assert second.alert_id == str(alert.id)
