from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from typing import Any

from bson import ObjectId
from pymongo.errors import PyMongoError

from app.core.time import BusinessClock
from app.repositories.alert_repository import AlertRepository
from app.repositories.overload_repository import OverloadRepository
from app.repositories.performance_repository import PerformanceRepository
from app.repositories.task_repository import TaskRepository


class ManagerBriefingService:
    """Build a bounded, scope-aware briefing before any model call."""

    def __init__(
        self,
        performance_repository: PerformanceRepository,
        alert_repository: AlertRepository,
        overload_repository: OverloadRepository,
        task_repository: TaskRepository,
        clock: BusinessClock | None = None,
    ) -> None:
        self.performance_repository = performance_repository
        self.alert_repository = alert_repository
        self.overload_repository = overload_repository
        self.task_repository = task_repository
        self.clock = clock or BusinessClock()

    async def build(
        self, scope: ObjectId | None, max_chars: int = 24000
    ) -> dict[str, Any]:
        scope_label = "toàn công ty" if scope is None else "phòng ban của người dùng"
        try:
            metrics = await self.performance_repository.find_many(scope)
            alerts = await self.alert_repository.find_many(scope, status="open")
            overload_logs = await self.overload_repository.list_logs(scope)
            overdue_tasks = await self.task_repository.find_many(scope, overdue_only=True)
        except (PyMongoError, RuntimeError):
            return {
                "pham_vi": scope_label,
                "ky_du_lieu": {"den_ngay": self.clock.today().isoformat()},
                "note": "Hiện chưa thể tải đầy đủ dữ liệu từ hệ thống.",
                "nguon_du_lieu": [],
            }

        employee_ids = {
            str(getattr(metric, "employee_id", ""))
            for metric in metrics
            if getattr(metric, "employee_id", None) is not None
        }
        daily: defaultdict[str, list[float]] = defaultdict(list)
        performance_values: list[float] = []
        quality_values: list[float] = []
        for metric in metrics:
            metric_date = getattr(metric, "date", None)
            performance = getattr(metric, "performance_score", None)
            quality = getattr(metric, "quality_score", None)
            if metric_date is not None and performance is not None:
                daily[str(metric_date)].append(float(performance))
            if performance is not None:
                performance_values.append(float(performance))
            if quality is not None:
                quality_values.append(float(quality))

        alert_items = [
            {
                "loại": "cảnh báo",
                "nhân viên": alert.employee_name,
                "mức độ": _value(alert.severity),
                "tiêu đề": alert.title,
                "nội dung": alert.message,
                "ưu tiên": 3 if _value(alert.severity) == "high" else 2,
            }
            for alert in alerts[:10]
        ]

        overload_employee_map = await self.overload_repository.find_employees(
            list({log.employee_id for log in overload_logs})
        )
        overload_items = [
            {
                "loại": "quá tải",
                "nhân viên": (
                    overload_employee_map[log.employee_id].full_name
                    if log.employee_id in overload_employee_map
                    else "Nhân viên chưa xác định"
                ),
                "ngày": _value(log.date),
                "lý do": [_value(reason) for reason in log.trigger_reason],
                "số công việc": log.tasks_completed,
                "điểm chất lượng": log.quality_score,
                "ưu tiên": 3,
            }
            for log in overload_logs[:10]
        ]

        employees = {
            str(employee.id): employee.full_name
            for employee in await self.performance_repository.list_employees(scope)
        }
        employee_metrics: defaultdict[str, list[Any]] = defaultdict(list)
        for metric in metrics:
            employee_metrics[str(getattr(metric, "employee_id", ""))].append(metric)
        capacity_candidates = []
        for employee_id, employee_name in employees.items():
            records = employee_metrics.get(employee_id, [])
            task_values = [
                float(getattr(record, "tasks_completed", 0)) for record in records
            ]
            quality_values_for_employee = [
                float(record.quality_score)
                for record in records
                if getattr(record, "quality_score", None) is not None
            ]
            average_tasks = _average(task_values)
            average_quality = _average(quality_values_for_employee)
            if average_tasks is not None and average_quality is not None and average_tasks <= 2:
                capacity_candidates.append(
                    {
                        "nhân viên": employee_name,
                        "số công việc trung bình": average_tasks,
                        "điểm chất lượng trung bình": average_quality,
                    }
                )
        capacity_candidates.sort(
            key=lambda item: (
                _float_value(item["số công việc trung bình"]),
                -_float_value(item["điểm chất lượng trung bình"]),
            )
        )
        overdue_items = [
            {
                "loại": "việc quá hạn",
                "công việc": task.title,
                "nhân viên": employees.get(str(task.employee_id), "Nhân viên chưa xác định"),
                "hạn hoàn thành": _value(task.due_date),
                "ưu tiên": 2,
            }
            for task in overdue_tasks[:10]
        ]

        items = sorted(
            alert_items + overload_items + overdue_items,
            key=lambda item: (-int(item["ưu tiên"]), str(item.get("ngày", ""))),
        )[:15]
        context: dict[str, Any] = {
            "pham_vi": scope_label,
            "ky_du_lieu": {
                "tu_ngay": min(daily) if daily else None,
                "den_ngay": max(daily) if daily else self.clock.today().isoformat(),
            },
            "tong_quan": {
                "Số nhân viên có ghi nhận": len(employee_ids),
                "Điểm hiệu suất trung bình": _average(performance_values),
                "Điểm chất lượng trung bình": _average(quality_values),
                "Số cảnh báo đang mở": len(alerts),
                "Số lượt ghi nhận quá tải": len(overload_logs),
                "Số công việc quá hạn": len(overdue_tasks),
            },
            "điểm_cần_chú_ý": items,
            "ứng_viên_có_thể_nhận_việc": capacity_candidates[:5],
            "xu_hướng_gần_đây": [
                {
                    "Ngày": day,
                    "Điểm hiệu suất trung bình": _average(values),
                }
                for day, values in sorted(daily.items())[-7:]
            ],
            "nguon_du_lieu": [
                "Chỉ số hiệu suất",
                "Cảnh báo",
                "Nhật ký quá tải",
                "Công việc",
                "Nhân viên",
            ],
        }
        if len(str(context)) > max(1000, max_chars):
            context["điểm_cần_chú_ý"] = items[:6]
            context["xu_hướng_gần_đây"] = context["xu_hướng_gần_đây"][-3:]
        return context


def _value(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if hasattr(value, "value"):
        return value.value
    return value


def _average(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 2) if values else None


def _float_value(value: Any) -> float:
    return float(value)


__all__ = ["ManagerBriefingService"]
