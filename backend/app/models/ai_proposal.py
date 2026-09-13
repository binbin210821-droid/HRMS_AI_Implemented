from typing import Annotated, Literal

from pydantic import BaseModel, Field


class ResolveAlertProposal(BaseModel):
    type: Literal["resolve_alert"] = "resolve_alert"
    resolution_note: str = Field(min_length=1, max_length=1000)
    rationale: str = Field(min_length=1, max_length=500)
    evidence: list[str] = Field(default_factory=list, max_length=5)
    priority: Literal["low", "medium", "high"] = "medium"
    data_as_of: str | None = Field(default=None, max_length=64)
    conditions: str | None = Field(default=None, max_length=500)


class ApplyCoordinationProposal(BaseModel):
    type: Literal["apply_coordination"] = "apply_coordination"
    target_employee_id: str
    tasks_to_transfer: int = Field(ge=1, le=2)
    note: str | None = Field(default=None, max_length=1000)
    rationale: str = Field(min_length=1, max_length=500)
    evidence: list[str] = Field(default_factory=list, max_length=5)
    priority: Literal["low", "medium", "high"] = "medium"
    data_as_of: str | None = Field(default=None, max_length=64)
    conditions: str | None = Field(default=None, max_length=500)


AiProposedAction = Annotated[
    ResolveAlertProposal | ApplyCoordinationProposal, Field(discriminator="type")
]


class AiAlertProposalResponse(BaseModel):
    alert_id: str
    summary: str
    actions: list[AiProposedAction]


class IssueDepartmentDirectiveProposal(BaseModel):
    type: Literal["issue_department_directive"] = "issue_department_directive"
    department_id: str = Field(min_length=1, max_length=100)
    department_name: str | None = Field(default=None, max_length=160)
    alert_type: Literal["all", "early_warning", "overload"] = "all"
    severity: Literal["all", "medium", "high"] = "all"
    note: str | None = Field(default=None, max_length=1000)
    rationale: str = Field(min_length=1, max_length=500)
    evidence: list[str] = Field(default_factory=list, max_length=5)
    priority: Literal["low", "medium", "high"] = "medium"


class LeadershipKeyFinding(BaseModel):
    department_id: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=200)
    evidence: list[str] = Field(default_factory=list, max_length=5)
    severity: Literal["low", "medium", "high"] = "medium"


class LeadershipFollowUpProposal(BaseModel):
    type: Literal[
        "request_manager_explanation",
        "monitor_department",
        "request_manager_re_evaluation",
    ]
    department_id: str = Field(min_length=1, max_length=100)
    monitoring_days: int | None = Field(default=None, ge=3, le=30)
    note: str | None = Field(default=None, max_length=1000)
    rationale: str = Field(min_length=1, max_length=500)
    evidence: list[str] = Field(default_factory=list, max_length=5)
    priority: Literal["low", "medium", "high"] = "medium"


class CrossDepartmentCoordinationProposal(BaseModel):
    type: Literal["cross_department_coordination"] = "cross_department_coordination"
    source_department_id: str = Field(min_length=1, max_length=100)
    target_department_id: str = Field(min_length=1, max_length=100)
    action: Literal["transfer_work", "extend_deadline", "reduce_scope", "keep_and_extend"] = (
        "transfer_work"
    )
    tasks_to_transfer: int = Field(default=1, ge=1, le=2)
    note: str | None = Field(default=None, max_length=1000)
    rationale: str = Field(min_length=1, max_length=500)
    evidence: list[str] = Field(default_factory=list, max_length=5)
    priority: Literal["low", "medium", "high"] = "medium"
    fit_score: int | None = Field(default=None, ge=0, le=100)
    source_department_name: str | None = Field(default=None, max_length=160)
    target_department_name: str | None = Field(default=None, max_length=160)
    available_employee_count: int | None = Field(default=None, ge=0)
    capacity_score: float | None = Field(default=None, ge=0, le=100)
    skill_fit_score: float | None = Field(default=None, ge=0, le=100)
    deadline_reliability_score: float | None = Field(default=None, ge=0, le=100)
    recent_quality_score: float | None = Field(default=None, ge=0, le=100)
    expected_impact: str | None = Field(default=None, max_length=500)
    risks: str | None = Field(default=None, max_length=500)


class ThresholdConfigProposal(BaseModel):
    type: Literal["propose_threshold_config"] = "propose_threshold_config"
    department_id: str | None = Field(default=None, max_length=100)
    consecutive_days: int = Field(ge=3, le=7)
    quality_drop_percent: float = Field(ge=1, le=100)
    rationale: str = Field(min_length=1, max_length=500)
    evidence: list[str] = Field(default_factory=list, max_length=5)
    priority: Literal["low", "medium", "high"] = "medium"


AiLeadershipProposedAction = Annotated[
    IssueDepartmentDirectiveProposal
    | CrossDepartmentCoordinationProposal
    | ThresholdConfigProposal
    | LeadershipFollowUpProposal,
    Field(discriminator="type"),
]


class AiLeadershipProposalResponse(BaseModel):
    summary: str
    key_findings: list[LeadershipKeyFinding] = Field(default_factory=list, max_length=20)
    actions: list[AiLeadershipProposedAction] = Field(default_factory=list, max_length=10)
    limitations: list[str] = Field(default_factory=list, max_length=10)
