from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.user import CurrentUser, UserRole


class _LeadershipModel(BaseModel):
    """Strict internal contract for company-level AI context."""

    model_config = ConfigDict(extra="forbid")


class LeadershipDepartmentSummary(_LeadershipModel):
    department_id: str = Field(min_length=1, max_length=100)
    department_name: str = Field(min_length=1, max_length=160)
    employee_count: int = Field(default=0, ge=0)
    average_performance_score: float | None = Field(default=None, ge=0, le=100)
    average_quality_score: float | None = Field(default=None, ge=0, le=100)
    completed_task_count: int = Field(default=0, ge=0)
    trend: Literal["increasing", "decreasing", "stable", "insufficient_data"] = (
        "insufficient_data"
    )


class LeadershipManagerEvaluationSummary(_LeadershipModel):
    manager_name: str = Field(min_length=1, max_length=160)
    department_name: str = Field(min_length=1, max_length=160)
    period: str = Field(min_length=1, max_length=30)
    department_average_performance: float | None = Field(default=None, ge=0, le=100)
    overall_score: float | None = Field(default=None, ge=0, le=100)
    directive_execution_score: float | None = Field(default=None, ge=0, le=100)
    stability_score: float | None = Field(default=None, ge=0, le=100)
    timeliness_score: float | None = Field(default=None, ge=0, le=100)
    assessment_note: str | None = Field(default=None, max_length=1000)


class LeadershipRiskSummary(_LeadershipModel):
    department_id: str = Field(min_length=1, max_length=100)
    department_name: str = Field(min_length=1, max_length=160)
    open_alert_count: int = Field(default=0, ge=0)
    affected_employee_count: int = Field(default=0, ge=0)
    overload_alert_count: int = Field(default=0, ge=0)
    overdue_task_count: int = Field(default=0, ge=0)
    maximum_overdue_days: int = Field(default=0, ge=0)
    maximum_unresolved_days: int = Field(default=0, ge=0)
    highest_severity: Literal["low", "medium", "high"] | None = None


class LeadershipOverdueWorkSummary(_LeadershipModel):
    department_id: str = Field(min_length=1, max_length=100)
    department_name: str = Field(min_length=1, max_length=160)
    overdue_task_count: int = Field(default=0, ge=0)
    affected_employee_count: int = Field(default=0, ge=0)
    high_priority_task_count: int = Field(default=0, ge=0)
    maximum_overdue_days: int = Field(default=0, ge=0)


class LeadershipCrossDepartmentCandidate(_LeadershipModel):
    """Anonymized department-level option for Leadership coordination review."""

    source_department_id: str = Field(min_length=1, max_length=100)
    source_department_name: str = Field(min_length=1, max_length=160)
    target_department_id: str = Field(min_length=1, max_length=100)
    target_department_name: str = Field(min_length=1, max_length=160)
    available_employee_count: int = Field(default=0, ge=0)
    capacity_score: float = Field(ge=0, le=100)
    skill_fit_score: float = Field(ge=0, le=100)
    deadline_reliability_score: float = Field(ge=0, le=100)
    recent_quality_score: float | None = Field(default=None, ge=0, le=100)
    fit_score: int = Field(ge=0, le=100)
    evidence: list[str] = Field(default_factory=list, max_length=5)


class LeadershipAiContext(_LeadershipModel):
    role: Literal["leadership"] = "leadership"
    scope: Literal["company"] = "company"
    departments: list[LeadershipDepartmentSummary] = Field(default_factory=list)
    manager_evaluations: list[LeadershipManagerEvaluationSummary] = Field(default_factory=list)
    risks: list[LeadershipRiskSummary] = Field(default_factory=list)
    overdue_work: list[LeadershipOverdueWorkSummary] = Field(default_factory=list)
    coordination_candidates: list[LeadershipCrossDepartmentCandidate] = Field(
        default_factory=list, max_length=50
    )
    limitations: list[str] = Field(default_factory=list, max_length=10)

    def to_prompt_data(self, *, include_internal_references: bool = False) -> dict[str, object]:
        """Return Vietnamese labels without exposing technical field names."""

        department_rows: list[dict[str, object]] = []
        for department_item in self.departments:
            row = {
                "Tên phòng ban": department_item.department_name,
                "Số nhân viên": department_item.employee_count,
                "Điểm hiệu suất trung bình": department_item.average_performance_score,
                "Điểm chất lượng trung bình": department_item.average_quality_score,
                "Số công việc hoàn thành": department_item.completed_task_count,
                "Xu hướng": department_item.trend,
            }
            if include_internal_references:
                row["Mã tham chiếu nội bộ"] = department_item.department_id
            department_rows.append(row)

        risk_rows: list[dict[str, object]] = []
        for risk_item in self.risks:
            row = {
                "Phòng ban": risk_item.department_name,
                "Số cảnh báo đang mở": risk_item.open_alert_count,
                "Số nhân viên liên quan": risk_item.affected_employee_count,
                "Số cảnh báo quá tải": risk_item.overload_alert_count,
                "Số công việc quá hạn": risk_item.overdue_task_count,
                "Số ngày quá hạn lớn nhất": risk_item.maximum_overdue_days,
                "Số ngày chưa xử lý lớn nhất": risk_item.maximum_unresolved_days,
                "Mức độ cao nhất": risk_item.highest_severity,
            }
            if include_internal_references:
                row["Mã tham chiếu nội bộ"] = risk_item.department_id
            risk_rows.append(row)

        overdue_rows: list[dict[str, object]] = []
        for overdue_item in self.overdue_work:
            row = {
                "Phòng ban": overdue_item.department_name,
                "Số công việc quá hạn": overdue_item.overdue_task_count,
                "Số nhân viên liên quan": overdue_item.affected_employee_count,
                "Số việc ưu tiên cao": overdue_item.high_priority_task_count,
                "Số ngày quá hạn lớn nhất": overdue_item.maximum_overdue_days,
            }
            if include_internal_references:
                row["Mã tham chiếu nội bộ"] = overdue_item.department_id
            overdue_rows.append(row)

        coordination_rows: list[dict[str, object]] = []
        for candidate in self.coordination_candidates:
            row = {
                "Phòng ban nguồn": candidate.source_department_name,
                "Phòng ban hỗ trợ": candidate.target_department_name,
                "Số người có thể nhận thêm việc": candidate.available_employee_count,
                "Khả năng nhận thêm việc": candidate.capacity_score,
                "Mức khớp với yêu cầu công việc": candidate.skill_fit_score,
                "Khả năng hoàn thành đúng hạn": candidate.deadline_reliability_score,
                "Điểm chất lượng gần đây": candidate.recent_quality_score,
                "Mức độ phù hợp": candidate.fit_score,
                "Căn cứ": candidate.evidence,
            }
            if include_internal_references:
                row["Mã phòng ban nguồn"] = candidate.source_department_id
                row["Mã phòng ban hỗ trợ"] = candidate.target_department_id
            coordination_rows.append(row)

        return {
            "Phạm vi": "toàn công ty",
            "Phòng ban": department_rows,
            "Đánh giá Quản lý": [
                {
                    "Quản lý": item.manager_name,
                    "Phòng ban": item.department_name,
                    "Kỳ đánh giá": item.period,
                    "Hiệu suất trung bình phòng ban": item.department_average_performance,
                    "Điểm tổng thể đánh giá phòng ban": item.overall_score,
                    "Điểm thực hiện chỉ thị": item.directive_execution_score,
                    "Điểm ổn định": item.stability_score,
                    "Điểm đúng hạn": item.timeliness_score,
                    "Nhận xét": item.assessment_note,
                }
                for item in self.manager_evaluations
            ],
            "Rủi ro phòng ban": risk_rows,
            "Công việc quá hạn theo phòng ban": overdue_rows,
            "Ứng viên điều phối liên phòng ban": coordination_rows,
            "Giới hạn dữ liệu": self.limitations,
        }


class LeadershipContextAccessError(PermissionError):
    """Raised when a non-Leadership user requests company-level AI context."""


class LeadershipAiContextBuilder:
    """Builds a strict, company-level context after a backend role check."""

    @staticmethod
    def build(
        current_user: CurrentUser,
        *,
        departments: list[LeadershipDepartmentSummary] | None = None,
        manager_evaluations: list[LeadershipManagerEvaluationSummary] | None = None,
        risks: list[LeadershipRiskSummary] | None = None,
        overdue_work: list[LeadershipOverdueWorkSummary] | None = None,
        coordination_candidates: list[LeadershipCrossDepartmentCandidate] | None = None,
        limitations: list[str] | None = None,
    ) -> LeadershipAiContext:
        if current_user.role != UserRole.LEADERSHIP:
            raise LeadershipContextAccessError(
                "Chỉ Lãnh đạo mới được tạo context AI ở phạm vi toàn công ty."
            )
        return LeadershipAiContext(
            departments=departments or [],
            manager_evaluations=manager_evaluations or [],
            risks=risks or [],
            overdue_work=overdue_work or [],
            coordination_candidates=coordination_candidates or [],
            limitations=limitations or [],
        )


__all__ = [
    "LeadershipAiContext",
    "LeadershipAiContextBuilder",
    "LeadershipContextAccessError",
    "LeadershipCrossDepartmentCandidate",
    "LeadershipDepartmentSummary",
    "LeadershipManagerEvaluationSummary",
    "LeadershipOverdueWorkSummary",
    "LeadershipRiskSummary",
]
