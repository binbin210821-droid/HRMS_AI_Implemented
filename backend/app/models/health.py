from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: Literal["healthy"] = Field(description="Trạng thái hoạt động của hệ thống")
    timestamp: datetime = Field(description="Thời điểm kiểm tra theo múi giờ UTC")
    process_started_at: datetime | None = Field(
        default=None, description="Thời điểm process backend khởi động"
    )
    ai_provider: str | None = Field(default=None, description="Provider AI đang chọn")
    ai_model: str | None = Field(default=None, description="Model AI đang chọn")
    ai_provider_configured: bool | None = Field(
        default=None, description="Provider AI chính đã có đủ cấu hình hay chưa"
    )
    ai_fallback_provider: str | None = Field(
        default=None, description="Provider dự phòng đang chọn"
    )
    ai_fallback_configured: bool | None = Field(
        default=None, description="Provider dự phòng đã có đủ cấu hình hay chưa"
    )
