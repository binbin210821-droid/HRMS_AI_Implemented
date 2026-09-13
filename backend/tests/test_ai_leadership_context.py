from datetime import date
from types import SimpleNamespace

import pytest
from bson import ObjectId
from pydantic import ValidationError

from app.ai.tooling import ToolCall, ToolExecutionContext, ToolNotAllowedError
from app.models.ai_leadership import (
    LeadershipAiContextBuilder,
    LeadershipContextAccessError,
    LeadershipCrossDepartmentCandidate,
    LeadershipDepartmentSummary,
    LeadershipRiskSummary,
)
from app.models.ai_tools import LeadershipDepartmentSummaryToolInput
from app.models.task import ACTIVE_DIRECTIVE_STATUSES
from app.models.user import CurrentUser, UserRole
from app.services.ai_data_tool_service import AiDataToolService
from app.services.ai_leadership_context_service import AiLeadershipContextService
from app.services.ai_service import AiService
from app.services.ai_tool_service import build_tool_registry


def _user(role: UserRole) -> CurrentUser:
    return CurrentUser(
        user_id="user-1",
        username="test-user",
        full_name="Người dùng kiểm thử",
        role=role,
        department_id="department-1" if role == UserRole.MANAGER else None,
    )


def test_leadership_context_has_company_scope_and_vietnamese_prompt_labels() -> None:
    context = LeadershipAiContextBuilder.build(
        _user(UserRole.LEADERSHIP),
        departments=[
            LeadershipDepartmentSummary(
                department_id="department-1",
                department_name="Kinh doanh",
                employee_count=6,
                average_performance_score=82.7,
                average_quality_score=85.84,
                completed_task_count=24,
                trend="increasing",
            )
        ],
        risks=[
            LeadershipRiskSummary(
                department_id="department-1",
                department_name="Kinh doanh",
                open_alert_count=2,
                affected_employee_count=2,
                overdue_task_count=4,
                maximum_overdue_days=3,
                highest_severity="high",
            )
        ],
    )

    assert context.role == "leadership"
    assert context.scope == "company"
    prompt_data = context.to_prompt_data()
    assert prompt_data["Phạm vi"] == "toàn công ty"
    assert prompt_data["Phòng ban"][0]["Tên phòng ban"] == "Kinh doanh"
    assert prompt_data["Rủi ro phòng ban"][0]["Số công việc quá hạn"] == 4
    assert "employee_id" not in str(prompt_data)
    assert "email" not in str(prompt_data).casefold()
    assert "phone" not in str(prompt_data).casefold()


def test_manager_cannot_build_company_level_leadership_context() -> None:
    with pytest.raises(LeadershipContextAccessError):
        LeadershipAiContextBuilder.build(_user(UserRole.MANAGER))


def test_leadership_context_rejects_unapproved_personal_fields() -> None:
    with pytest.raises(ValidationError):
        LeadershipDepartmentSummary(
            department_id="department-1",
            department_name="Kinh doanh",
            email="hidden@example.com",
        )


class _LeadershipClock:
    def today(self):
        return date(2026, 9, 10)


class _LeadershipPerformanceRepository:
    def __init__(self, department_id: ObjectId):
        self.department_id = department_id

    async def list_departments(self):
        return [SimpleNamespace(id=self.department_id, name="Kinh doanh")]

    async def aggregate_company_comparison(self, start_date, _end_date):
        score = 82 if start_date == date(2026, 9, 4) else 78
        return [
            {
                "_id": self.department_id,
                "average_performance_score": score,
                "average_quality_score": 85,
                "total_tasks": 24,
                "metric_days": 6,
                "employee_count": 6,
            }
        ]


@pytest.mark.asyncio
async def test_company_summary_is_department_level_and_rejects_manager_scope() -> None:
    department_id = ObjectId()
    service = AiDataToolService(
        _LeadershipPerformanceRepository(department_id),
        SimpleNamespace(),
        SimpleNamespace(),
        SimpleNamespace(),
        SimpleNamespace(),
        clock=_LeadershipClock(),
    )
    arguments = LeadershipDepartmentSummaryToolInput(
        date_from=date(2026, 9, 4), date_to=date(2026, 9, 10)
    )

    company_result = await service.get_company_performance_summary(arguments, None)
    manager_result = await service.get_company_performance_summary(arguments, department_id)

    assert company_result["co_du_lieu"] is True
    assert company_result["du_lieu"] == [
        {
            "Phòng ban": "Kinh doanh",
            "Số nhân viên": 6,
            "Điểm hiệu suất trung bình": 82.0,
            "Điểm chất lượng trung bình": 85.0,
            "Số công việc hoàn thành": 24,
            "Xu hướng": "increasing",
        }
    ]
    assert "Nhân viên" not in str(company_result["du_lieu"])
    assert manager_result["co_du_lieu"] is False


@pytest.mark.asyncio
async def test_leadership_context_service_assembles_only_company_aggregates() -> None:
    department_id = ObjectId()

    class _EmptyAlerts:
        async def find_many(self, *_args, **_kwargs):
            return []

    class _EmptyOverload:
        async def list_logs(self, *_args, **_kwargs):
            return []

    class _EmptyTasks:
        async def find_many(self, *_args, **_kwargs):
            return []

        async def list_directed_task_ids(self, *_args, **_kwargs):
            return set()

    class _EmptyEvaluations:
        async def list_evaluations(self, *_args, **_kwargs):
            return [], 0

    data_service = AiDataToolService(
        _LeadershipPerformanceRepository(department_id),
        _EmptyAlerts(),
        _EmptyOverload(),
        _EmptyTasks(),
        _EmptyEvaluations(),
        clock=_LeadershipClock(),
    )

    context = await AiLeadershipContextService(data_service).build(_user(UserRole.LEADERSHIP))

    assert context.scope == "company"
    assert [item.department_name for item in context.departments] == ["Kinh doanh"]
    assert context.to_prompt_data()["Phòng ban"][0]["Tên phòng ban"] == "Kinh doanh"
    assert "Mã tham chiếu nội bộ" not in str(context.to_prompt_data())


@pytest.mark.asyncio
async def test_leadership_chat_prompt_uses_aggregate_context_instead_of_personal_rows() -> None:
    class _LeadershipContext:
        async def build_for_leadership(self):
            return _leadership_context()

    service = AiService(
        SimpleNamespace(),
        SimpleNamespace(),
        SimpleNamespace(),
        _ProviderFactory("Kết quả"),
        leadership_context_service=_LeadershipContext(),
    )

    prompt = await service._build_chat_prompt(
        "Tóm tắt tình hình công ty",
        None,
        "summary",
        UserRole.LEADERSHIP,
    )

    assert "Kinh doanh" in prompt
    assert "Mã tham chiếu nội bộ" not in prompt
    assert "employee_id" not in prompt


@pytest.mark.asyncio
async def test_department_risk_summary_does_not_expose_assignees() -> None:
    department_id = ObjectId()
    alert = SimpleNamespace(
        department_id=department_id,
        employee_id=ObjectId(),
        alert_type="overload",
        severity=SimpleNamespace(value="high"),
        detected_dates=[date(2026, 9, 10)],
    )
    task = SimpleNamespace(
        id=ObjectId(),
        department_id=department_id,
        due_date=date(2026, 9, 7),
    )
    service = AiDataToolService(
        _LeadershipPerformanceRepository(department_id),
        SimpleNamespace(find_many=lambda *_args, **_kwargs: None),
        SimpleNamespace(list_logs=lambda *_args: None),
        SimpleNamespace(),
        SimpleNamespace(),
        clock=_LeadershipClock(),
    )
    service.alert_repository.find_many = lambda *_args, **_kwargs: _async_value([alert])
    service.task_repository.find_many = lambda *_args, **_kwargs: _async_value([task])
    service.task_repository.list_directed_task_ids = lambda *_args, **_kwargs: _async_value(set())
    service.overload_repository.list_logs = lambda *_args: _async_value([])

    result = await service.get_department_risk_summary(
        LeadershipDepartmentSummaryToolInput(
            date_from=date(2026, 9, 10), date_to=date(2026, 9, 10)
        ),
        None,
    )

    assert result["co_du_lieu"] is True
    assert result["du_lieu"][0]["Số cảnh báo quá tải"] == 1
    assert result["du_lieu"][0]["Số công việc quá hạn"] == 1
    assert "employee_id" not in str(result)
    assert "Nhân viên phụ trách" not in str(result)


@pytest.mark.asyncio
async def test_overdue_work_summary_counts_all_tasks_and_separates_undirected_tasks() -> None:
    department_id = ObjectId()
    directed_task = SimpleNamespace(
        id=ObjectId(),
        department_id=department_id,
        employee_id=ObjectId(),
        due_date=date(2026, 9, 7),
        priority=SimpleNamespace(value="high"),
    )
    undirected_task = SimpleNamespace(
        id=ObjectId(),
        department_id=department_id,
        employee_id=ObjectId(),
        due_date=date(2026, 9, 8),
        priority=SimpleNamespace(value="medium"),
    )
    accepted_task = SimpleNamespace(
        id=ObjectId(),
        department_id=department_id,
        employee_id=ObjectId(),
        due_date=date(2026, 9, 6),
        priority=SimpleNamespace(value="low"),
    )

    class _Tasks:
        def __init__(self) -> None:
            self.requested_statuses = None

        async def find_many(self, *_args, **_kwargs):
            return [directed_task, undirected_task, accepted_task]

        async def list_directed_task_ids(self, statuses=None):
            self.requested_statuses = statuses
            return {directed_task.id}

    tasks = _Tasks()
    service = AiDataToolService(
        _LeadershipPerformanceRepository(department_id),
        SimpleNamespace(),
        SimpleNamespace(),
        tasks,
        SimpleNamespace(),
        clock=_LeadershipClock(),
    )

    result = await service.get_overdue_work_summary(
        LeadershipDepartmentSummaryToolInput(), None
    )

    assert tasks.requested_statuses == ACTIVE_DIRECTIVE_STATUSES
    assert result["tong_quan"]["Tổng số công việc quá hạn"] == 3
    assert result["tong_quan"]["Tổng số công việc quá hạn chưa gửi chỉ thị"] == 2
    assert result["du_lieu"][0]["Số công việc quá hạn"] == 3
    assert result["du_lieu"][0]["Số công việc quá hạn chưa gửi chỉ thị"] == 2


async def _async_value(value):
    return value


@pytest.mark.asyncio
async def test_leadership_cannot_execute_manager_detail_tool() -> None:
    registry = build_tool_registry(
        SimpleNamespace(repository=SimpleNamespace()),
        data_service=SimpleNamespace(),
    )

    with pytest.raises(ToolNotAllowedError):
        await registry.execute(
            ToolCall("get_employee_performance", {"employee_name": "Nguyễn An"}),
            ToolExecutionContext("leadership-1", UserRole.LEADERSHIP, None),
        )


class _ProviderFactory:
    def __init__(self, output: str):
        self.output = output

    async def generate_insight_stream(self, _prompt, **_kwargs):
        yield self.output


def _leadership_context():
    return LeadershipAiContextBuilder.build(
        _user(UserRole.LEADERSHIP),
        departments=[
            LeadershipDepartmentSummary(
                department_id="department-1",
                department_name="Kinh doanh",
                employee_count=6,
                average_performance_score=82,
            )
        ],
    )


def test_leadership_coordination_tool_is_role_scoped_and_deterministic() -> None:
    from app.services.ai_tool_service import _infer_read_tool_call

    call = _infer_read_tool_call(
        "Phòng ban nào có thể hỗ trợ liên phòng ban?", UserRole.LEADERSHIP
    )

    assert call is not None
    assert call.name == "get_cross_department_coordination_candidates"


@pytest.mark.asyncio
async def test_leadership_proposal_keeps_real_coordination_pair_and_drops_fake_pair() -> None:
    context = LeadershipAiContextBuilder.build(
        _user(UserRole.LEADERSHIP),
        departments=[
            LeadershipDepartmentSummary(
                department_id="source-1", department_name="Kinh doanh", employee_count=4
            ),
            LeadershipDepartmentSummary(
                department_id="target-1", department_name="Bán hàng", employee_count=4
            ),
        ],
        coordination_candidates=[
            LeadershipCrossDepartmentCandidate(
                source_department_id="source-1",
                source_department_name="Kinh doanh",
                target_department_id="target-1",
                target_department_name="Bán hàng",
                available_employee_count=2,
                capacity_score=50,
                skill_fit_score=80,
                deadline_reliability_score=90,
                recent_quality_score=88,
                fit_score=77,
                evidence=["Có 2 người đang ở mức tải an toàn"],
            )
        ],
    )
    provider = _ProviderFactory(
        '{"summary":"Có thể hỗ trợ.","actions":['
        '{"type":"cross_department_coordination","source_department_id":"source-1",'
        '"target_department_id":"target-1","action":"transfer_work",'
        '"tasks_to_transfer":1,"rationale":"Có năng lực hỗ trợ.","evidence":[]},'
        '{"type":"cross_department_coordination","source_department_id":"source-1",'
        '"target_department_id":"target-fake","action":"transfer_work",'
        '"tasks_to_transfer":1,"rationale":"Không có căn cứ.","evidence":[]}'
        ']} '
    )
    result = await AiService(SimpleNamespace(), SimpleNamespace(), SimpleNamespace(), provider).generate_leadership_action_proposal(context)

    assert len(result.actions) == 1
    assert result.actions[0].type == "cross_department_coordination"
    assert result.actions[0].fit_score == 77


@pytest.mark.asyncio
async def test_leadership_proposal_validates_and_filters_unknown_department() -> None:
    provider = _ProviderFactory(
        '{"summary":"Cần theo dõi Kinh doanh.","actions":['
        '{"type":"issue_department_directive","department_id":"department-1",'
        '"alert_type":"overload","severity":"high","note":"Rà soát khối lượng.",'
        '"rationale":"Có dấu hiệu quá tải.","evidence":["2 cảnh báo mở"]},'
        '{"type":"issue_department_directive","department_id":"department-fake",'
        '"rationale":"Không có căn cứ.","evidence":[]}'
        ']}'
    )
    service = AiService(
        SimpleNamespace(), SimpleNamespace(), SimpleNamespace(), provider
    )

    result = await service.generate_leadership_action_proposal(_leadership_context())

    assert result.summary == "Cần theo dõi Kinh doanh."
    assert len(result.actions) == 1
    assert result.actions[0].department_id == "department-1"
    assert result.actions[0].type == "issue_department_directive"


@pytest.mark.asyncio
@pytest.mark.parametrize("output", ["Không phải JSON", '{"summary":"thiếu actions"}'])
async def test_leadership_proposal_invalid_output_falls_back_safely(output: str) -> None:
    service = AiService(
        SimpleNamespace(),
        SimpleNamespace(),
        SimpleNamespace(),
        _ProviderFactory(output),
    )

    result = await service.generate_leadership_action_proposal(_leadership_context())

    assert result.actions == []
    assert result.summary == "Chưa đủ dữ liệu để đề xuất phương án cho Lãnh đạo lúc này."
