from datetime import datetime

from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field


class DepartmentDocument(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)

    id: ObjectId = Field(alias="_id")
    name: str
    code: str
    specialty: str | None = Field(default=None, max_length=100)
    description: str | None = None
    is_active: bool = True
    created_at: datetime
    updated_at: datetime


class DepartmentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    code: str = Field(min_length=2, max_length=20)
    specialty: str | None = Field(default=None, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    is_active: bool = True


class DepartmentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    code: str | None = Field(default=None, min_length=2, max_length=20)
    specialty: str | None = Field(default=None, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    is_active: bool | None = None


class DepartmentResponse(BaseModel):
    id: str
    name: str
    code: str
    specialty: str | None = None
    description: str | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime
