from datetime import date as Date
from datetime import datetime
from enum import Enum
from typing import Literal

from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field


class TaskStatus(str, Enum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"


class TaskPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class TaskDirectiveFocus(str, Enum):
    OVERDUE = "overdue"
    DUE_SOON = "due_soon"
    HIGH_PRIORITY_OPEN = "high_priority_open"
    AT_RISK = "at_risk"


class DepartmentTaskDirectiveStatus(str, Enum):
    PENDING = "pending"
    ACKNOWLEDGED = "acknowledged"
    SUBMITTED = "submitted"
    ACCEPTED = "accepted"
    NEEDS_REVISION = "needs_revision"


ACTIVE_DIRECTIVE_STATUSES: set[str] = {
    DepartmentTaskDirectiveStatus.PENDING.value,
    DepartmentTaskDirectiveStatus.ACKNOWLEDGED.value,
    DepartmentTaskDirectiveStatus.SUBMITTED.value,
    DepartmentTaskDirectiveStatus.NEEDS_REVISION.value,
}


class TaskDocument(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)

    id: ObjectId = Field(alias="_id")
    title: str
    description: str | None = None
    subtasks: list[str] = Field(default_factory=list)
    estimated_effort_hours: float | None = Field(default=None, gt=0, le=1000)
    required_skills: list[str] = Field(default_factory=list)
    employee_id: ObjectId
    department_id: ObjectId
    priority: TaskPriority = TaskPriority.MEDIUM
    status: TaskStatus = TaskStatus.TODO
    due_date: Date
    completed_at: datetime | None = None
    created_by: ObjectId
    created_at: datetime
    updated_at: datetime


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    subtasks: list[str] = Field(default_factory=list, max_length=20)
    estimated_effort_hours: float | None = Field(default=None, gt=0, le=1000)
    required_skills: list[str] = Field(default_factory=list, max_length=30)
    employee_id: str = Field(min_length=1)
    priority: TaskPriority = TaskPriority.MEDIUM
    status: TaskStatus = TaskStatus.TODO
    due_date: Date


class TaskUpdate(BaseModel):
    expected_updated_at: datetime | None = Field(default=None, exclude=True)
    planning_version: str | None = Field(default=None, min_length=1, max_length=128, exclude=True)
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    subtasks: list[str] | None = Field(default=None, max_length=20)
    estimated_effort_hours: float | None = Field(default=None, gt=0, le=1000)
    required_skills: list[str] | None = Field(default=None, max_length=30)
    employee_id: str | None = Field(default=None, min_length=1)
    priority: TaskPriority | None = None
    status: TaskStatus | None = None
    due_date: Date | None = None


class TaskResponse(BaseModel):
    id: str
    title: str
    description: str | None = None
    subtasks: list[str]
    estimated_effort_hours: float | None = None
    required_skills: list[str] = Field(default_factory=list)
    employee_id: str
    employee_name: str
    employee_code: str
    department_id: str
    priority: TaskPriority
    status: TaskStatus
    due_date: Date
    is_overdue: bool
    completed_at: datetime | None = None
    created_by: str
    created_at: datetime
    updated_at: datetime


class TaskCompletionTrendPoint(BaseModel):
    week_start: Date
    label: str
    completed_count: int


class DepartmentTaskOverviewResponse(BaseModel):
    department_id: str
    department_name: str
    department_code: str
    manager_name: str | None = None
    total_count: int
    open_count: int
    overdue_count: int
    due_soon_count: int
    high_priority_open_count: int
    completed_in_period_count: int
    oldest_overdue_date: Date | None = None
    undirected_at_risk_count: int
    # Chỉ nhóm công việc quá hạn mới đủ điều kiện phát hành chỉ thị.
    undirected_overdue_count: int = 0


class LeadershipTaskOverviewResponse(BaseModel):
    range: Literal["7d", "30d", "90d"]
    period_start: Date
    period_end: Date
    departments_with_tasks: int
    departments_need_attention: int
    departments_overdue: int
    departments_due_soon: int
    completion_trend: list[TaskCompletionTrendPoint]
    departments: list[DepartmentTaskOverviewResponse]


class DepartmentTaskPortfolioItemResponse(BaseModel):
    id: str
    title: str
    priority: TaskPriority
    status: TaskStatus
    due_date: Date
    is_overdue: bool
    subtask_count: int
    completed_at: datetime | None = None
    directive_id: str | None = None
    directive_status: str | None = None
    # Phân biệt chỉ thị đang hoạt động với lịch sử chỉ thị đã nghiệm thu.
    has_active_directive: bool = False


class DepartmentTaskPortfolioResponse(BaseModel):
    department_id: str
    department_name: str
    department_code: str
    manager_name: str | None = None
    range: Literal["7d", "30d", "90d"]
    period_start: Date
    period_end: Date
    overdue: list[DepartmentTaskPortfolioItemResponse]
    due_soon: list[DepartmentTaskPortfolioItemResponse]
    high_priority: list[DepartmentTaskPortfolioItemResponse]
    on_track: list[DepartmentTaskPortfolioItemResponse]
    completed_in_period: list[DepartmentTaskPortfolioItemResponse]


class DepartmentTaskDirectiveDocument(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)

    id: ObjectId = Field(alias="_id")
    target_department_id: ObjectId
    target_manager_id: ObjectId
    task_ids: list[ObjectId]
    focus: TaskDirectiveFocus
    selected_task_count: int
    note: str | None = None
    status: DepartmentTaskDirectiveStatus
    issued_by: ObjectId
    issued_at: datetime
    acknowledged_by: ObjectId | None = None
    acknowledged_at: datetime | None = None
    action_note: str | None = None
    commitment_date: Date | None = None
    completion_note: str | None = None
    submitted_by: ObjectId | None = None
    submitted_at: datetime | None = None
    accepted_by: ObjectId | None = None
    accepted_at: datetime | None = None
    acceptance_note: str | None = None
    revision_requested_by: ObjectId | None = None
    revision_requested_at: datetime | None = None
    revision_note: str | None = None


class DepartmentTaskDirectiveResponse(BaseModel):
    id: str
    target_department_id: str
    target_department_name: str
    target_manager_id: str
    target_manager_name: str | None = None
    task_ids: list[str]
    focus: TaskDirectiveFocus
    selected_task_count: int
    note: str | None = None
    status: DepartmentTaskDirectiveStatus
    issued_by: str
    issued_at: datetime
    acknowledged_by: str | None = None
    acknowledged_by_name: str | None = None
    acknowledged_at: datetime | None = None
    action_note: str | None = None
    commitment_date: Date | None = None
    completion_note: str | None = None
    submitted_by: str | None = None
    submitted_by_name: str | None = None
    submitted_at: datetime | None = None
    accepted_by: str | None = None
    accepted_by_name: str | None = None
    accepted_at: datetime | None = None
    acceptance_note: str | None = None
    revision_requested_by: str | None = None
    revision_requested_by_name: str | None = None
    revision_requested_at: datetime | None = None
    revision_note: str | None = None
    completed_item_count: int = 0
    total_item_count: int = 0
    progress_percent: int = 0


class IssueDepartmentTaskDirectiveRequest(BaseModel):
    focus: TaskDirectiveFocus
    note: str | None = Field(default=None, max_length=1000)
    task_ids: list[str] | None = Field(default=None, min_length=1, max_length=100)


class AcknowledgeDepartmentTaskDirectiveRequest(BaseModel):
    action_note: str = Field(min_length=1, max_length=1000)
    commitment_date: Date


class SubmitDepartmentTaskDirectiveRequest(BaseModel):
    completion_note: str | None = Field(default=None, max_length=1000)


class ReviewDepartmentTaskDirectiveRequest(BaseModel):
    note: str | None = Field(default=None, max_length=1000)


__all__ = [
    "ACTIVE_DIRECTIVE_STATUSES",
    "AcknowledgeDepartmentTaskDirectiveRequest",
    "DepartmentTaskDirectiveDocument",
    "DepartmentTaskDirectiveResponse",
    "DepartmentTaskDirectiveStatus",
    "DepartmentTaskOverviewResponse",
    "DepartmentTaskPortfolioItemResponse",
    "DepartmentTaskPortfolioResponse",
    "IssueDepartmentTaskDirectiveRequest",
    "LeadershipTaskOverviewResponse",
    "ReviewDepartmentTaskDirectiveRequest",
    "SubmitDepartmentTaskDirectiveRequest",
    "TaskCompletionTrendPoint",
    "TaskCreate",
    "TaskDirectiveFocus",
    "TaskDocument",
    "TaskPriority",
    "TaskResponse",
    "TaskStatus",
    "TaskUpdate",
]
