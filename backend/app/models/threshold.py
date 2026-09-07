from datetime import datetime
from enum import Enum

from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field


class ThresholdConfigStatus(str, Enum):
    PROPOSED = "proposed"
    APPROVED = "approved"


class ThresholdConfigDocument(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)

    id: ObjectId = Field(alias="_id")
    department_id: ObjectId | None = None
    consecutive_days: int
    quality_drop_percent: float
    status: ThresholdConfigStatus
    proposed_by: ObjectId
    approved_by: ObjectId | None = None
    created_at: datetime
    updated_at: datetime


class ThresholdConfigCreate(BaseModel):
    consecutive_days: int = Field(default=3, ge=3, le=7)
    quality_drop_percent: float = Field(default=20, ge=1, le=100)


class ThresholdConfigResponse(BaseModel):
    id: str
    department_id: str | None = None
    consecutive_days: int
    quality_drop_percent: float
    status: ThresholdConfigStatus
    proposed_by: str
    approved_by: str | None = None
    created_at: datetime
    updated_at: datetime
