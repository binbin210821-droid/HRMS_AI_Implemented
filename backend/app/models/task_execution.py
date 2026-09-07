from datetime import date as Date
from datetime import datetime
from enum import Enum

from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field


class TaskExecutionOutcome(str, Enum):
    COMPLETED = "completed"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"


class EvidenceStatus(str, Enum):
    VERIFIED = "verified"
    MISSING_WITH_REASON = "missing_with_reason"


class TaskExecutionAttachment(BaseModel):
    attachment_id: str | None = None
    storage_key: str
    file_name: str
    content_type: str
    file_size: int = Field(ge=0)
    checksum: str


class ManagerTaskReview(BaseModel):
    score: float = Field(ge=0, le=100)
    note: str | None = None
    change_reason: str | None = Field(default=None, max_length=1000)
    evidence_status: EvidenceStatus
    missing_reason: str | None = None
    reviewed_by: ObjectId
    reviewed_at: datetime

    model_config = ConfigDict(arbitrary_types_allowed=True)


class TaskExecutionReportDocument(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)

    id: ObjectId = Field(alias="_id")
    task_id: ObjectId
    employee_id: ObjectId
    department_id: ObjectId
    work_date: Date
    result_summary: str | None = None
    progress_percent: int = Field(default=0, ge=0, le=100)
    outcome_status: TaskExecutionOutcome = TaskExecutionOutcome.IN_PROGRESS
    attachments: list[TaskExecutionAttachment] = Field(default_factory=list)
    submitted_by_employee_id: ObjectId | None = None
    submitted_at: datetime | None = None
    manager_review: ManagerTaskReview | None = None
    created_at: datetime
    updated_at: datetime


class DailyPerformanceReviewItem(BaseModel):
    task_id: str = Field(min_length=1)
    score: float = Field(ge=0, le=100)
    note: str | None = Field(default=None, max_length=1000)
    missing_reason: str | None = Field(default=None, max_length=1000)
    change_reason: str | None = Field(default=None, max_length=1000)


class DailyPerformanceReviewCreate(BaseModel):
    employee_id: str = Field(min_length=1)
    date: Date
    items: list[DailyPerformanceReviewItem] = Field(min_length=1)


class DailyReviewEmployeeResponse(BaseModel):
    id: str
    full_name: str
    employee_code: str


class DailyReviewAttachmentMetadata(BaseModel):
    file_name: str
    content_type: str
    file_size: int = Field(ge=0)
    checksum: str
    attachment_id: str


class DailyReviewAttachmentResponse(DailyReviewAttachmentMetadata):
    pass


class DailyReviewDownloadUrlResponse(BaseModel):
    url: str
    expires_at: datetime


class DailyReviewTaskResponse(BaseModel):
    id: str
    title: str
    description: str | None = None
    priority: str
    status: str
    due_date: Date
    subtask_count: int
    completed_at: datetime | None = None
    result_summary: str | None = None
    progress_percent: int = 0
    outcome_status: TaskExecutionOutcome = TaskExecutionOutcome.IN_PROGRESS
    attachments: list[DailyReviewAttachmentResponse] = Field(default_factory=list)
    evidence_status: EvidenceStatus | None = None
    score: float | None = None
    note: str | None = None
    missing_reason: str | None = None
    change_reason: str | None = None


class DailyPerformanceReviewSummary(BaseModel):
    tasks_completed: int = 0
    reviewed_task_count: int = 0
    missing_evidence_count: int = 0
    quality_score: float | None = None
    performance_score: float | None = None
    can_finalize: bool = False


class DailyPerformanceReviewResponse(BaseModel):
    employee: DailyReviewEmployeeResponse
    date: Date
    tasks: list[DailyReviewTaskResponse]
    summary: DailyPerformanceReviewSummary


__all__ = [
    "DailyPerformanceReviewCreate",
    "DailyPerformanceReviewItem",
    "DailyPerformanceReviewResponse",
    "DailyPerformanceReviewSummary",
    "DailyReviewAttachmentMetadata",
    "DailyReviewAttachmentResponse",
    "DailyReviewDownloadUrlResponse",
    "DailyReviewEmployeeResponse",
    "DailyReviewTaskResponse",
    "EvidenceStatus",
    "ManagerTaskReview",
    "TaskExecutionAttachment",
    "TaskExecutionOutcome",
    "TaskExecutionReportDocument",
]
