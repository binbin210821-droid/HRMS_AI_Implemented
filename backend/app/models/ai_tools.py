from datetime import date as Date
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class RebalanceCandidatesToolInput(BaseModel):
    alert_id: str = Field(min_length=1, max_length=100)


class DataToolRangeInput(BaseModel):
    date_from: Date | None = None
    date_to: Date | None = None
    limit: int = Field(default=20, ge=1, le=50)


class DepartmentPerformanceToolInput(DataToolRangeInput):
    department_name: str | None = Field(default=None, max_length=120)


class EmployeePerformanceToolInput(DataToolRangeInput):
    employee_name: str = Field(min_length=1, max_length=120)


class PerformanceTrendToolInput(DataToolRangeInput):
    employee_name: str | None = Field(default=None, max_length=120)
    department_name: str | None = Field(default=None, max_length=120)


class ComparePerformancePeriodsToolInput(BaseModel):
    date_from: Date | None = None
    date_to: Date | None = None
    employee_name: str | None = Field(default=None, max_length=120)
    department_name: str | None = Field(default=None, max_length=120)


class ExplainAlertToolInput(BaseModel):
    alert_id: str | None = Field(default=None, max_length=100)
    employee_name: str | None = Field(default=None, max_length=120)
    limit: int = Field(default=5, ge=1, le=10)

    @model_validator(mode="after")
    def require_alert_reference(self):
        if not self.alert_id and not self.employee_name:
            raise ValueError("Cần mã cảnh báo hoặc tên nhân viên để giải thích cảnh báo")
        return self


class OpenAlertsToolInput(BaseModel):
    alert_type: str | None = Field(default=None, max_length=60)
    severity: Literal["medium", "high"] | None = None
    limit: int = Field(default=20, ge=1, le=50)


class OverloadedEmployeesToolInput(DataToolRangeInput):
    pass


class DepartmentWeeklyEvaluationToolInput(BaseModel):
    department_name: str | None = Field(default=None, max_length=120)
    week_start: Date | None = None
    limit: int = Field(default=5, ge=1, le=20)


class OverdueTasksToolInput(BaseModel):
    department_name: str | None = Field(default=None, max_length=120)
    limit: int = Field(default=20, ge=1, le=50)


class LeadershipEvaluationToolInput(DataToolRangeInput):
    department_name: str | None = Field(default=None, max_length=120)


class LeadershipDepartmentSummaryToolInput(DataToolRangeInput):
    department_name: str | None = Field(default=None, max_length=120)


class LeadershipCrossDepartmentCandidatesToolInput(DataToolRangeInput):
    source_department_name: str | None = Field(default=None, max_length=120)


class ApplyCoordinationToolInput(BaseModel):
    alert_id: str = Field(min_length=1, max_length=100)
    target_employee_id: str = Field(min_length=1, max_length=100)
    tasks_to_transfer: int = Field(ge=1, le=2)
    note: str | None = Field(default=None, max_length=1000)


class AiToolPreviewRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


class AiToolPreviewResponse(BaseModel):
    status: Literal["executed", "approval_required", "no_tool_call", "unavailable"]
    tool_name: str | None = None
    message: str
    data: dict[str, object] | None = None


class AiDataToolResponse(BaseModel):
    co_du_lieu: bool
    pham_vi: str
    ky_du_lieu: dict[str, str | None]
    tong_quan: dict[str, object] | None = None
    du_lieu: list[dict[str, object]]
    nguon_du_lieu: list[str]
    # Compatibility field retained for audit and existing internal callers.
    cong_cu: str


__all__ = [
    "AiDataToolResponse",
    "AiToolPreviewRequest",
    "AiToolPreviewResponse",
    "ApplyCoordinationToolInput",
    "ComparePerformancePeriodsToolInput",
    "DataToolRangeInput",
    "DepartmentPerformanceToolInput",
    "DepartmentWeeklyEvaluationToolInput",
    "EmployeePerformanceToolInput",
    "ExplainAlertToolInput",
    "LeadershipCrossDepartmentCandidatesToolInput",
    "LeadershipDepartmentSummaryToolInput",
    "LeadershipEvaluationToolInput",
    "OpenAlertsToolInput",
    "OverdueTasksToolInput",
    "OverloadedEmployeesToolInput",
    "PerformanceTrendToolInput",
    "RebalanceCandidatesToolInput",
]
