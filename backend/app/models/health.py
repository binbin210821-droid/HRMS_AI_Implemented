from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: Literal["healthy"] = Field(description="Trạng thái hoạt động của hệ thống")
    timestamp: datetime = Field(description="Thời điểm kiểm tra theo múi giờ UTC")
