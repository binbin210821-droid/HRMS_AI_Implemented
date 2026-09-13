from datetime import date as Date
from datetime import datetime
from enum import Enum
from typing import Literal

from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field

from app.models.overload import WorkloadCandidateResponse


class CoordinationMode(str, Enum):
    SUGGESTED = "suggested"
    CUSTOMIZED = "customized"


class CoordinationPlanDocument(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)

    id: ObjectId = Field(alias="_id")
    alert_id: ObjectId
    department_id: ObjectId
    # Optional for backwards compatibility with plans created before cross-department directives.
    target_department_id: ObjectId | None = None
    source_employee_id: ObjectId
    target_employee_id: ObjectId
    alert_date: Date
    tasks_to_transfer: int
    mode: CoordinationMode
    note: str | None = None
    created_by: ObjectId
    created_at: datetime
    updated_at: datetime


class CoordinationPlanResponse(BaseModel):
    id: str
    alert_id: str
    department_id: str
    target_department_id: str
    source_employee_id: str
    target_employee_id: str
    target_employee_code: str
    target_employee_name: str
    alert_date: Date
    tasks_to_transfer: int
    mode: CoordinationMode
    note: str | None = None
    created_by: str
    created_at: datetime
    updated_at: datetime


class CoordinationSuggestionResponse(BaseModel):
    alert_id: str
    alert_type: str
    severity: str
    alert_date: Date
    source_employee_id: str
    source_employee_code: str
    source_employee_name: str
    candidates: list[WorkloadCandidateResponse]
    applied_plan: CoordinationPlanResponse | None = None


class ApplyCoordinationRequest(BaseModel):
    target_employee_id: str | None = None
    tasks_to_transfer: int | None = Field(default=None, ge=1, le=2)
    note: str | None = Field(default=None, max_length=1000)


class CoordinationDirectiveStatus(str, Enum):
    PENDING = "pending"
    FULFILLED = "fulfilled"


class CoordinationDirectiveDocument(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)

    id: ObjectId = Field(alias="_id")
    alert_id: ObjectId
    source_department_id: ObjectId
    target_department_id: ObjectId
    tasks_to_transfer: int | None = None
    note: str | None = None
    status: CoordinationDirectiveStatus
    issued_by: ObjectId
    issued_at: datetime
    fulfilled_plan_id: ObjectId | None = None
    fulfilled_by: ObjectId | None = None
    fulfilled_at: datetime | None = None


class CoordinationDirectiveResponse(BaseModel):
    id: str
    alert_id: str
    source_department_id: str
    source_department_name: str | None = None
    target_department_id: str
    target_department_name: str
    alert_title: str | None = None
    tasks_to_transfer: int | None = None
    note: str | None = None
    status: CoordinationDirectiveStatus
    issued_by: str
    issued_at: datetime
    fulfilled_plan_id: str | None = None
    fulfilled_by: str | None = None
    fulfilled_by_name: str | None = None
    fulfilled_at: datetime | None = None


class FulfillDirectiveRequest(BaseModel):
    target_employee_id: str
    tasks_to_transfer: int | None = Field(default=None, ge=1, le=2)


class DepartmentAlertDirectiveStatus(str, Enum):
    PENDING = "pending"
    ACKNOWLEDGED = "acknowledged"
    SUBMITTED = "submitted"
    ACCEPTED = "accepted"
    NEEDS_REVISION = "needs_revision"


class DepartmentAlertDirectiveDocument(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)

    id: ObjectId = Field(alias="_id")
    department_id: ObjectId
    target_department_id: ObjectId
    target_manager_id: ObjectId
    alert_ids: list[ObjectId]
    selected_alert_type: str
    selected_severity: str
    selected_alert_count: int
    selected_open_count: int
    total_count: int
    open_count: int
    resolved_count: int
    early_warning_count: int
    overload_count: int
    high_count: int
    note: str | None = None
    status: DepartmentAlertDirectiveStatus
    issued_by: ObjectId
    issued_at: datetime
    acknowledged_by: ObjectId | None = None
    acknowledged_at: datetime | None = None
    acknowledgement_note: str | None = None
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


class DepartmentAlertDirectiveResponse(BaseModel):
    id: str
    department_id: str
    department_name: str
    target_department_id: str
    target_manager_id: str
    target_manager_name: str | None = None
    alert_ids: list[str] = Field(default_factory=list)
    selected_alert_type: str
    selected_severity: str
    selected_alert_count: int
    selected_open_count: int
    total_count: int
    open_count: int
    resolved_count: int
    early_warning_count: int
    overload_count: int
    high_count: int
    note: str | None = None
    status: DepartmentAlertDirectiveStatus
    issued_by: str
    issued_at: datetime
    acknowledged_by: str | None = None
    acknowledged_by_name: str | None = None
    acknowledged_at: datetime | None = None
    acknowledgement_note: str | None = None
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


class IssueDepartmentAlertDirectiveRequest(BaseModel):
    alert_type: Literal["all", "early_warning", "overload"] = "all"
    severity: Literal["all", "medium", "high"] = "all"
    note: str | None = Field(default=None, max_length=1000)


class AcknowledgeDepartmentAlertDirectiveRequest(BaseModel):
    note: str | None = Field(default=None, max_length=1000)
    commitment_date: Date


class SubmitDepartmentAlertDirectiveRequest(BaseModel):
    completion_note: str | None = Field(default=None, max_length=1000)


class ReviewDepartmentAlertDirectiveRequest(BaseModel):
    note: str | None = Field(default=None, max_length=1000)


__all__ = [
    "AcknowledgeDepartmentAlertDirectiveRequest",
    "ApplyCoordinationRequest",
    "CoordinationDirectiveDocument",
    "CoordinationDirectiveResponse",
    "CoordinationDirectiveStatus",
    "CoordinationMode",
    "CoordinationPlanDocument",
    "CoordinationPlanResponse",
    "CoordinationSuggestionResponse",
    "DepartmentAlertDirectiveDocument",
    "DepartmentAlertDirectiveResponse",
    "DepartmentAlertDirectiveStatus",
    "FulfillDirectiveRequest",
    "IssueDepartmentAlertDirectiveRequest",
    "ReviewDepartmentAlertDirectiveRequest",
    "SubmitDepartmentAlertDirectiveRequest",
]
