import pytest

from app.services.ai_chat_orchestrator import AiChatOrchestrator
from app.services.ai_tool_service import _infer_read_tool_call

MANAGER_QUERY_CASES = (
    ("Hiệu suất phòng tôi 7 ngày gần đây thế nào?", "get_performance_trend"),
    ("So với tuần trước điểm hiệu suất phòng tôi thay đổi thế nào?", "compare_performance_periods"),
    ("Hiệu suất của Nguyễn An trong 7 ngày gần đây thế nào?", "get_performance_trend"),
    ("Cảnh báo hôm nay của phòng tôi là gì?", "get_open_alerts"),
    ("Nhân viên nào đang quá tải?", "get_overloaded_employees"),
    ("Đánh giá phòng ban tuần này thế nào?", "get_department_weekly_evaluation"),
    ("Có công việc nào đang quá hạn không?", "get_overdue_tasks"),
    ("Theo dõi hiệu suất phòng tôi tuần này ra sao?", "get_performance_trend"),
    ("Diễn biến điểm chất lượng 7 ngày gần đây thế nào?", "get_performance_trend"),
    ("Điểm hiệu suất phòng tôi gần đây có giảm không?", "get_performance_trend"),
    ("So sánh hiệu suất phòng tôi với tuần trước.", "compare_performance_periods"),
    ("Điểm chất lượng so với kỳ trước thay đổi ra sao?", "compare_performance_periods"),
    ("Phòng tôi tốt hơn tuần trước không?", "compare_performance_periods"),
    ("Giải thích cảnh báo của Nguyễn An.", "explain_alert"),
    ("Giải thích cảnh báo của Trần Bình trong phòng tôi.", "explain_alert"),
    ("Cảnh báo mở của phòng tôi là gì?", "get_open_alerts"),
    ("Có cảnh báo quá tải nào hôm nay không?", "get_open_alerts"),
    ("Danh sách cảnh báo mức cao của tôi.", "get_open_alerts"),
    ("Những ai có dấu hiệu quá tải trong 7 ngày?", "get_overloaded_employees"),
    ("Ai đang bị quá tải gần đây?", "get_overloaded_employees"),
    ("Tình hình quá tải của phòng ban thế nào?", "get_overloaded_employees"),
    ("Các nhiệm vụ trễ hạn của phòng tôi là gì?", "get_overdue_tasks"),
    ("Hôm nay có việc nào quá hạn không?", "get_overdue_tasks"),
    ("Tôi cần xử lý công việc quá hạn nào?", "get_overdue_tasks"),
    ("Đánh giá phòng ban tuần này của tôi.", "get_department_weekly_evaluation"),
    ("Điểm đánh giá tuần của phòng tôi là bao nhiêu?", "get_department_weekly_evaluation"),
    ("Tóm tắt đánh giá phòng ban tuần này.", "get_department_weekly_evaluation"),
    ("Điểm hiệu suất trung bình của phòng tôi là bao nhiêu?", "get_department_performance"),
    ("Phòng ban tôi có hiệu suất thế nào?", "get_department_performance"),
    ("Cho tôi xem kết quả hiệu suất phòng ban.", "get_department_performance"),
    ("Nhân viên Nguyễn An đạt hiệu suất bao nhiêu?", "get_employee_performance"),
    ("Có ai trong phòng tôi cần chú ý không?", "get_department_performance"),
    ("Hiệu suất của phòng tôi trong tháng này thế nào?", "get_department_performance"),
    ("Theo dõi điểm hiệu suất gần đây của Nguyễn An.", "get_performance_trend"),
    ("So với tuần trước phòng tôi có tiến bộ không?", "compare_performance_periods"),
)


@pytest.mark.parametrize(("message", "expected_tool"), MANAGER_QUERY_CASES)
def test_manager_vietnamese_queries_have_bounded_fallback_route(message, expected_tool) -> None:
    call = _infer_read_tool_call(message)

    assert call is not None
    assert call.name == expected_tool
    assert AiChatOrchestrator.requires_data_tool(message) is True


def test_employee_trend_fallback_keeps_employee_name_as_bounded_input() -> None:
    call = _infer_read_tool_call("Hiệu suất của Nguyễn An trong 7 ngày gần đây thế nào?")

    assert call is not None
    assert call.name == "get_performance_trend"
    assert call.arguments["employee_name"] == "Nguyễn An"


def test_manager_eval_cases_are_unique_and_do_not_contain_raw_query_instructions() -> None:
    messages = [message.casefold() for message, _ in MANAGER_QUERY_CASES]

    assert len(messages) == len(set(messages))
    assert not any("mongo" in message or "sql" in message for message in messages)
