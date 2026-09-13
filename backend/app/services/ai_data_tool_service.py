from __future__ import annotations

from datetime import date as Date
from datetime import timedelta
from typing import Any

from bson import ObjectId

from app.core.time import BusinessClock
from app.models.ai_tools import (
    AiDataToolResponse,
    ComparePerformancePeriodsToolInput,
    DepartmentPerformanceToolInput,
    DepartmentWeeklyEvaluationToolInput,
    EmployeePerformanceToolInput,
    ExplainAlertToolInput,
    LeadershipCrossDepartmentCandidatesToolInput,
    LeadershipDepartmentSummaryToolInput,
    LeadershipEvaluationToolInput,
    OpenAlertsToolInput,
    OverdueTasksToolInput,
    OverloadedEmployeesToolInput,
    PerformanceTrendToolInput,
)
from app.models.task import ACTIVE_DIRECTIVE_STATUSES
from app.repositories.alert_repository import AlertRepository
from app.repositories.department_evaluation_repository import DepartmentEvaluationRepository
from app.repositories.overload_repository import OverloadRepository
from app.repositories.performance_repository import PerformanceRepository
from app.repositories.task_repository import TaskRepository


class AiDataToolService:
    """Read-only, bounded and scope-aware data access for the AI tool registry."""

    def __init__(
        self,
        performance_repository: PerformanceRepository,
        alert_repository: AlertRepository,
        overload_repository: OverloadRepository,
        task_repository: TaskRepository,
        evaluation_repository: DepartmentEvaluationRepository,
        clock: BusinessClock | None = None,
    ) -> None:
        self.performance_repository = performance_repository
        self.alert_repository = alert_repository
        self.overload_repository = overload_repository
        self.task_repository = task_repository
        self.evaluation_repository = evaluation_repository
        self.clock = clock or BusinessClock()

    @staticmethod
    def _date_in_range(value: Date, date_from: Date | None, date_to: Date | None) -> bool:
        return (date_from is None or value >= date_from) and (date_to is None or value <= date_to)

    @staticmethod
    def _empty(
        tool_name: str,
        *,
        scope: ObjectId | None = None,
        date_from: Date | None = None,
        date_to: Date | None = None,
        scope_label: str | None = None,
        sources: list[str] | None = None,
    ) -> dict[str, Any]:
        return AiDataToolResponse(
            co_du_lieu=False,
            cong_cu=tool_name,
            pham_vi=scope_label or ("toàn công ty" if scope is None else "phòng ban của người dùng"),
            ky_du_lieu={
                "tu_ngay": date_from.isoformat() if date_from else None,
                "den_ngay": date_to.isoformat() if date_to else None,
            },
            du_lieu=[],
            nguon_du_lieu=sources or [],
        ).model_dump()

    @staticmethod
    def _rows(
        tool_name: str,
        rows: list[dict[str, Any]],
        summary: dict[str, Any] | None = None,
        scope: ObjectId | None = None,
        date_from: Date | None = None,
        date_to: Date | None = None,
        scope_label: str | None = None,
        sources: list[str] | None = None,
    ) -> dict[str, Any]:
        return AiDataToolResponse(
            co_du_lieu=bool(rows),
            cong_cu=tool_name,
            pham_vi=scope_label or ("toàn công ty" if scope is None else "phòng ban của người dùng"),
            ky_du_lieu={
                "tu_ngay": date_from.isoformat() if date_from else None,
                "den_ngay": date_to.isoformat() if date_to else None,
            },
            tong_quan=summary,
            du_lieu=rows,
            nguon_du_lieu=sources or [],
        ).model_dump()

    @staticmethod
    def _department_performance_summary(
        department_name: str, rows: list[dict[str, Any]]
    ) -> dict[str, Any] | None:
        """Return a weighted department aggregate without asking the LLM to calculate it."""

        metric_days = sum(int(row.get("metric_days") or 0) for row in rows)
        if metric_days == 0:
            return None
        performance_total = sum(
            float(row["average_performance_score"]) * int(row.get("metric_days") or 0)
            for row in rows
            if row.get("average_performance_score") is not None
        )
        quality_total = sum(
            float(row["average_quality_score"]) * int(row.get("metric_days") or 0)
            for row in rows
            if row.get("average_quality_score") is not None
        )
        summary = {
            "Phòng ban": department_name,
            "Điểm hiệu suất trung bình": _round(performance_total / metric_days),
            "Điểm chất lượng trung bình": _round(quality_total / metric_days),
            "Số nhân viên có ghi nhận": sum(
                int(row.get("employee_count") or 1) for row in rows
            ),
            "Số ngày có ghi nhận": metric_days,
        }
        if any("total_tasks" in row for row in rows):
            summary["Tổng công việc hoàn thành"] = sum(
                int(row.get("total_tasks") or 0) for row in rows
            )
        return summary

    async def _department_id(
        self,
        department_name: str | None,
        scope: ObjectId | None,
    ) -> ObjectId | None:
        if scope is not None:
            if not department_name:
                return scope
            department = await self.performance_repository.find_department(scope)
            if department and department.name.casefold() == department_name.casefold():
                return scope
            return None

        if not department_name:
            return None
        departments = await self.performance_repository.list_departments()
        exact = [item for item in departments if item.name.casefold() == department_name.casefold()]
        if len(exact) == 1:
            return exact[0].id
        partial = [item for item in departments if department_name.casefold() in item.name.casefold()]
        return partial[0].id if len(partial) == 1 else None

    def _period(
        self, date_from: Date | None, date_to: Date | None, default_days: int = 7
    ) -> tuple[Date, Date] | None:
        end = date_to or self.clock.today()
        start = date_from or (end - timedelta(days=default_days - 1))
        return None if start > end else (start, end)

    async def _find_employee(
        self, employee_name: str, scope: ObjectId | None
    ) -> Any | None:
        employees = await self.performance_repository.list_employees(scope)
        normalized = employee_name.casefold()
        exact = [employee for employee in employees if employee.full_name.casefold() == normalized]
        if len(exact) == 1:
            return exact[0]
        partial = [employee for employee in employees if normalized in employee.full_name.casefold()]
        return partial[0] if len(partial) == 1 else None

    @staticmethod
    def _trend_summary(
        scope_label: str,
        rows: list[dict[str, Any]],
        performance_key: str,
        quality_key: str,
    ) -> dict[str, Any] | None:
        if not rows:
            return None
        performance_values = [
            float(row[performance_key])
            for row in rows
            if row.get(performance_key) is not None
        ]
        quality_values = [
            float(row[quality_key]) for row in rows if row.get(quality_key) is not None
        ]
        if not performance_values:
            return None
        first = performance_values[0]
        last = performance_values[-1]
        change = last - first
        direction = "tăng" if change > 0.01 else "giảm" if change < -0.01 else "ổn định"
        return {
            "Phạm vi": scope_label,
            "Điểm hiệu suất đầu kỳ": _round(first),
            "Điểm hiệu suất cuối kỳ": _round(last),
            "Thay đổi điểm hiệu suất": _round(change),
            "Xu hướng": direction,
            "Điểm hiệu suất trung bình": _round(sum(performance_values) / len(performance_values)),
            "Điểm chất lượng trung bình": (
                _round(sum(quality_values) / len(quality_values)) if quality_values else None
            ),
            "Số ngày có ghi nhận": len(rows),
        }

    @staticmethod
    def _period_average(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
        if not rows:
            return None
        performance_values = [
            float(row["performance_score"])
            for row in rows
            if row.get("performance_score") is not None
        ]
        quality_values = [
            float(row["quality_score"])
            for row in rows
            if row.get("quality_score") is not None
        ]
        return {
            "Điểm hiệu suất trung bình": (
                _round(sum(performance_values) / len(performance_values))
                if performance_values
                else None
            ),
            "Điểm chất lượng trung bình": (
                _round(sum(quality_values) / len(quality_values)) if quality_values else None
            ),
            "Số ngày có ghi nhận": len(rows),
        }

    @staticmethod
    def _comparison_summary(
        scope_label: str,
        current: dict[str, Any] | None,
        previous: dict[str, Any] | None,
        current_period: tuple[Date, Date],
        previous_period: tuple[Date, Date],
    ) -> dict[str, Any] | None:
        if current is None and previous is None:
            return None
        current_score = current.get("Điểm hiệu suất trung bình") if current else None
        previous_score = previous.get("Điểm hiệu suất trung bình") if previous else None
        change = (
            _round(current_score - previous_score)
            if current_score is not None and previous_score is not None
            else None
        )
        return {
            "Phạm vi": scope_label,
            "Kỳ hiện tại": {
                "Từ ngày": current_period[0].isoformat(),
                "Đến ngày": current_period[1].isoformat(),
                **(current or {}),
            },
            "Kỳ trước": {
                "Từ ngày": previous_period[0].isoformat(),
                "Đến ngày": previous_period[1].isoformat(),
                **(previous or {}),
            },
            "Thay đổi điểm hiệu suất": change,
            "Thay đổi phần trăm": (
                _round(change / previous_score * 100)
                if change is not None and previous_score not in (None, 0)
                else None
            ),
        }

    async def get_performance_trend(
        self, arguments: PerformanceTrendToolInput, scope: ObjectId | None
    ) -> dict[str, Any]:
        period = self._period(arguments.date_from, arguments.date_to)
        if period is None:
            return self._empty(
                "get_performance_trend",
                scope=scope,
                date_from=arguments.date_from,
                date_to=arguments.date_to,
                sources=["Chỉ số hiệu suất", "Nhân viên", "Phòng ban"],
            )
        date_from, date_to = period
        if arguments.employee_name:
            employee = await self._find_employee(arguments.employee_name, scope)
            if employee is None:
                return self._empty(
                    "get_performance_trend",
                    scope=scope,
                    date_from=date_from,
                    date_to=date_to,
                    sources=["Chỉ số hiệu suất", "Nhân viên"],
                )
            raw_rows = await self.performance_repository.aggregate_employee_trend(
                employee.id, date_from, date_to
            )
            compact = [
                {
                    "Nhân viên": employee.full_name,
                    "Ngày": _display(row.get("date")),
                    "Điểm hiệu suất": _round(row.get("performance_score")),
                    "Điểm chất lượng": _round(row.get("quality_score")),
                    "Số công việc hoàn thành": int(row.get("tasks_completed") or 0),
                }
                for row in raw_rows[-arguments.limit :]
            ]
            summary = self._trend_summary(
                employee.full_name,
                raw_rows[-arguments.limit :],
                "performance_score",
                "quality_score",
            )
            return self._rows(
                "get_performance_trend",
                compact,
                summary,
                scope=scope,
                date_from=date_from,
                date_to=date_to,
                scope_label=employee.full_name,
                sources=["Chỉ số hiệu suất", "Nhân viên"],
            )

        department_id = await self._department_id(arguments.department_name, scope)
        if department_id is None:
            return self._empty(
                "get_performance_trend",
                scope=scope,
                date_from=date_from,
                date_to=date_to,
                sources=["Chỉ số hiệu suất", "Nhân viên", "Phòng ban"],
            )
        department = await self.performance_repository.find_department(department_id)
        raw_rows = await self.performance_repository.aggregate_department_trend(
            department_id, date_from, date_to
        )
        compact = [
            {
                "Phòng ban": department.name if department else "Phòng ban chưa xác định",
                "Ngày": _display(row.get("date")),
                "Điểm hiệu suất trung bình": _round(row.get("average_performance_score")),
                "Điểm chất lượng trung bình": _round(row.get("average_quality_score")),
                "Số công việc hoàn thành": int(row.get("total_tasks") or 0),
                "Số nhân viên có ghi nhận": int(row.get("employee_count") or 0),
            }
            for row in raw_rows[-arguments.limit :]
        ]
        summary = self._trend_summary(
            department.name if department else "Phòng ban chưa xác định",
            raw_rows[-arguments.limit :],
            "average_performance_score",
            "average_quality_score",
        )
        return self._rows(
            "get_performance_trend",
            compact,
            summary,
            scope=scope,
            date_from=date_from,
            date_to=date_to,
            scope_label=department.name if department else None,
            sources=["Chỉ số hiệu suất", "Nhân viên", "Phòng ban"],
        )

    async def get_compare_performance_periods(
        self, arguments: ComparePerformancePeriodsToolInput, scope: ObjectId | None
    ) -> dict[str, Any]:
        period = self._period(arguments.date_from, arguments.date_to)
        if period is None:
            return self._empty(
                "compare_performance_periods",
                scope=scope,
                sources=["Chỉ số hiệu suất", "Nhân viên", "Phòng ban"],
            )
        current_start, current_end = period
        days = (current_end - current_start).days + 1
        previous_end = current_start - timedelta(days=1)
        previous_start = previous_end - timedelta(days=days - 1)
        scope_label: str | None = None
        if arguments.employee_name:
            employee = await self._find_employee(arguments.employee_name, scope)
            if employee is None:
                return self._empty(
                    "compare_performance_periods",
                    scope=scope,
                    date_from=current_start,
                    date_to=current_end,
                    sources=["Chỉ số hiệu suất", "Nhân viên"],
                )
            current_rows = await self.performance_repository.aggregate_employee_trend(
                employee.id, current_start, current_end
            )
            previous_rows = await self.performance_repository.aggregate_employee_trend(
                employee.id, previous_start, previous_end
            )
            current = self._period_average(current_rows)
            previous = self._period_average(previous_rows)
            scope_label = employee.full_name
            sources = ["Chỉ số hiệu suất", "Nhân viên"]
        else:
            department_id = await self._department_id(arguments.department_name, scope)
            if department_id is None:
                return self._empty(
                    "compare_performance_periods",
                    scope=scope,
                    date_from=current_start,
                    date_to=current_end,
                    sources=["Chỉ số hiệu suất", "Nhân viên", "Phòng ban"],
                )
            department = await self.performance_repository.find_department(department_id)
            current_rows = await self.performance_repository.aggregate_department_comparison(
                department_id, current_start, current_end
            )
            previous_rows = await self.performance_repository.aggregate_department_comparison(
                department_id, previous_start, previous_end
            )
            current = self._department_performance_summary(
                department.name if department else "Phòng ban chưa xác định", current_rows
            )
            previous = self._department_performance_summary(
                department.name if department else "Phòng ban chưa xác định", previous_rows
            )
            scope_label = department.name if department else "Phòng ban chưa xác định"
            sources = ["Chỉ số hiệu suất", "Nhân viên", "Phòng ban"]

        summary = self._comparison_summary(
            scope_label or "Phạm vi được cấp quyền",
            current,
            previous,
            (current_start, current_end),
            (previous_start, previous_end),
        )
        rows = [
            {"Kỳ": "Kỳ hiện tại", **(current or {})},
            {"Kỳ": "Kỳ trước", **(previous or {})},
        ]
        return self._rows(
            "compare_performance_periods",
            [row for row in rows if len(row) > 1],
            summary,
            scope=scope,
            date_from=previous_start,
            date_to=current_end,
            scope_label=scope_label,
            sources=sources,
        )

    async def explain_alert(
        self, arguments: ExplainAlertToolInput, scope: ObjectId | None
    ) -> dict[str, Any]:
        alerts = await self.alert_repository.find_many(scope, status="open")
        if arguments.alert_id:
            alerts = [alert for alert in alerts if str(alert.id) == arguments.alert_id]
        elif arguments.employee_name:
            normalized = arguments.employee_name.casefold()
            alerts = [
                alert
                for alert in alerts
                if normalized in alert.employee_name.casefold()
            ]
        alerts = alerts[: arguments.limit]
        rows: list[dict[str, Any]] = []
        for alert in alerts:
            detected_dates = sorted(alert.detected_dates)
            start = (detected_dates[0] - timedelta(days=7)) if detected_dates else None
            end = detected_dates[-1] if detected_dates else None
            metrics = (
                await self.performance_repository.aggregate_employee_trend(
                    alert.employee_id, start, end
                )
                if start and end
                else []
            )
            rows.append(
                {
                    "Nhân viên": alert.employee_name,
                    "Loại cảnh báo": alert.alert_type,
                    "Mức độ": alert.severity.value,
                    "Tiêu đề": alert.title,
                    "Nội dung": alert.message,
                    "Ngày phát hiện": [item.isoformat() for item in detected_dates],
                    "Gợi ý xử lý": alert.suggested_action,
                    "Chỉ số liên quan": [
                        {
                            "Ngày": _display(metric.get("date")),
                            "Điểm hiệu suất": _round(metric.get("performance_score")),
                            "Điểm chất lượng": _round(metric.get("quality_score")),
                            "Số công việc hoàn thành": int(metric.get("tasks_completed") or 0),
                        }
                        for metric in metrics[-7:]
                    ],
                }
            )
        summary = {
            "Số cảnh báo được giải thích": len(rows),
            "Phạm vi": "toàn công ty" if scope is None else "phòng ban của người dùng",
        } if rows else None
        return self._rows(
            "explain_alert",
            rows,
            summary,
            scope=scope,
            sources=["Cảnh báo", "Chỉ số hiệu suất"],
        )

    async def get_department_performance(
        self, arguments: DepartmentPerformanceToolInput, scope: ObjectId | None
    ) -> dict[str, Any]:
        if arguments.date_from and arguments.date_to and arguments.date_from > arguments.date_to:
            return self._empty(
                "get_department_performance",
                scope=scope,
                date_from=arguments.date_from,
                date_to=arguments.date_to,
                sources=["Chỉ số hiệu suất", "Nhân viên", "Phòng ban"],
            )
        department_id = await self._department_id(arguments.department_name, scope)
        if scope is not None and department_id is None:
            return self._empty(
                "get_department_performance",
                scope=scope,
                date_from=arguments.date_from,
                date_to=arguments.date_to,
                sources=["Chỉ số hiệu suất", "Nhân viên", "Phòng ban"],
            )
        if department_id is not None:
            department = await self.performance_repository.find_department(department_id)
            rows = await self.performance_repository.aggregate_department_comparison(
                department_id, arguments.date_from, arguments.date_to
            )
            employees = await self.performance_repository.list_department_employees(department_id)
            names = {str(employee.id): employee.full_name for employee in employees}
            compact = [
                {
                    "Phòng ban": department.name if department else "Phòng ban chưa xác định",
                    "Nhân viên": names.get(str(row.get("_id")), "Nhân viên chưa xác định"),
                    "Điểm hiệu suất trung bình": _round(row.get("average_performance_score")),
                    "Điểm chất lượng trung bình": _round(row.get("average_quality_score")),
                    "Số công việc hoàn thành": int(row.get("total_tasks", 0)),
                    "Số ngày có ghi nhận": int(row.get("metric_days", 0)),
                }
                for row in rows[: arguments.limit]
            ]
            return self._rows(
                "get_department_performance",
                compact,
                self._department_performance_summary(
                    department.name if department else "Phòng ban chưa xác định", rows
                ),
                scope=scope,
                date_from=arguments.date_from,
                date_to=arguments.date_to,
                scope_label=department.name if department else None,
                sources=["Chỉ số hiệu suất", "Nhân viên", "Phòng ban"],
            )

        rows = await self.performance_repository.aggregate_company_comparison(
            arguments.date_from, arguments.date_to
        )
        departments = {
            str(department.id): department.name
            for department in await self.performance_repository.list_departments()
        }
        compact = [
            {
                "Phòng ban": departments.get(str(row.get("_id")), "Phòng ban chưa xác định"),
                "Điểm hiệu suất trung bình": _round(row.get("average_performance_score")),
                "Điểm chất lượng trung bình": _round(row.get("average_quality_score")),
                "Số nhân viên": int(row.get("employee_count", 0)),
                "Số ngày có ghi nhận": int(row.get("metric_days", 0)),
            }
            for row in rows[: arguments.limit]
        ]
        return self._rows(
            "get_department_performance",
            compact,
            self._department_performance_summary("Toàn công ty", rows),
            scope=scope,
            date_from=arguments.date_from,
            date_to=arguments.date_to,
            scope_label="toàn công ty",
            sources=["Chỉ số hiệu suất", "Nhân viên", "Phòng ban"],
        )

    async def get_employee_performance(
        self, arguments: EmployeePerformanceToolInput, scope: ObjectId | None
    ) -> dict[str, Any]:
        if arguments.date_from and arguments.date_to and arguments.date_from > arguments.date_to:
            return self._empty(
                "get_employee_performance",
                scope=scope,
                date_from=arguments.date_from,
                date_to=arguments.date_to,
                sources=["Chỉ số hiệu suất", "Nhân viên"],
            )
        employees = await self.performance_repository.list_employees(scope)
        name = arguments.employee_name.casefold()
        matches = [employee for employee in employees if employee.full_name.casefold() == name]
        if len(matches) != 1:
            matches = [employee for employee in employees if name in employee.full_name.casefold()]
        if len(matches) != 1:
            return self._empty(
                "get_employee_performance",
                scope=scope,
                date_from=arguments.date_from,
                date_to=arguments.date_to,
                sources=["Chỉ số hiệu suất", "Nhân viên"],
            )
        employee = matches[0]
        trend = await self.performance_repository.aggregate_employee_trend(
            employee.id, arguments.date_from, arguments.date_to
        )
        compact = [
            {
                "Nhân viên": employee.full_name,
                "Ngày": _display(row.get("date")),
                "Số công việc hoàn thành": int(row.get("tasks_completed", 0)),
                "Điểm chất lượng công việc": _round(row.get("quality_score")),
                "Điểm hiệu suất": _round(row.get("performance_score")),
            }
            for row in trend[-arguments.limit :]
        ]
        return self._rows(
            "get_employee_performance",
            compact,
            scope=scope,
            date_from=arguments.date_from,
            date_to=arguments.date_to,
            sources=["Chỉ số hiệu suất", "Nhân viên"],
        )

    async def get_open_alerts(
        self, arguments: OpenAlertsToolInput, scope: ObjectId | None
    ) -> dict[str, Any]:
        alerts = await self.alert_repository.find_many(scope, status="open", alert_type=arguments.alert_type)
        if arguments.severity:
            alerts = [alert for alert in alerts if alert.severity.value == arguments.severity]
        rows = [
            {
                "Nhân viên": alert.employee_name,
                "Loại cảnh báo": alert.alert_type,
                "Mức độ": alert.severity.value,
                "Tiêu đề": alert.title,
                "Nội dung": alert.message,
                "Gợi ý xử lý": alert.suggested_action,
            }
            for alert in alerts[: arguments.limit]
        ]
        return self._rows(
            "get_open_alerts",
            rows,
            scope=scope,
            sources=["Cảnh báo"],
        )

    async def get_overloaded_employees(
        self, arguments: OverloadedEmployeesToolInput, scope: ObjectId | None
    ) -> dict[str, Any]:
        logs = await self.overload_repository.list_logs(scope)
        logs = [
            log
            for log in logs
            if self._date_in_range(log.date, arguments.date_from, arguments.date_to)
        ]
        employee_map = await self.overload_repository.find_employees(
            list({log.employee_id for log in logs})
        )
        rows = [
            {
                "Nhân viên": (
                    employee.full_name
                    if (employee := employee_map.get(log.employee_id)) is not None
                    else "Nhân viên chưa xác định"
                ),
                "Ngày": log.date.isoformat(),
                "Lý do cảnh báo": [reason.value for reason in log.trigger_reason],
                "Số công việc hoàn thành": log.tasks_completed,
                "Điểm chất lượng công việc": log.quality_score,
                "Chất lượng trung bình làm mốc": log.baseline_quality_avg,
            }
            for log in logs[: arguments.limit]
        ]
        return self._rows(
            "get_overloaded_employees",
            rows,
            scope=scope,
            date_from=arguments.date_from,
            date_to=arguments.date_to,
            sources=["Nhật ký quá tải", "Nhân viên"],
        )

    async def get_department_weekly_evaluation(
        self, arguments: DepartmentWeeklyEvaluationToolInput, scope: ObjectId | None
    ) -> dict[str, Any]:
        department_id = await self._department_id(arguments.department_name, scope)
        if scope is not None and department_id is None:
            return self._empty(
                "get_department_weekly_evaluation",
                scope=scope,
                sources=["Đánh giá phòng ban"],
            )
        evaluations, _ = await self.evaluation_repository.list_evaluations(
            department_id, page=1, page_size=arguments.limit
        )
        if arguments.week_start:
            evaluations = [item for item in evaluations if item.week_start == arguments.week_start]
        rows = [
            {
                "Phòng ban": item.department_name,
                "Tuần bắt đầu": item.week_start.isoformat(),
                "Tuần kết thúc": item.week_end.isoformat(),
                "Điểm thực hiện chỉ thị": item.directive_execution_score,
                "Điểm ổn định": item.stability_score,
                "Điểm đúng hạn": item.timeliness_score,
                "Điểm đánh giá tổng thể": item.overall_score,
                "Nhận xét": item.assessment_note,
                "Chỉ số bằng chứng": item.evidence_snapshot.stability.current.model_dump(),
            }
            for item in evaluations[: arguments.limit]
        ]
        return self._rows(
            "get_department_weekly_evaluation",
            rows,
            scope=scope,
            sources=["Đánh giá phòng ban"],
        )

    async def get_overdue_tasks(
        self, arguments: OverdueTasksToolInput, scope: ObjectId | None
    ) -> dict[str, Any]:
        department_id = await self._department_id(arguments.department_name, scope)
        if scope is not None and department_id is None:
            return self._empty(
                "get_overdue_tasks",
                scope=scope,
                sources=["Công việc", "Nhân viên"],
            )
        tasks = await self.task_repository.find_many(department_id, overdue_only=True)
        if scope is None:
            directed = await self.task_repository.list_directed_task_ids(
                ACTIVE_DIRECTIVE_STATUSES
            )
            tasks = [task for task in tasks if task.id not in directed]
        employees = {
            str(employee.id): employee.full_name
            for employee in await self.performance_repository.list_employees(department_id)
        }
        rows = [
            {
                "Công việc": task.title,
                "Nhân viên phụ trách": employees.get(str(task.employee_id), "Nhân viên chưa xác định"),
                "Mức ưu tiên": task.priority.value,
                "Hạn hoàn thành": task.due_date.isoformat(),
                "Trạng thái": task.status.value,
            }
            for task in tasks[: arguments.limit]
        ]
        return self._rows(
            "get_overdue_tasks",
            rows,
            scope=scope,
            sources=["Công việc", "Nhân viên"],
        )

    async def get_company_performance_summary(
        self, arguments: LeadershipDepartmentSummaryToolInput, scope: ObjectId | None
    ) -> dict[str, Any]:
        """Return company-level aggregates without employee-level rows."""

        if scope is not None:
            return self._empty(
                "get_company_performance_summary",
                scope=scope,
                date_from=arguments.date_from,
                date_to=arguments.date_to,
                sources=["Chỉ số hiệu suất", "Phòng ban"],
            )
        if arguments.date_from and arguments.date_to and arguments.date_from > arguments.date_to:
            return self._empty(
                "get_company_performance_summary",
                date_from=arguments.date_from,
                date_to=arguments.date_to,
                sources=["Chỉ số hiệu suất", "Phòng ban"],
            )

        period = self._period(arguments.date_from, arguments.date_to)
        if period is None:
            return self._empty(
                "get_company_performance_summary",
                sources=["Chỉ số hiệu suất", "Phòng ban"],
            )
        date_from, date_to = period
        requested_department = None
        if arguments.department_name:
            requested_department = await self._department_id(arguments.department_name, None)
            if requested_department is None:
                return self._empty(
                    "get_company_performance_summary",
                    date_from=date_from,
                    date_to=date_to,
                    sources=["Chỉ số hiệu suất", "Phòng ban"],
                )
        current_rows = (
            await self.performance_repository.aggregate_company_comparison(date_from, date_to)
            if requested_department is None
            else await self.performance_repository.aggregate_department_comparison(
                requested_department, date_from, date_to
            )
        )
        previous_end = date_from - timedelta(days=1)
        previous_start = previous_end - (date_to - date_from)
        previous_rows = (
            await self.performance_repository.aggregate_company_comparison(
                previous_start, previous_end
            )
            if requested_department is None
            else await self.performance_repository.aggregate_department_comparison(
                requested_department, previous_start, previous_end
            )
        )
        departments = {
            str(department.id): department.name
            for department in await self.performance_repository.list_departments()
        }
        scope_label = "toàn công ty"
        if requested_department is not None:
            scope_label = departments.get(str(requested_department), "Phòng ban")
            current_summary = self._department_performance_summary(scope_label, current_rows)
            previous_summary = self._department_performance_summary(scope_label, previous_rows)
            employees = await self.performance_repository.list_department_employees(
                requested_department
            )
            current_rows = [
                {
                    "_id": requested_department,
                    "average_performance_score": current_summary.get("Điểm hiệu suất trung bình")
                    if current_summary
                    else None,
                    "average_quality_score": current_summary.get("Điểm chất lượng trung bình")
                    if current_summary
                    else None,
                    "total_tasks": current_summary.get("Tổng công việc hoàn thành", 0)
                    if current_summary
                    else 0,
                    "employee_count": len(employees),
                }
            ] if current_summary else []
            previous_rows = [
                {
                    "_id": requested_department,
                    "average_performance_score": previous_summary.get("Điểm hiệu suất trung bình")
                    if previous_summary
                    else None,
                }
            ] if previous_summary else []
        previous_by_department = {str(row.get("_id")): row for row in previous_rows}
        summaries = []
        for row in current_rows[: arguments.limit]:
            department_id = str(row.get("_id"))
            score = _round(row.get("average_performance_score"))
            previous_score = _round(
                previous_by_department.get(department_id, {}).get("average_performance_score")
            )
            change = score - previous_score if score is not None and previous_score is not None else None
            trend = (
                "increasing"
                if change is not None and change > 0.01
                else "decreasing"
                if change is not None and change < -0.01
                else "stable"
                if change is not None
                else "insufficient_data"
            )
            summaries.append(
                {
                    "Phòng ban": departments.get(department_id, "Phòng ban chưa xác định"),
                    "Số nhân viên": int(row.get("employee_count") or 0),
                    "Điểm hiệu suất trung bình": score,
                    "Điểm chất lượng trung bình": _round(row.get("average_quality_score")),
                    "Số công việc hoàn thành": int(row.get("total_tasks") or 0),
                    "Xu hướng": trend,
                }
            )
        summary = {
            "Phạm vi": scope_label,
            "Số phòng ban có ghi nhận": len(summaries),
            "Từ ngày": date_from.isoformat(),
            "Đến ngày": date_to.isoformat(),
        } if summaries else None
        return self._rows(
            "get_company_performance_summary",
            summaries,
            summary,
            date_from=date_from,
            date_to=date_to,
            scope_label=scope_label,
            sources=["Chỉ số hiệu suất", "Phòng ban"],
        )

    async def compare_departments(
        self,
        arguments: LeadershipDepartmentSummaryToolInput,
        scope: ObjectId | None,
    ) -> dict[str, Any]:
        """Return the same trusted aggregates under an explicit comparison tool name."""

        result = await self.get_company_performance_summary(arguments, scope)
        result["cong_cu"] = "compare_departments"
        return result

    async def get_department_risk_summary(
        self, arguments: LeadershipDepartmentSummaryToolInput, scope: ObjectId | None
    ) -> dict[str, Any]:
        """Summarize open alerts and overdue work by department for Leadership."""

        if scope is not None:
            return self._empty(
                "get_department_risk_summary",
                scope=scope,
                date_from=arguments.date_from,
                date_to=arguments.date_to,
                sources=["Cảnh báo", "Công việc", "Nhật ký quá tải", "Phòng ban"],
            )
        if arguments.date_from and arguments.date_to and arguments.date_from > arguments.date_to:
            return self._empty(
                "get_department_risk_summary",
                sources=["Cảnh báo", "Công việc", "Nhật ký quá tải", "Phòng ban"],
            )

        start = arguments.date_from
        end = arguments.date_to or self.clock.today()
        requested_department = None
        if arguments.department_name:
            requested_department = await self._department_id(arguments.department_name, None)
            if requested_department is None:
                return self._empty(
                    "get_department_risk_summary",
                    sources=["Cảnh báo", "Công việc", "Nhật ký quá tải", "Phòng ban"],
                )
        alerts = await self.alert_repository.find_many(None, status="open")
        alerts = [
            alert
            for alert in alerts
            if any(self._date_in_range(value, start, end) for value in alert.detected_dates)
            and (requested_department is None or alert.department_id == requested_department)
        ]
        tasks = await self.task_repository.find_many(None, overdue_only=True)
        directed = await self.task_repository.list_directed_task_ids(ACTIVE_DIRECTIVE_STATUSES)
        tasks = [
            task
            for task in tasks
            if task.id not in directed
            and (requested_department is None or task.department_id == requested_department)
        ]
        logs = await self.overload_repository.list_logs(None)
        logs = [
            log
            for log in logs
            if self._date_in_range(log.date, start, end)
            and (requested_department is None or log.department_id == requested_department)
        ]
        departments = {
            str(department.id): department.name
            for department in await self.performance_repository.list_departments()
        }
        alert_by_department: dict[str, list[Any]] = {}
        for alert in alerts:
            alert_by_department.setdefault(str(alert.department_id), []).append(alert)
        task_by_department: dict[str, list[Any]] = {}
        for task in tasks:
            task_by_department.setdefault(str(task.department_id), []).append(task)
        log_by_department: dict[str, list[Any]] = {}
        for log in logs:
            log_by_department.setdefault(str(log.department_id), []).append(log)

        department_ids = set(alert_by_department) | set(task_by_department) | set(log_by_department)
        rows = []
        for department_id in sorted(department_ids):
            department_alerts = alert_by_department.get(department_id, [])
            department_tasks = task_by_department.get(department_id, [])
            department_logs = log_by_department.get(department_id, [])
            overdue_days = [max(0, (end - task.due_date).days) for task in department_tasks]
            unresolved_days = [
                max(0, (self.clock.today() - alert.created_at.date()).days)
                for alert in department_alerts
                if getattr(alert, "created_at", None) is not None
            ]
            severities = {alert.severity.value for alert in department_alerts}
            rows.append(
                {
                    "Phòng ban": departments.get(department_id, "Phòng ban chưa xác định"),
                    "Số cảnh báo đang mở": len(department_alerts),
                    "Số nhân viên liên quan": len({str(alert.employee_id) for alert in department_alerts}),
                    "Số cảnh báo quá tải": sum(
                        alert.alert_type == "overload" for alert in department_alerts
                    ),
                    "Số công việc quá hạn": len(department_tasks),
                    "Số ngày quá hạn lớn nhất": max(overdue_days, default=0),
                    "Số ngày chưa xử lý lớn nhất": max(unresolved_days, default=0),
                    "Số ghi nhận quá tải": len(department_logs),
                    "Mức độ cao nhất": "high" if "high" in severities else "medium" if severities else None,
                }
            )
        rows = rows[: arguments.limit]
        return self._rows(
            "get_department_risk_summary",
            rows,
            {"Phạm vi": "toàn công ty", "Số phòng ban có rủi ro": len(rows)} if rows else None,
            date_from=start,
            date_to=end,
            scope_label="toàn công ty",
            sources=["Cảnh báo", "Công việc", "Nhật ký quá tải", "Phòng ban"],
        )

    async def get_manager_evaluations(
        self, arguments: LeadershipEvaluationToolInput, scope: ObjectId | None
    ) -> dict[str, Any]:
        """Read weekly department evaluations used as Leadership evidence."""

        if scope is not None:
            return self._empty(
                "get_manager_evaluations",
                scope=scope,
                date_from=arguments.date_from,
                date_to=arguments.date_to,
                sources=["Đánh giá phòng ban"],
            )
        department_id = await self._department_id(arguments.department_name, None)
        evaluations, _ = await self.evaluation_repository.list_evaluations(
            department_id, page=1, page_size=arguments.limit
        )
        if arguments.date_from:
            evaluations = [item for item in evaluations if item.week_start >= arguments.date_from]
        if arguments.date_to:
            evaluations = [item for item in evaluations if item.week_start <= arguments.date_to]
        rows = [
            {
                "Quản lý": item.manager_name or "Chưa xác định",
                "Phòng ban": item.department_name,
                "Kỳ đánh giá": f"Tuần bắt đầu {item.week_start.isoformat()}",
                "Điểm hiệu suất trung bình phòng ban": item.evidence_snapshot.stability.current.average_performance_score,
                "Điểm đánh giá tổng thể": item.overall_score,
                "Điểm thực hiện chỉ thị": item.directive_execution_score,
                "Điểm ổn định": item.stability_score,
                "Điểm đúng hạn": item.timeliness_score,
                "Nhận xét": item.assessment_note,
            }
            for item in evaluations[: arguments.limit]
        ]
        return self._rows(
            "get_manager_evaluations",
            rows,
            {"Phạm vi": "toàn công ty", "Số kỳ đánh giá": len(rows)} if rows else None,
            scope_label="toàn công ty",
            sources=["Đánh giá phòng ban"],
        )

    async def get_cross_department_coordination_candidates(
        self,
        arguments: LeadershipCrossDepartmentCandidatesToolInput,
        scope: ObjectId | None,
    ) -> dict[str, Any]:
        """Build department-level coordination candidates from real workload data.

        Leadership sees only anonymized department aggregates.  Employee-level
        candidates remain behind the Manager coordination flow, and no score is
        invented by the model.
        """

        sources = ["Phòng ban", "Chỉ số hiệu suất", "Công việc", "Cảnh báo"]
        if scope is not None:
            return self._empty(
                "get_cross_department_coordination_candidates",
                scope=scope,
                date_from=arguments.date_from,
                date_to=arguments.date_to,
                sources=sources,
            )
        if arguments.date_from and arguments.date_to and arguments.date_from > arguments.date_to:
            return self._empty("get_cross_department_coordination_candidates", sources=sources)

        end = arguments.date_to or self.clock.today()
        start = arguments.date_from or (end - timedelta(days=6))
        departments = [item for item in await self.performance_repository.list_departments() if item.is_active]
        source_departments = departments
        if arguments.source_department_name:
            requested = arguments.source_department_name.casefold().strip()
            source_departments = [
                item for item in departments if item.name.casefold() == requested
            ]
            if not source_departments:
                return self._empty(
                    "get_cross_department_coordination_candidates",
                    date_from=start,
                    date_to=end,
                    sources=sources,
                )

        alerts = await self.alert_repository.find_many(None, status="open")
        alerts_by_department: dict[ObjectId, int] = {}
        for alert in alerts:
            if any(self._date_in_range(value, start, end) for value in alert.detected_dates):
                alerts_by_department[alert.department_id] = (
                    alerts_by_department.get(alert.department_id, 0) + 1
                )
        tasks = await self.task_repository.find_many(None, overdue_only=True)
        directed = await self.task_repository.list_directed_task_ids(ACTIVE_DIRECTIVE_STATUSES)
        overdue_by_department: dict[ObjectId, list[Any]] = {}
        for task in tasks:
            if task.id in directed or task.due_date > end:
                continue
            overdue_by_department.setdefault(task.department_id, []).append(task)

        rows: list[dict[str, Any]] = []
        for source in source_departments:
            source_tasks = overdue_by_department.get(source.id, [])
            if not source_tasks and not alerts_by_department.get(source.id):
                continue
            required_skills = {
                skill.strip().casefold()
                for task in source_tasks
                for skill in task.required_skills
                if skill.strip()
            }
            for target in departments:
                if target.id == source.id or not target.specialty:
                    continue
                if source.specialty != target.specialty:
                    continue
                employees = [
                    item
                    for item in await self.performance_repository.list_department_employees(target.id)
                    if item.is_active
                ]
                if not employees:
                    continue
                metrics = await self.performance_repository.find_department_metrics(
                    target.id, start, end
                )
                latest_by_employee: dict[ObjectId, Any] = {}
                for metric in metrics:
                    previous = latest_by_employee.get(metric.employee_id)
                    if previous is None or metric.date > previous.date:
                        latest_by_employee[metric.employee_id] = metric
                available = [
                    metric
                    for metric in latest_by_employee.values()
                    if metric.tasks_completed <= 2 and metric.quality_score >= 80
                ]
                available_count = len(available)
                if not available_count:
                    continue
                capacity_score = round(available_count / len(employees) * 100, 2)
                quality_values = [float(item.quality_score) for item in available]
                recent_quality = round(sum(quality_values) / len(quality_values), 2)
                target_tasks = await self.task_repository.find_department_tasks(target.id)
                open_tasks = [item for item in target_tasks if item.status.value != "done"]
                overdue_count = sum(item.due_date < end for item in open_tasks)
                reliability = round(
                    max(0.0, 100.0 - overdue_count / max(1, len(open_tasks)) * 100), 2
                ) if open_tasks else 70.0
                target_skills = {
                    skill.strip().casefold()
                    for employee in employees
                    for skill in employee.skills
                    if skill.strip()
                }
                skill_fit = (
                    round(len(required_skills & target_skills) / len(required_skills) * 100, 2)
                    if required_skills
                    else 70.0
                )
                fit_score = round(
                    capacity_score * 0.30
                    + recent_quality * 0.25
                    + reliability * 0.25
                    + skill_fit * 0.20
                )
                rows.append(
                    {
                        "Mã phòng ban nguồn": str(source.id),
                        "Phòng ban nguồn": source.name,
                        "Mã phòng ban hỗ trợ": str(target.id),
                        "Phòng ban hỗ trợ": target.name,
                        "Số người có thể nhận thêm việc": available_count,
                        "Khả năng nhận thêm việc": capacity_score,
                        "Mức khớp với yêu cầu công việc": skill_fit,
                        "Khả năng hoàn thành đúng hạn": reliability,
                        "Điểm chất lượng gần đây": recent_quality,
                        "Mức độ phù hợp": fit_score,
                        "Căn cứ": [
                            f"Có {available_count} người đang ở mức tải an toàn",
                            f"Điểm chất lượng gần đây trung bình {recent_quality:.1f}/100",
                            f"Khả năng hoàn thành đúng hạn {reliability:.1f}/100",
                        ],
                    }
                )

        rows.sort(key=lambda item: (-int(item["Mức độ phù hợp"]), item["Phòng ban hỗ trợ"]))
        rows = rows[: arguments.limit]
        return self._rows(
            "get_cross_department_coordination_candidates",
            rows,
            {"Phạm vi": "toàn công ty", "Số phương án đủ điều kiện": len(rows)} if rows else None,
            date_from=start,
            date_to=end,
            scope_label="toàn công ty",
            sources=sources,
        )

    async def get_overdue_work_summary(
        self, arguments: LeadershipDepartmentSummaryToolInput, scope: ObjectId | None
    ) -> dict[str, Any]:
        """Return overdue workload grouped by department, without assignee names."""

        if scope is not None:
            return self._empty(
                "get_overdue_work_summary",
                scope=scope,
                sources=["Công việc", "Phòng ban"],
            )
        requested_department = None
        if arguments.department_name:
            requested_department = await self._department_id(arguments.department_name, None)
            if requested_department is None:
                return self._empty(
                    "get_overdue_work_summary",
                    sources=["Công việc", "Phòng ban"],
                )
        tasks = await self.task_repository.find_many(None, overdue_only=True)
        directed = await self.task_repository.list_directed_task_ids(ACTIVE_DIRECTIVE_STATUSES)
        tasks = [
            task
            for task in tasks
            if requested_department is None or task.department_id == requested_department
        ]
        departments = {
            str(department.id): department.name
            for department in await self.performance_repository.list_departments()
        }
        grouped: dict[str, list[Any]] = {}
        for task in tasks:
            grouped.setdefault(str(task.department_id), []).append(task)
        rows = []
        today = self.clock.today()
        for department_id, department_tasks in sorted(grouped.items()):
            undirected_tasks = [task for task in department_tasks if task.id not in directed]
            rows.append(
                {
                    "Phòng ban": departments.get(department_id, "Phòng ban chưa xác định"),
                    "Số công việc quá hạn": len(department_tasks),
                    "Số công việc quá hạn chưa gửi chỉ thị": len(undirected_tasks),
                    "Số nhân viên liên quan": len(
                        {
                            str(getattr(task, "employee_id", "unknown"))
                            for task in department_tasks
                        }
                    ),
                    "Số việc ưu tiên cao": sum(task.priority.value == "high" for task in department_tasks),
                    "Số ngày quá hạn lớn nhất": max(
                        (max(0, (today - task.due_date).days) for task in department_tasks),
                        default=0,
                    ),
                }
            )
        total_overdue = sum(len(items) for items in grouped.values())
        total_undirected = sum(
            sum(task.id not in directed for task in items) for items in grouped.values()
        )
        rows = rows[: arguments.limit]
        return self._rows(
            "get_overdue_work_summary",
            rows,
            {
                "Phạm vi": "toàn công ty",
                "Số phòng ban có việc quá hạn": len(grouped),
                "Tổng số công việc quá hạn": total_overdue,
                "Tổng số công việc quá hạn chưa gửi chỉ thị": total_undirected,
            }
            if rows
            else None,
            scope_label="toàn công ty",
            sources=["Công việc", "Phòng ban"],
        )


def _round(value: Any) -> float | None:
    return round(float(value), 2) if value is not None else None


def _display(value: Any) -> str | None:
    return value.isoformat() if hasattr(value, "isoformat") else str(value) if value is not None else None


__all__ = ["AiDataToolService"]
