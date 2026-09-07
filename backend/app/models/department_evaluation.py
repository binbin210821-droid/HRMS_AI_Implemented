from datetime import date as Date
from datetime import datetime
from enum import Enum

from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field


class StabilityStatus(str, Enum):
    IMPROVING = "improving"
    STABLE = "stable"
    NEEDS_ATTENTION = "needs_attention"
    INSUFFICIENT_DATA = "insufficient_data"


class DirectiveTimingStatus(str, Enum):
    ON_TIME = "on_time"
    LATE = "late"
    OVERDUE = "overdue"
    NOT_DUE = "not_due"
    NO_COMMITMENT = "no_commitment"


class DepartmentWeeklyIndicators(BaseModel):
    average_performance_score: float | None = None
    average_quality_score: float | None = None
    performance_metric_days: int = 0
    performance_tasks_completed: int = 0
    completed_task_count: int = 0
    overdue_task_count: int = 0
    early_warning_count: int = 0
    overload_count: int = 0
    open_overload_count: int = 0
    resolved_alert_count: int = 0
    open_alert_count: int = 0


class DepartmentIndicatorDeltas(BaseModel):
    performance_score: float | None = None
    quality_score: float | None = None
    performance_metric_days: int = 0
    performance_tasks_completed: int = 0
    completed_tasks: int = 0
    overdue_tasks: int = 0
    early_warnings: int = 0
    overload_alerts: int = 0
    open_overload_alerts: int = 0
    resolved_alerts: int = 0
    open_alerts: int = 0


class DepartmentStabilityEvidence(BaseModel):
    status: StabilityStatus
    current: DepartmentWeeklyIndicators
    previous: DepartmentWeeklyIndicators
    deltas: DepartmentIndicatorDeltas


class DepartmentDirectiveEvidenceItem(BaseModel):
    directive_id: str
    source: str
    source_label: str
    status: str
    issued_at: datetime
    commitment_date: Date | None = None
    submitted_at: datetime | None = None
    accepted_at: datetime | None = None
    progress_percent: int = 0
    timing_status: DirectiveTimingStatus
    delay_hours: float = 0


class DepartmentDirectiveEvidence(BaseModel):
    total_count: int = 0
    pending_count: int = 0
    acknowledged_count: int = 0
    submitted_count: int = 0
    accepted_count: int = 0
    needs_revision_count: int = 0
    completed_count: int = 0
    completion_rate: float | None = None
    with_commitment_count: int = 0
    on_time_count: int = 0
    late_count: int = 0
    overdue_count: int = 0
    no_commitment_count: int = 0
    on_time_rate: float | None = None
    average_delay_hours: float | None = None
    maximum_delay_hours: float | None = None
    items: list[DepartmentDirectiveEvidenceItem] = Field(default_factory=list)


class DepartmentEvaluationEvidenceSnapshot(BaseModel):
    stability: DepartmentStabilityEvidence
    directives: DepartmentDirectiveEvidence


class DepartmentEvaluationAttachment(BaseModel):
    attachment_id: str
    storage_key: str
    file_name: str
    content_type: str
    file_size: int = Field(gt=0)
    checksum: str


class DepartmentEvaluationAttachmentResponse(BaseModel):
    """Metadata attachment; URL is issued only by the download endpoint."""

    attachment_id: str
    storage_key: str | None = None
    file_name: str
    content_type: str
    file_size: int = Field(gt=0)
    checksum: str


class DepartmentEvaluationAttachmentMetadata(BaseModel):
    attachment_id: str
    file_name: str
    content_type: str
    file_size: int = Field(gt=0)


class DepartmentWeeklyEvaluationDocument(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)

    id: ObjectId = Field(alias="_id")
    department_id: ObjectId
    department_name: str
    department_code: str
    manager_id: ObjectId | None = None
    manager_name: str | None = None
    week_start: Date
    week_end: Date
    evidence_cutoff_at: datetime
    directive_execution_score: float = Field(ge=0, le=100)
    stability_score: float = Field(ge=0, le=100)
    timeliness_score: float = Field(ge=0, le=100)
    overall_score: float = Field(ge=0, le=100)
    assessment_note: str | None = None
    evidence_snapshot: DepartmentEvaluationEvidenceSnapshot
    attachments: list[DepartmentEvaluationAttachment] = Field(default_factory=list)
    evaluated_by: ObjectId
    evaluated_at: datetime
    evaluation_delay_days: int = Field(ge=0)
    created_at: datetime
    updated_at: datetime


class DepartmentWeeklyEvaluationPayload(BaseModel):
    department_id: str = Field(min_length=1)
    week_start: Date
    directive_execution_score: float = Field(ge=0, le=100)
    stability_score: float = Field(ge=0, le=100)
    timeliness_score: float = Field(ge=0, le=100)
    assessment_note: str | None = Field(default=None, max_length=1000)
    attachment_session_ids: list[str] = Field(default_factory=list, max_length=5)


class DepartmentWeeklyEvaluationUpdatePayload(BaseModel):
    directive_execution_score: float = Field(ge=0, le=100)
    stability_score: float = Field(ge=0, le=100)
    timeliness_score: float = Field(ge=0, le=100)
    assessment_note: str | None = Field(default=None, max_length=1000)
    attachment_session_ids: list[str] = Field(default_factory=list, max_length=5)


class DepartmentWeeklyEvaluationResponse(BaseModel):
    id: str
    department_id: str
    department_name: str
    department_code: str
    manager_id: str | None = None
    manager_name: str | None = None
    week_start: Date
    week_end: Date
    evidence_cutoff_at: datetime
    directive_execution_score: float
    stability_score: float
    timeliness_score: float
    overall_score: float
    assessment_note: str | None = None
    evidence_snapshot: DepartmentEvaluationEvidenceSnapshot
    attachments: list[DepartmentEvaluationAttachmentMetadata] = Field(default_factory=list)
    evaluated_by: str
    evaluated_at: datetime
    evaluation_delay_days: int
    created_at: datetime
    updated_at: datetime


class DepartmentWeeklyEvaluationListItemResponse(BaseModel):
    id: str
    department_id: str
    department_name: str
    department_code: str
    week_start: Date
    week_end: Date
    directive_execution_score: float
    stability_score: float
    timeliness_score: float
    overall_score: float
    assessment_note: str | None = None
    attachment_count: int = 0
    attachments: list[DepartmentEvaluationAttachmentMetadata] = Field(default_factory=list)
    evaluated_at: datetime
    evaluation_delay_days: int


class DepartmentWeeklyEvaluationListResponse(BaseModel):
    items: list[DepartmentWeeklyEvaluationListItemResponse] = Field(default_factory=list)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    total: int = Field(ge=0)
    has_next: bool


class DepartmentEvaluationDownloadUrlResponse(BaseModel):
    url: str
    expires_at: datetime


class DepartmentWeeklyReviewResponse(BaseModel):
    department_id: str
    department_name: str
    department_code: str
    manager_id: str | None = None
    manager_name: str | None = None
    week_start: Date
    week_end: Date
    available_from: datetime
    can_evaluate: bool
    evaluation_delay_days: int
    evidence: DepartmentEvaluationEvidenceSnapshot
    existing_evaluation: DepartmentWeeklyEvaluationResponse | None = None


__all__ = [
    "DepartmentDirectiveEvidence",
    "DepartmentDirectiveEvidenceItem",
    "DepartmentEvaluationAttachment",
    "DepartmentEvaluationAttachmentMetadata",
    "DepartmentEvaluationAttachmentResponse",
    "DepartmentEvaluationDownloadUrlResponse",
    "DepartmentEvaluationEvidenceSnapshot",
    "DepartmentIndicatorDeltas",
    "DepartmentStabilityEvidence",
    "DepartmentWeeklyEvaluationDocument",
    "DepartmentWeeklyEvaluationListItemResponse",
    "DepartmentWeeklyEvaluationListResponse",
    "DepartmentWeeklyEvaluationPayload",
    "DepartmentWeeklyEvaluationResponse",
    "DepartmentWeeklyEvaluationUpdatePayload",
    "DepartmentWeeklyIndicators",
    "DepartmentWeeklyReviewResponse",
    "DirectiveTimingStatus",
    "StabilityStatus",
]
