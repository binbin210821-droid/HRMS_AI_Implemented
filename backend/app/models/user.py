from datetime import datetime
from enum import Enum

from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field


class UserRole(str, Enum):
    MANAGER = "manager"
    LEADERSHIP = "leadership"


class UserDocument(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)

    id: ObjectId = Field(alias="_id")
    username: str
    password_hash: str
    full_name: str
    role: UserRole
    department_id: ObjectId | None = None
    is_active: bool = True
    created_at: datetime


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str = Field(
        ...,
        description="Deprecated: chỉ giữ tạm cho client tương thích Bearer",
        json_schema_extra={"deprecated": True},
    )
    token_type: str = "bearer"


class CurrentUser(BaseModel):
    user_id: str
    username: str
    full_name: str
    role: UserRole
    department_id: str | None = None
