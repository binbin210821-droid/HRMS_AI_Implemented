from datetime import date as Date
from datetime import datetime
from enum import Enum

from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field


class AlertSeverity(str, Enum):
    MEDIUM = "medium"
    HIGH = "high"


class AlertStatus(str, Enum):
    OPEN = "open"
    RESOLVED = "resolved"


class AlertDocument(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)

    id: ObjectId = Field(alias="_id")
    alert_type: str
    severity: AlertSeverity
    status: AlertStatus
    employee_id: ObjectId
    department_id: ObjectId
    employee_code: str
    employee_name: str
    title: str
    message: str
    suggested_action: str
    detected_dates: list[Date]
    fingerprint: str
    resolution_note: str | None = None
    resolved_by: ObjectId | None = None
    resolved_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class AlertResponse(BaseModel):
    id: str
    alert_type: str
    severity: AlertSeverity
    status: AlertStatus
    employee_id: str
    department_id: str
    employee_code: str
    employee_name: str
    title: str
    message: str
    suggested_action: str
    detected_dates: list[Date]
    resolution_note: str | None = None
    resolved_by: str | None = None
    resolved_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class DepartmentAlertSummaryResponse(BaseModel):
    department_id: str
    department_name: str
    department_code: str | None = None
    total_count: int
    open_count: int
    resolved_count: int
    early_warning_count: int
    overload_count: int
    high_count: int
    latest_created_at: datetime | None = None
    # Chỉ dùng cho deep-link/truy vết; không hiển thị danh sách cá nhân trên UI Leadership.
    alert_ids: list[str] = Field(default_factory=list)


class AlertResolveRequest(BaseModel):
    resolution_note: str | None = Field(default=None, max_length=1000)
