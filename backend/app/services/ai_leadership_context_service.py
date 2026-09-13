from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from datetime import date as Date
from datetime import timedelta
from typing import Any, Literal

from app.models.ai_leadership import (
    LeadershipAiContext,
    LeadershipAiContextBuilder,
    LeadershipContextAccessError,
    LeadershipCrossDepartmentCandidate,
    LeadershipDepartmentSummary,
    LeadershipManagerEvaluationSummary,
    LeadershipOverdueWorkSummary,
    LeadershipRiskSummary,
)
from app.models.ai_tools import (
    LeadershipCrossDepartmentCandidatesToolInput,
    LeadershipDepartmentSummaryToolInput,
    LeadershipEvaluationToolInput,
)
from app.models.user import CurrentUser, UserRole
from app.services.ai_data_tool_service import AiDataToolService

logger = logging.getLogger(__name__)


class AiLeadershipContextService:
    """Assemble one bounded, company-level context for Leadership AI."""

    def __init__(self, data_service: AiDataToolService) -> None:
        self.data_service = data_service

    async def build_for_leadership(
        self,
        *,
        date_from: Date | None = None,
        date_to: Date | None = None,
        limit: int = 20,
    ) -> LeadershipAiContext:
        """Build the company context for an already authenticated Leadership flow."""

        return await self.build(
            CurrentUser(
                user_id="system-leadership-ai",
                username="leadership-ai",
                full_name="Trợ lý AI Leadership",
                role=UserRole.LEADERSHIP,
            ),
            date_from=date_from,
            date_to=date_to,
            limit=limit,
        )

    async def build(
        self,
        current_user: CurrentUser,
        *,
        date_from: Date | None = None,
        date_to: Date | None = None,
        limit: int = 20,
    ) -> LeadershipAiContext:
        if current_user.role != UserRole.LEADERSHIP:
            raise LeadershipContextAccessError(
                "Chỉ Lãnh đạo mới được tạo context AI ở phạm vi toàn công ty."
            )

        end = date_to or self.data_service.clock.today()
        start = date_from or (end - timedelta(days=6))
        if start > end:
            raise ValueError("Khoảng thời gian dữ liệu không hợp lệ")

        summary_arguments = LeadershipDepartmentSummaryToolInput(
            date_from=start,
            date_to=end,
            limit=limit,
        )
        evaluation_arguments = LeadershipEvaluationToolInput(
            date_from=start,
            date_to=end,
            limit=limit,
        )
        coordination_arguments = LeadershipCrossDepartmentCandidatesToolInput(
            date_from=start,
            date_to=end,
            limit=min(limit, 50),
        )
        limitations: list[str] = []
        sources: dict[str, Any] = {}

        await self._read_source(
            sources,
            limitations,
            "departments",
            lambda: self.data_service.performance_repository.list_departments(),
        )
        await self._read_source(
            sources,
            limitations,
            "performance",
            lambda: self.data_service.get_company_performance_summary(summary_arguments, None),
        )
        await self._read_source(
            sources,
            limitations,
            "risks",
            lambda: self.data_service.get_department_risk_summary(summary_arguments, None),
        )
        await self._read_source(
            sources,
            limitations,
            "evaluations",
            lambda: self.data_service.get_manager_evaluations(evaluation_arguments, None),
        )
        await self._read_source(
            sources,
            limitations,
            "overdue_work",
            lambda: self.data_service.get_overdue_work_summary(summary_arguments, None),
        )
        await self._read_source(
            sources,
            limitations,
            "coordination",
            lambda: self.data_service.get_cross_department_coordination_candidates(
                coordination_arguments, None
            ),
        )

        department_ids = {
            item.name.casefold(): str(item.id) for item in sources.get("departments", [])
        }
        departments: dict[str, LeadershipDepartmentSummary] = {}
        for row in self._rows(sources.get("performance")):
            name = self._text(row.get("Phòng ban"))
            department_id = department_ids.get(name.casefold())
            if not department_id:
                limitations.append(f"Bỏ qua phòng ban chưa ánh xạ được: {name}")
                continue
            departments[department_id] = LeadershipDepartmentSummary(
                department_id=department_id,
                department_name=name,
                employee_count=self._integer(row.get("Số nhân viên")),
                average_performance_score=self._number(row.get("Điểm hiệu suất trung bình")),
                average_quality_score=self._number(row.get("Điểm chất lượng trung bình")),
                completed_task_count=self._integer(row.get("Số công việc hoàn thành")),
                trend=self._trend(row.get("Xu hướng")),
            )

        risks: list[LeadershipRiskSummary] = []
        for row in self._rows(sources.get("risks")):
            risk_item = self._risk_summary(row, department_ids, limitations)
            if risk_item:
                risks.append(risk_item)

        overdue_work: list[LeadershipOverdueWorkSummary] = []
        for row in self._rows(sources.get("overdue_work")):
            overdue_item = self._overdue_summary(row, department_ids, limitations)
            if overdue_item:
                overdue_work.append(overdue_item)
                if overdue_item.department_id not in departments:
                    departments[overdue_item.department_id] = LeadershipDepartmentSummary(
                        department_id=overdue_item.department_id,
                        department_name=overdue_item.department_name,
                    )

        evaluations = [
            LeadershipManagerEvaluationSummary(
                manager_name=self._text(row.get("Quản lý"), "Chưa xác định"),
                department_name=self._text(row.get("Phòng ban")),
                period=self._text(row.get("Kỳ đánh giá")),
                department_average_performance=self._number(
                    row.get("Điểm hiệu suất trung bình phòng ban")
                ),
                overall_score=self._number(row.get("Điểm đánh giá tổng thể")),
                directive_execution_score=self._number(row.get("Điểm thực hiện chỉ thị")),
                stability_score=self._number(row.get("Điểm ổn định")),
                timeliness_score=self._number(row.get("Điểm đúng hạn")),
                assessment_note=self._optional_text(row.get("Nhận xét")),
            )
            for row in self._rows(sources.get("evaluations"))
        ]

        coordination_candidates = [
            candidate
            for row in self._rows(sources.get("coordination"))
            if (candidate := self._coordination_candidate(row, department_ids, limitations))
            is not None
        ]

        return LeadershipAiContextBuilder.build(
            current_user,
            departments=list(departments.values()),
            manager_evaluations=evaluations,
            risks=risks,
            overdue_work=overdue_work,
            coordination_candidates=coordination_candidates,
            limitations=limitations,
        )

    @staticmethod
    async def _read_source(
        target: dict[str, Any],
        limitations: list[str],
        name: str,
        reader: Callable[[], Awaitable[Any]],
    ) -> None:
        try:
            target[name] = await reader()
        except Exception:
            logger.exception("leadership_ai_context_source_failed", extra={"source": name})
            target[name] = {}
            limitations.append("Chưa đọc được đầy đủ một nguồn dữ liệu tổng hợp.")

    @staticmethod
    def _rows(value: Any) -> list[dict[str, Any]]:
        if not isinstance(value, dict) or not value.get("co_du_lieu"):
            return []
        rows = value.get("du_lieu")
        return rows if isinstance(rows, list) else []

    @staticmethod
    def _text(value: Any, default: str = "Phòng ban chưa xác định") -> str:
        return str(value).strip() if value is not None and str(value).strip() else default

    @staticmethod
    def _optional_text(value: Any) -> str | None:
        text = str(value).strip() if value is not None else ""
        return text or None

    @staticmethod
    def _number(value: Any) -> float | None:
        try:
            return round(float(value), 2) if value is not None else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _integer(value: Any) -> int:
        try:
            return max(0, int(value or 0))
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _trend(
        value: Any,
    ) -> Literal["increasing", "decreasing", "stable", "insufficient_data"]:
        if value == "increasing":
            return "increasing"
        if value == "decreasing":
            return "decreasing"
        if value == "stable":
            return "stable"
        return "insufficient_data"

    @classmethod
    def _risk_summary(
        cls,
        row: dict[str, Any],
        department_ids: dict[str, str],
        limitations: list[str],
    ) -> LeadershipRiskSummary | None:
        name = cls._text(row.get("Phòng ban"))
        department_id = department_ids.get(name.casefold())
        if not department_id:
            limitations.append(f"Bỏ qua phòng ban chưa ánh xạ được: {name}")
            return None
        severity = row.get("Mức độ cao nhất")
        return LeadershipRiskSummary(
            department_id=department_id,
            department_name=name,
            open_alert_count=cls._integer(row.get("Số cảnh báo đang mở")),
            affected_employee_count=cls._integer(row.get("Số nhân viên liên quan")),
            overload_alert_count=cls._integer(row.get("Số cảnh báo quá tải")),
            overdue_task_count=cls._integer(row.get("Số công việc quá hạn")),
            maximum_overdue_days=cls._integer(row.get("Số ngày quá hạn lớn nhất")),
            maximum_unresolved_days=cls._integer(row.get("Số ngày chưa xử lý lớn nhất")),
            highest_severity=severity if severity in {"low", "medium", "high"} else None,
        )

    @classmethod
    def _overdue_summary(
        cls,
        row: dict[str, Any],
        department_ids: dict[str, str],
        limitations: list[str],
    ) -> LeadershipOverdueWorkSummary | None:
        name = cls._text(row.get("Phòng ban"))
        department_id = department_ids.get(name.casefold())
        if not department_id:
            limitations.append(f"Bỏ qua phòng ban chưa ánh xạ được: {name}")
            return None
        return LeadershipOverdueWorkSummary(
            department_id=department_id,
            department_name=name,
            overdue_task_count=cls._integer(row.get("Số công việc quá hạn")),
            affected_employee_count=cls._integer(row.get("Số nhân viên liên quan")),
            high_priority_task_count=cls._integer(row.get("Số việc ưu tiên cao")),
            maximum_overdue_days=cls._integer(row.get("Số ngày quá hạn lớn nhất")),
        )

    @classmethod
    def _coordination_candidate(
        cls,
        row: dict[str, Any],
        department_ids: dict[str, str],
        limitations: list[str],
    ) -> LeadershipCrossDepartmentCandidate | None:
        source_name = cls._text(row.get("Phòng ban nguồn"))
        target_name = cls._text(row.get("Phòng ban hỗ trợ"))
        source_id = str(row.get("Mã phòng ban nguồn") or department_ids.get(source_name.casefold()) or "")
        target_id = str(row.get("Mã phòng ban hỗ trợ") or department_ids.get(target_name.casefold()) or "")
        if not source_id or not target_id:
            limitations.append("Bỏ qua phương án điều phối chưa ánh xạ được phòng ban.")
            return None
        evidence = row.get("Căn cứ")
        return LeadershipCrossDepartmentCandidate(
            source_department_id=source_id,
            source_department_name=source_name,
            target_department_id=target_id,
            target_department_name=target_name,
            available_employee_count=cls._integer(row.get("Số người có thể nhận thêm việc")),
            capacity_score=cls._number(row.get("Khả năng nhận thêm việc")) or 0,
            skill_fit_score=cls._number(row.get("Mức khớp với yêu cầu công việc")) or 0,
            deadline_reliability_score=cls._number(row.get("Khả năng hoàn thành đúng hạn")) or 0,
            recent_quality_score=cls._number(row.get("Điểm chất lượng gần đây")),
            fit_score=cls._integer(row.get("Mức độ phù hợp")),
            evidence=[str(item) for item in evidence[:5]] if isinstance(evidence, list) else [],
        )


__all__ = ["AiLeadershipContextService"]
