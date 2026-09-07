"""Translate technical metric fields before they reach an AI prompt or UI."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date, datetime
from typing import Any

FIELD_LABELS_VI: dict[str, str] = {
    "overload_index": "Chỉ số quá tải",
    "avg_task_completion_time": "Thời gian hoàn thành công việc trung bình",
    "performance_score": "Điểm hiệu suất",
    "threshold_breach_count": "Số lần vượt ngưỡng cho phép",
    "tasks_completed": "Số công việc hoàn thành",
    "quality_score": "Điểm chất lượng công việc",
    "baseline_quality_avg": "Chất lượng trung bình làm mốc so sánh",
    "department_avg_performance": "Hiệu suất trung bình của phòng ban",
    "leadership_score": "Điểm đánh giá từ Lãnh đạo",
    "trigger_reason": "Lý do phát sinh cảnh báo",
    "employee_id": "Mã định danh nhân viên",
    "department_id": "Mã định danh phòng ban",
    "reviewed_by": "Người đánh giá",
    "resolved_by": "Người xử lý",
    "resolved_at": "Thời điểm xử lý",
    "employee_code": "Mã nhân viên",
    "employee_name": "Tên nhân viên",
    "full_name": "Họ và tên",
    "department_name": "Tên phòng ban",
    "date": "Ngày",
    "month": "Tháng",
    "note": "Ghi chú",
    "resolution_note": "Ghi chú xử lý",
    "suggested_action": "Hành động gợi ý",
    "alert_type": "Loại cảnh báo",
    "severity": "Mức độ cảnh báo",
    "status": "Trạng thái",
    "title": "Tiêu đề",
    "message": "Nội dung",
    "created_at": "Thời điểm tạo",
    "updated_at": "Thời điểm cập nhật",
    "detected_dates": "Các ngày phát hiện",
    "total_tasks": "Tổng số công việc",
    "metric_days": "Số ngày có dữ liệu",
    "average_performance_score": "Điểm hiệu suất trung bình",
    "average_quality_score": "Điểm chất lượng trung bình",
    "employee_count": "Số nhân viên",
    "performance_metrics": "Dữ liệu hiệu suất",
    "alerts": "Các cảnh báo",
    "overload_logs": "Nhật ký quá tải",
    "scope": "Phạm vi dữ liệu",
}

VALUE_LABELS_VI: dict[str, str] = {
    "task_volume": "khối lượng công việc",
    "quality_drop": "chất lượng giảm",
    "early_warning": "cảnh báo sớm",
    "overload": "quá tải",
    "open": "đang mở",
    "resolved": "đã xử lý",
    "medium": "trung bình",
    "high": "cao",
}


def _label_for_key(key: str) -> str:
    return FIELD_LABELS_VI.get(key, "Thông tin")


def _format_value(value: Any) -> str:
    if value is None:
        return "chưa có dữ liệu"
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, bool):
        return "có" if value else "không"
    if isinstance(value, str) and value in VALUE_LABELS_VI:
        return VALUE_LABELS_VI[value]
    return str(value)


def translate_metrics_to_vietnamese(data: dict[str, Any]) -> str:
    """Render nested JSON as readable Vietnamese without exposing raw keys."""

    lines: list[str] = []

    def visit(value: Any, label: str, depth: int = 0) -> None:
        indent = "  " * depth
        if isinstance(value, Mapping):
            if not value:
                lines.append(f"{indent}{label}: chưa có dữ liệu")
                return
            lines.append(f"{indent}{label}:")
            for key, nested_value in value.items():
                visit(nested_value, _label_for_key(str(key)), depth + 1)
            return
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            if not value:
                lines.append(f"{indent}{label}: chưa có dữ liệu")
                return
            lines.append(f"{indent}{label}:")
            for item in value:
                visit(item, "- Mục dữ liệu", depth + 1)
            return
        lines.append(f"{indent}{label}: {_format_value(value)}")

    for key, value in data.items():
        visit(value, _label_for_key(str(key)))
    return "\n".join(lines)


def sanitize_ai_text(text: str) -> str:
    """Replace technical field names in provider output as a final safety net."""

    sanitized = text
    for technical_name, label in sorted(FIELD_LABELS_VI.items(), key=lambda item: -len(item[0])):
        sanitized = sanitized.replace(technical_name, label)
    return sanitized
