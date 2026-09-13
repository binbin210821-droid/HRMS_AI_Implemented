from datetime import date as Date
from enum import Enum

from pydantic import BaseModel, Field


class TaskActionType(str, Enum):
    KEEP_AND_EXTEND = "keep_and_extend"
    REASSIGN_AND_RESET_DEADLINE = "reassign_and_reset_deadline"
    # Giữ để đọc proposal cũ; planner hiện tại không còn sinh loại này.
    REASSIGN_TASK = "reassign_task"
    REASSIGN_AND_EXTEND = "reassign_and_extend"
    MANUAL_REVIEW = "manual_review"


class TaskPlanningEmployee(BaseModel):
    employee_id: str
    employee_name: str
    employee_code: str
    open_task_count: int = Field(ge=0)
    overdue_task_count: int = Field(ge=0)
    average_performance_score: float | None = Field(default=None, ge=0, le=100)
    average_quality_score: float | None = Field(default=None, ge=0, le=100)
    performance_trend: float | None = None
    latest_tasks_completed: int | None = Field(default=None, ge=0)
    capacity_score: float = Field(ge=0, le=100)
    reliability_score: float = Field(ge=0, le=100)
    skill_fit_score: float = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=1)
    eligible: bool
    exclusion_reason: str | None = None


class TaskActionOption(BaseModel):
    option_id: str = Field(min_length=1, max_length=100)
    type: TaskActionType
    target_employee_id: str | None = None
    target_employee_name: str | None = None
    due_date: Date | None = None
    fit_score: int = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=1)
    rationale: str = Field(min_length=1, max_length=500)
    evidence: list[str] = Field(default_factory=list, max_length=6)
    requires_manual_review: bool = True


class OverdueTaskPlanningResponse(BaseModel):
    task_id: str
    summary: str
    options: list[TaskActionOption]
    data_as_of: Date
    plan_version: str = Field(min_length=1, max_length=128)


class TaskPlanningExplanationItem(BaseModel):
    option_id: str = Field(min_length=1, max_length=100)
    rationale: str = Field(min_length=1, max_length=500)


class AiTaskPlanningExplanation(BaseModel):
    summary: str = Field(min_length=1, max_length=500)
    explanations: list[TaskPlanningExplanationItem] = Field(default_factory=list, max_length=8)


__all__ = [
    "AiTaskPlanningExplanation",
    "OverdueTaskPlanningResponse",
    "TaskActionOption",
    "TaskActionType",
    "TaskPlanningEmployee",
    "TaskPlanningExplanationItem",
]
