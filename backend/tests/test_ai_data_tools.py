from datetime import date
from types import SimpleNamespace

import pytest
from bson import ObjectId

from app.models.ai_tools import (
    ComparePerformancePeriodsToolInput,
    DepartmentPerformanceToolInput,
    EmployeePerformanceToolInput,
    ExplainAlertToolInput,
    PerformanceTrendToolInput,
)
from app.models.user import CurrentUser, UserRole
from app.services.ai_chat_orchestrator import (
    NO_OPEN_ALERTS_MESSAGE,
    SAFE_DATA_ACCESS_MESSAGE,
    AiChatOrchestrator,
)
from app.services.ai_data_tool_service import AiDataToolService
from app.services.ai_tool_service import _infer_read_tool_call, build_tool_registry


def _employee(employee_id: ObjectId, department_id: ObjectId, name: str) -> SimpleNamespace:
    return SimpleNamespace(id=employee_id, department_id=department_id, full_name=name)


class PerformanceRepoFake:
    def __init__(self, department_id: ObjectId, employee: SimpleNamespace) -> None:
        self.department_id = department_id
        self.employee = employee
        self.department = SimpleNamespace(id=department_id, name="Phòng Kinh doanh")

    async def find_department(self, department_id):
        return self.department if department_id == self.department_id else None

    async def list_departments(self):
        return [self.department]

    async def list_department_employees(self, department_id):
        return [self.employee] if department_id == self.department_id else []

    async def list_employees(self, department_id=None):
        return [self.employee] if department_id in (None, self.department_id) else []

    async def aggregate_department_comparison(self, *_args):
        return [
            {
                "_id": self.employee.id,
                "average_performance_score": 86.5,
                "average_quality_score": 90,
                "total_tasks": 8,
                "metric_days": 2,
            }
        ]

    async def aggregate_employee_trend(self, *_args):
        return [
            {
                "date": date(2026, 9, 10),
                "tasks_completed": 4,
                "quality_score": 90,
                "performance_score": 87,
            }
        ]

    async def aggregate_department_trend(self, *_args):
        return [
            {
                "date": date(2026, 9, 9),
                "average_performance_score": 82,
                "average_quality_score": 85,
                "total_tasks": 3,
                "employee_count": 1,
            },
            {
                "date": date(2026, 9, 10),
                "average_performance_score": 88,
                "average_quality_score": 90,
                "total_tasks": 4,
                "employee_count": 1,
            },
        ]


class EmptyRepoFake:
    async def find_department(self, _department_id):
        return None

    async def list_departments(self):
        return []

    async def list_employees(self, _scope=None):
        return []


class AlertRepoFake:
    def __init__(self, alert) -> None:
        self.alert = alert

    async def find_many(self, _scope, status=None, alert_type=None):
        return [self.alert] if status == "open" else []


@pytest.mark.asyncio
async def test_manager_cannot_select_employee_or_department_outside_scope() -> None:
    own_department = ObjectId()
    employee = _employee(ObjectId(), own_department, "Nguyễn An")
    service = AiDataToolService(
        PerformanceRepoFake(own_department, employee),
        SimpleNamespace(),
        SimpleNamespace(),
        SimpleNamespace(),
        SimpleNamespace(),
    )

    outside_employee = await service.get_employee_performance(
        EmployeePerformanceToolInput(employee_name="Trần Bình"), own_department
    )
    outside_department = await service.get_department_performance(
        DepartmentPerformanceToolInput(department_name="Phòng Nhân sự"), own_department
    )

    assert outside_employee["co_du_lieu"] is False
    assert outside_department["co_du_lieu"] is False


@pytest.mark.asyncio
async def test_department_performance_includes_weighted_department_summary() -> None:
    department_id = ObjectId()
    employee = _employee(ObjectId(), department_id, "Nguyễn An")
    service = AiDataToolService(
        PerformanceRepoFake(department_id, employee),
        SimpleNamespace(),
        SimpleNamespace(),
        SimpleNamespace(),
        SimpleNamespace(),
    )

    result = await service.get_department_performance(
        DepartmentPerformanceToolInput(), department_id
    )

    assert result["co_du_lieu"] is True
    assert result["pham_vi"] == "Phòng Kinh doanh"
    assert result["ky_du_lieu"] == {"tu_ngay": None, "den_ngay": None}
    assert result["nguon_du_lieu"] == ["Chỉ số hiệu suất", "Nhân viên", "Phòng ban"]
    assert result["tong_quan"] == {
        "Phòng ban": "Phòng Kinh doanh",
        "Điểm hiệu suất trung bình": 86.5,
        "Điểm chất lượng trung bình": 90.0,
        "Số nhân viên có ghi nhận": 1,
        "Số ngày có ghi nhận": 2,
        "Tổng công việc hoàn thành": 8,
    }


@pytest.mark.asyncio
async def test_employee_tool_returns_compact_vietnamese_data_without_ids() -> None:
    department_id = ObjectId()
    employee = _employee(ObjectId(), department_id, "Nguyễn An")
    service = AiDataToolService(
        PerformanceRepoFake(department_id, employee),
        SimpleNamespace(),
        SimpleNamespace(),
        SimpleNamespace(),
        SimpleNamespace(),
    )

    result = await service.get_employee_performance(
        EmployeePerformanceToolInput(employee_name="Nguyễn An"), department_id
    )

    assert result["co_du_lieu"] is True
    assert result["du_lieu"][0]["Nhân viên"] == "Nguyễn An"
    assert "employee_id" not in str(result)


@pytest.mark.asyncio
async def test_performance_trend_returns_backend_computed_direction_and_contract() -> None:
    department_id = ObjectId()
    employee = _employee(ObjectId(), department_id, "Nguyễn An")
    service = AiDataToolService(
        PerformanceRepoFake(department_id, employee),
        SimpleNamespace(),
        SimpleNamespace(),
        SimpleNamespace(),
        SimpleNamespace(),
    )

    result = await service.get_performance_trend(
        PerformanceTrendToolInput(date_from=date(2026, 9, 9), date_to=date(2026, 9, 10)),
        department_id,
    )

    assert result["co_du_lieu"] is True
    assert result["tong_quan"]["Xu hướng"] == "tăng"
    assert result["tong_quan"]["Thay đổi điểm hiệu suất"] == 6.0
    assert result["du_lieu"][0]["Ngày"] == "2026-09-09"


@pytest.mark.asyncio
async def test_compare_performance_periods_returns_bounded_summary() -> None:
    department_id = ObjectId()
    employee = _employee(ObjectId(), department_id, "Nguyễn An")
    service = AiDataToolService(
        PerformanceRepoFake(department_id, employee),
        SimpleNamespace(),
        SimpleNamespace(),
        SimpleNamespace(),
        SimpleNamespace(),
    )

    result = await service.get_compare_performance_periods(
        ComparePerformancePeriodsToolInput(
            date_from=date(2026, 9, 10), date_to=date(2026, 9, 10)
        ),
        department_id,
    )

    assert result["co_du_lieu"] is True
    assert result["tong_quan"]["Kỳ hiện tại"]["Điểm hiệu suất trung bình"] == 86.5
    assert result["tong_quan"]["Kỳ trước"]["Số ngày có ghi nhận"] == 2


@pytest.mark.asyncio
async def test_explain_alert_returns_minimal_alert_evidence_without_ids() -> None:
    department_id = ObjectId()
    employee = _employee(ObjectId(), department_id, "Nguyễn An")
    alert = SimpleNamespace(
        id=ObjectId(),
        employee_id=employee.id,
        employee_name=employee.full_name,
        alert_type="overload",
        severity=SimpleNamespace(value="high"),
        title="Cảnh báo quá tải",
        message="Khối lượng công việc tăng cao.",
        detected_dates=[date(2026, 9, 10)],
        suggested_action="Kiểm tra và điều phối công việc.",
    )
    service = AiDataToolService(
        PerformanceRepoFake(department_id, employee),
        AlertRepoFake(alert),
        SimpleNamespace(),
        SimpleNamespace(),
        SimpleNamespace(),
    )

    result = await service.explain_alert(
        ExplainAlertToolInput(employee_name="Nguyễn An"), department_id
    )

    assert result["co_du_lieu"] is True
    assert result["du_lieu"][0]["Nhân viên"] == "Nguyễn An"
    assert "employee_id" not in str(result)
    assert result["nguon_du_lieu"] == ["Cảnh báo", "Chỉ số hiệu suất"]


class ToolServiceFake:
    def __init__(self, result):
        self.result = result

    async def read_data_from_message(self, *_args):
        return self.result


class ChatServiceFake:
    def __init__(self) -> None:
        self.grounded_called = False

    async def stream_grounded_response(self, *_args, **_kwargs):
        self.grounded_called = True
        yield "Câu trả lời dựa trên dữ liệu thật."

    async def stream_response(self, *_args, **_kwargs):
        yield "Câu trả lời thông thường."


@pytest.mark.asyncio
async def test_data_question_with_no_tool_result_has_safe_no_hallucination_answer() -> None:
    user = CurrentUser(
        user_id="manager-1",
        username="manager",
        full_name="Quản lý",
        role=UserRole.MANAGER,
        department_id=str(ObjectId()),
    )
    chat = ChatServiceFake()
    orchestrator = AiChatOrchestrator(
        chat, ToolServiceFake(("no_tool_call", None, None, "Không có công cụ"))
    )

    chunks = [
        chunk
        async for chunk in orchestrator.stream_response(
            "Phòng tôi có bao nhiêu cảnh báo mở?", ObjectId(), user
        )
    ]

    assert chunks == [SAFE_DATA_ACCESS_MESSAGE]
    assert chat.grounded_called is False


@pytest.mark.asyncio
async def test_successful_empty_alert_tool_returns_no_open_alerts_message() -> None:
    user = CurrentUser(
        user_id="manager-1",
        username="manager",
        full_name="Quản lý",
        role=UserRole.MANAGER,
        department_id=str(ObjectId()),
    )
    chat = ChatServiceFake()
    orchestrator = AiChatOrchestrator(
        chat,
        ToolServiceFake(
            (
                "executed",
                "get_open_alerts",
                {"co_du_lieu": False, "du_lieu": []},
                "Đã đọc dữ liệu.",
            )
        ),
    )

    chunks = [
        chunk
        async for chunk in orchestrator.stream_response(
            "Cảnh báo hôm nay của tôi là gì?", ObjectId(), user
        )
    ]

    assert chunks == [NO_OPEN_ALERTS_MESSAGE]
    assert chat.grounded_called is False


@pytest.mark.asyncio
async def test_data_question_uses_grounded_result_after_tool_execution() -> None:
    user = CurrentUser(
        user_id="lead-1",
        username="leadership",
        full_name="Lãnh đạo",
        role=UserRole.LEADERSHIP,
    )
    chat = ChatServiceFake()
    data = {"co_du_lieu": True, "du_lieu": [{"Nhân viên": "Nguyễn An", "Điểm hiệu suất": 90}]}
    orchestrator = AiChatOrchestrator(
        chat, ToolServiceFake(("executed", "get_employee_performance", data, "Đã đọc dữ liệu"))
    )

    chunks = [
        chunk
        async for chunk in orchestrator.stream_response(
            "Hiệu suất của Nguyễn An thế nào?", None, user
        )
    ]

    assert chunks == ["Câu trả lời dựa trên dữ liệu thật."]
    assert chat.grounded_called is True


def test_registry_exposes_only_the_bounded_read_tools_to_the_planner() -> None:
    registry = build_tool_registry(
        SimpleNamespace(repository=SimpleNamespace()),
        data_service=SimpleNamespace(),
    )
    names = {definition.name for definition in registry.definitions_for(UserRole.LEADERSHIP)}
    manager_names = {definition.name for definition in registry.definitions_for(UserRole.MANAGER)}

    assert names == {
        "get_department_weekly_evaluation",
        "get_company_performance_summary",
        "get_department_risk_summary",
        "get_manager_evaluations",
        "get_overdue_work_summary",
        "get_cross_department_coordination_candidates",
        "compare_departments",
    }
    assert {
        "get_department_performance",
        "get_employee_performance",
        "get_performance_trend",
        "compare_performance_periods",
        "explain_alert",
        "get_open_alerts",
        "get_overloaded_employees",
        "get_overdue_tasks",
        "get_department_weekly_evaluation",
    }.issubset(manager_names)
    assert "get_rebalance_candidates" in manager_names
    assert not {
        "get_company_performance_summary",
        "get_department_risk_summary",
        "get_manager_evaluations",
        "get_overdue_work_summary",
    } & manager_names
    mutation = next(
        definition
        for definition in registry.definitions_for(UserRole.MANAGER)
        if definition.name == "apply_coordination"
    )
    assert mutation.read_only is False
    assert mutation.requires_human_approval is True


def test_common_vietnamese_data_questions_have_bounded_tool_fallback_routes() -> None:
    performance = _infer_read_tool_call("Hiệu suất của nhân viên trong phòng tôi 7 ngày gần đây thế nào?")
    alerts = _infer_read_tool_call("Cảnh báo hôm nay của tôi là gì?")

    assert performance.name == "get_performance_trend"
    assert performance.arguments["date_to"]
    assert performance.arguments["date_from"]
    assert alerts.name == "get_open_alerts"
    assert alerts.arguments == {}

    comparison = _infer_read_tool_call("So với tuần trước điểm hiệu suất phòng tôi thay đổi thế nào?")
    assert comparison.name == "compare_performance_periods"
    assert comparison.arguments["date_to"]

    leadership_performance = _infer_read_tool_call(
        "Phòng ban nào có hiệu suất tốt nhất?", UserRole.LEADERSHIP
    )
    leadership_risk = _infer_read_tool_call(
        "Phòng ban nào đang có nhiều cảnh báo?", UserRole.LEADERSHIP
    )
    leadership_overdue = _infer_read_tool_call(
        "Công việc quá hạn đang tập trung ở đâu?", UserRole.LEADERSHIP
    )
    leadership_evaluations = _infer_read_tool_call(
        "Tổng hợp đánh giá quản lý trong tháng này.", UserRole.LEADERSHIP
    )
    assert leadership_performance.name == "get_company_performance_summary"
    assert leadership_risk.name == "get_department_risk_summary"
    assert leadership_overdue.name == "get_overdue_work_summary"
    assert leadership_evaluations.name == "get_manager_evaluations"
