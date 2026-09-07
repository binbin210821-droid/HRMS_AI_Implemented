from datetime import date as Date
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class AttachmentPurpose(str, Enum):
    DEPARTMENT_EVALUATION = "department_evaluation"
    TASK_EXECUTION_REPORT = "task_execution_report"


class UploadSessionStatus(str, Enum):
    PENDING = "pending"
    UPLOADED = "uploaded"
    COMMITTED = "committed"
    EXPIRED = "expired"
    FAILED = "failed"
    CANCELLED = "cancelled"


class UploadSessionContext(BaseModel):
    purpose: AttachmentPurpose
    department_id: str = Field(min_length=1)
    target_id: str | None = None
    week_start: Date | None = None
    task_id: str | None = None
    work_date: Date | None = None


class CreateUploadSessionRequest(BaseModel):
    purpose: AttachmentPurpose
    department_id: str = Field(min_length=1)
    target_id: str | None = None
    week_start: Date | None = None
    task_id: str | None = None
    work_date: Date | None = None
    file_name: str = Field(min_length=1, max_length=255)
    content_type: str = Field(min_length=1, max_length=150)
    file_size: int = Field(gt=0)
    checksum: str = Field(pattern=r"^[0-9a-fA-F]{64}$")


class UploadSessionResponse(BaseModel):
    id: str
    upload_url: str
    expires_at: datetime
    required_headers: dict[str, str]


class CompleteUploadSessionResponse(BaseModel):
    id: str
    status: UploadSessionStatus
    file_name: str
    content_type: str
    file_size: int


class UploadSessionDocument(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(alias="_id")
    owner_id: str
    department_id: str
    purpose: AttachmentPurpose
    target_id: str | None = None
    week_start: Date | None = None
    task_id: str | None = None
    work_date: Date | None = None
    file_name: str
    content_type: str
    file_size: int
    checksum: str
    generated_storage_key: str
    status: UploadSessionStatus
    expires_at: datetime
    created_at: datetime
    updated_at: datetime


__all__ = [
    "AttachmentPurpose",
    "CompleteUploadSessionResponse",
    "CreateUploadSessionRequest",
    "UploadSessionContext",
    "UploadSessionDocument",
    "UploadSessionResponse",
    "UploadSessionStatus",
]
