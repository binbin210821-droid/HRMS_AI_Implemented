from datetime import date as Date
from datetime import datetime
from enum import Enum

from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field


class OverloadTriggerReason(str, Enum):
    TASK_VOLUME = "task_volume"
    QUALITY_DROP = "quality_drop"


class OverloadLogDocument(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)

    id: ObjectId = Field(alias="_id")
    employee_id: ObjectId
    department_id: ObjectId
    date: Date
    trigger_reason: list[OverloadTriggerReason]
    tasks_completed: int
    quality_score: float
    baseline_quality_avg: float | None = None
    created_at: datetime


class WorkloadCandidateResponse(BaseModel):
    employee_id: str
    employee_code: str
    employee_name: str
    tasks_completed: int
    quality_score: float
    active_task_count: int = Field(default=0, ge=0)
    active_task_titles: list[str] = Field(default_factory=list)
    reserved_coordination_count: int = Field(default=0, ge=0)
    workload_count: int | None = Field(default=None, ge=0)
    available_capacity: int | None = Field(default=None, ge=0)


class OverloadLogResponse(BaseModel):
    id: str
    employee_id: str
    department_id: str
    employee_code: str
    employee_name: str
    date: Date
    trigger_reason: list[OverloadTriggerReason]
    trigger_reason_labels: list[str]
    tasks_completed: int
    quality_score: float
    baseline_quality_avg: float | None = None
    suggested_candidates: list[WorkloadCandidateResponse]
    created_at: datetime


class OverloadScanResponse(BaseModel):
    created_count: int
    logs: list[OverloadLogResponse]
