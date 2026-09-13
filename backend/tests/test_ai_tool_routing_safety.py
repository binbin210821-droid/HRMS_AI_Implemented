from datetime import date
from types import SimpleNamespace

import pytest

from app.ai.tooling import AiToolDefinition, AiToolRegistry, ToolCall
from app.core.time import business_clock
from app.models.ai_tools import PerformanceTrendToolInput
from app.models.user import CurrentUser, UserRole
from app.services.ai_chat_orchestrator import (
    LEADERSHIP_DETAIL_POLICY_MESSAGE,
    NO_MATCHING_DATA_MESSAGE,
    AiChatOrchestrator,
)
from app.services.ai_tool_service import (
    CONTEXT_REVALIDATION_MESSAGE,
    AiToolService,
    _context_period_is_invalid,
    _extract_department_name,
    _infer_read_tool_call,
    _normalize_tool_call,
    _relative_date_arguments,
    _requests_restricted_employee_detail,
)


@pytest.fixture
def fixed_business_date(monkeypatch):
    monkeypatch.setattr(business_clock, "today", lambda: date(2026, 9, 10))


def test_model_stale_dates_are_replaced_by_user_period(fixed_business_date) -> None:
    call = ToolCall(
        "get_performance_trend",
        {"date_from": "2025-05-15", "date_to": "2025-05-22", "limit": 7},
    )

    normalized = _normalize_tool_call(
        call, "Hiệu suất phòng tôi 7 ngày gần đây thế nào?"
    )

    assert normalized.arguments["date_from"] == "2026-09-04"
    assert normalized.arguments["date_to"] == "2026-09-10"
    assert normalized.arguments["limit"] == 7


def test_missing_period_gets_bounded_recent_period(fixed_business_date) -> None:
    normalized = _normalize_tool_call(
        ToolCall("get_performance_trend", {"date_from": "2025-05-15"}),
        "Theo dõi hiệu suất phòng tôi gần đây.",
    )

    assert normalized.arguments["date_from"] == "2026-09-04"
    assert normalized.arguments["date_to"] == "2026-09-10"


def test_explicit_historical_period_is_preserved_and_bounded(fixed_business_date) -> None:
    normalized = _normalize_tool_call(
        ToolCall("get_performance_trend", {}),
        "Hiệu suất phòng tôi từ 01/08/2026 đến 07/08/2026.",
    )

    assert normalized.arguments["date_from"] == "2026-08-01"
    assert normalized.arguments["date_to"] == "2026-08-07"


def test_week_before_is_previous_calendar_week(fixed_business_date) -> None:
    arguments = _relative_date_arguments("hiệu suất tuần trước")

    assert arguments == {"date_from": "2026-08-31", "date_to": "2026-09-06"}


def test_comparison_route_does_not_accept_model_invented_department(fixed_business_date) -> None:
    call = _infer_read_tool_call("So với tuần trước điểm hiệu suất phòng tôi thay đổi thế nào?")
    assert call is not None

    normalized = _normalize_tool_call(
        ToolCall(
            call.name,
            {
                "date_from": "2025-05-15",
                "date_to": "2025-05-22",
                "department_name": "Phòng Nhân sự",
            },
        ),
        "So với tuần trước điểm hiệu suất phòng tôi thay đổi thế nào?",
    )

    assert normalized.arguments["date_from"] == "2026-09-07"
    assert normalized.arguments["date_to"] == "2026-09-10"
    assert "department_name" not in normalized.arguments


def test_explicit_department_name_is_kept(fixed_business_date) -> None:
    normalized = _normalize_tool_call(
        ToolCall(
            "get_department_performance",
            {"department_name": "Phòng Kinh doanh", "date_from": "2025-05-15"},
        ),
        "Điểm hiệu suất của Phòng Kinh doanh là bao nhiêu?",
    )

    assert normalized.arguments["department_name"] == "Phòng Kinh doanh"


def test_explicit_foreign_department_is_passed_to_scope_validation() -> None:
    call = _infer_read_tool_call("Điểm hiệu suất của Phòng Nhân sự là bao nhiêu?")

    assert call is not None
    assert call.arguments["department_name"] == "Phòng Nhân sự"
    assert _extract_department_name("Hiệu suất phòng tôi 7 ngày gần đây") is None


def test_leadership_employee_detail_is_not_routed_to_manager_tools() -> None:
    call = _infer_read_tool_call(
        "Cho tôi xem chi tiết từng nhân viên của công ty", UserRole.LEADERSHIP
    )

    assert _requests_restricted_employee_detail("Cho tôi xem chi tiết từng nhân viên của công ty")
    assert call is None or call.name not in {
        "get_employee_performance",
        "get_performance_trend",
        "get_overloaded_employees",
        "get_overdue_tasks",
    }


@pytest.mark.asyncio
async def test_leadership_employee_detail_returns_policy_message() -> None:
    class PolicyToolService:
        @staticmethod
        def deterministic_tool_name(_message, _role):
            return "get_company_performance_summary"

        async def read_data_from_message(self, *_args, **_kwargs):
            return "unavailable", None, None, LEADERSHIP_DETAIL_POLICY_MESSAGE

    user = CurrentUser(
        user_id="leadership-1",
        username="leadership",
        full_name="Lãnh đạo",
        role=UserRole.LEADERSHIP,
    )
    chunks = [
        chunk
        async for chunk in AiChatOrchestrator(
            GroundedChat(), PolicyToolService()
        ).stream_response(
            "Cho tôi xem chi tiết từng nhân viên của công ty",
            None,
            user,
        )
    ]

    assert chunks == [LEADERSHIP_DETAIL_POLICY_MESSAGE]


def test_follow_up_context_revalidates_future_period(fixed_business_date) -> None:
    normalized = _normalize_tool_call(
        ToolCall(
            "get_performance_trend",
            {"date_from": "2030-01-01", "date_to": "2030-01-07"},
        ),
        "",
        from_context=True,
    )

    assert normalized.arguments["date_from"] == "2026-09-04"
    assert normalized.arguments["date_to"] == "2026-09-10"
    assert _context_period_is_invalid(
        {"date_from": "2030-01-01", "date_to": "2030-01-07"}
    ) is True


def test_date_range_is_limited_to_ninety_days(fixed_business_date) -> None:
    normalized = _normalize_tool_call(
        ToolCall("get_performance_trend", {}),
        "Hiệu suất phòng tôi từ 01/01/2026 đến 10/09/2026.",
    )

    assert normalized.arguments["date_from"] == "2026-06-13"
    assert normalized.arguments["date_to"] == "2026-09-10"


def test_leadership_comparison_preserves_explicit_historical_period(fixed_business_date) -> None:
    call = _infer_read_tool_call(
        "So sánh hiệu suất các phòng ban từ 01/01/2020 đến 07/01/2020.",
        UserRole.LEADERSHIP,
    )

    assert call is not None and call.name == "compare_departments"
    normalized = _normalize_tool_call(call, "So sánh hiệu suất các phòng ban từ 01/01/2020 đến 07/01/2020.")

    assert normalized.arguments["date_from"] == "2020-01-01"
    assert normalized.arguments["date_to"] == "2020-01-07"


class RecoveryToolService:
    def __init__(self, *, with_data: bool) -> None:
        self.with_data = with_data
        self.calls: list[bool] = []

    @staticmethod
    def deterministic_tool_name(_message: str) -> str:
        return "get_performance_trend"

    async def read_data_from_message(self, *_args, force_deterministic=False, **_kwargs):
        self.calls.append(force_deterministic)
        if force_deterministic and self.with_data:
            return (
                "executed",
                "get_performance_trend",
                {"co_du_lieu": True, "du_lieu": [{"Ngày": "2026-09-10"}]},
                "Đã đọc dữ liệu.",
            )
        return (
            "executed",
            "get_department_performance",
            {"co_du_lieu": False, "du_lieu": []},
            "Chưa có dữ liệu.",
        )


class GroundedChat:
    async def stream_grounded_response(self, *_args, **_kwargs):
        yield "Đã đối chiếu dữ liệu."


@pytest.mark.asyncio
async def test_invalid_follow_up_context_asks_for_a_new_period(fixed_business_date) -> None:
    async def handler(_arguments, _context):
        return {"co_du_lieu": True, "du_lieu": [{"Ngày": "2026-09-10"}]}

    registry = AiToolRegistry()
    registry.register(
        AiToolDefinition(
            name="get_performance_trend",
            description="Đọc xu hướng hiệu suất.",
            input_model=PerformanceTrendToolInput,
            allowed_roles=frozenset({UserRole.MANAGER}),
            read_only=True,
            requires_human_approval=False,
            handler=handler,
        )
    )
    service = AiToolService(
        coordination_service=None,
        provider_factory=None,
        registry=registry,
    )
    user = CurrentUser(
        user_id="manager-1",
        username="manager",
        full_name="Quản lý",
        role=UserRole.MANAGER,
        department_id="department-1",
    )

    status, tool_name, data, message = await service.read_data_from_context(
        {
            "tool_name": "get_performance_trend",
            "arguments": {"date_from": "2030-01-01", "date_to": "2030-01-07"},
        },
        user,
        None,
    )

    assert (status, tool_name, data) == ("context_invalid", "get_performance_trend", None)
    assert message == CONTEXT_REVALIDATION_MESSAGE


@pytest.mark.asyncio
async def test_provider_invalid_tool_arguments_are_rejected_safely() -> None:
    async def handler(_arguments, _context):
        raise AssertionError("Tham số sai không được đi tới handler")

    registry = AiToolRegistry()
    registry.register(
        AiToolDefinition(
            name="get_performance_trend",
            description="Đọc xu hướng hiệu suất.",
            input_model=PerformanceTrendToolInput,
            allowed_roles=frozenset({UserRole.MANAGER}),
            read_only=True,
            requires_human_approval=False,
            handler=handler,
        )
    )

    class InvalidPlanner:
        async def generate_tool_call(self, _prompt, _tools):
            return ToolCall("get_performance_trend", {"limit": 0})

    service = AiToolService(
        coordination_service=SimpleNamespace(),
        provider_factory=InvalidPlanner(),
        registry=registry,
    )
    user = CurrentUser(
        user_id="manager-1",
        username="manager",
        full_name="Quản lý",
        role=UserRole.MANAGER,
        department_id="department-1",
    )

    status, tool_name, data, message = await service.read_data_from_message(
        "Tóm tắt dữ liệu vận hành giúp tôi.", user, None
    )

    assert status == "unavailable"
    assert tool_name == "get_performance_trend"
    assert data is None
    assert "không hợp lệ" in message


@pytest.mark.asyncio
async def test_routing_and_recovery_statuses_are_audited() -> None:
    async def empty_handler(_arguments, _context):
        return {"co_du_lieu": False, "du_lieu": []}

    class AuditFake:
        def __init__(self) -> None:
            self.statuses: list[str] = []

        async def record(self, **kwargs) -> None:
            self.statuses.append(kwargs["status"])

    registry = AiToolRegistry()
    registry.register(
        AiToolDefinition(
            name="get_performance_trend",
            description="Đọc xu hướng hiệu suất.",
            input_model=PerformanceTrendToolInput,
            allowed_roles=frozenset({UserRole.MANAGER}),
            read_only=True,
            requires_human_approval=False,
            handler=empty_handler,
        )
    )
    audit = AuditFake()
    service = AiToolService(
        coordination_service=SimpleNamespace(),
        provider_factory=SimpleNamespace(),
        registry=registry,
        audit_logger=audit,
    )
    user = CurrentUser(
        user_id="manager-1",
        username="manager",
        full_name="Quản lý",
        role=UserRole.MANAGER,
        department_id="department-1",
    )
    message = "Hiệu suất phòng tôi 7 ngày gần đây thế nào?"

    await service.read_data_from_message(message, user, None)
    await service.read_data_from_message(message, user, None, force_deterministic=True)

    assert "deterministic_route" in audit.statuses
    assert "no_data" in audit.statuses
    assert "deterministic_recovery" in audit.statuses
    assert "no_data_after_recovery" in audit.statuses


@pytest.mark.asyncio
async def test_wrong_planner_tool_is_recovered_by_deterministic_route() -> None:
    tool_service = RecoveryToolService(with_data=True)
    orchestrator = AiChatOrchestrator(GroundedChat(), tool_service)
    user = CurrentUser(
        user_id="manager-1",
        username="manager",
        full_name="Quản lý",
        role=UserRole.MANAGER,
        department_id="department-1",
    )

    chunks = [
        chunk
        async for chunk in orchestrator.stream_response(
            "Hiệu suất phòng tôi 7 ngày gần đây thế nào?", None, user
        )
    ]

    assert chunks == ["Đã đối chiếu dữ liệu."]
    assert tool_service.calls == [False, True]


@pytest.mark.asyncio
async def test_no_data_recovery_stays_safe_and_does_not_generate_claims() -> None:
    tool_service = RecoveryToolService(with_data=False)
    orchestrator = AiChatOrchestrator(GroundedChat(), tool_service)
    user = CurrentUser(
        user_id="manager-1",
        username="manager",
        full_name="Quản lý",
        role=UserRole.MANAGER,
        department_id="department-1",
    )

    chunks = [
        chunk
        async for chunk in orchestrator.stream_response(
            "Hiệu suất phòng tôi 7 ngày gần đây thế nào?", None, user
        )
    ]

    assert chunks == [NO_MATCHING_DATA_MESSAGE]
    assert tool_service.calls == [False, True]
