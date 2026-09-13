from datetime import datetime

from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field


class EmployeeDocument(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)

    id: ObjectId = Field(alias="_id")
    employee_code: str
    full_name: str
    email: str | None = None
    phone: str | None = None
    position: str
    skills: list[str] = Field(default_factory=list)
    department_id: ObjectId
    is_active: bool = True
    created_at: datetime
    updated_at: datetime


class EmployeeCreate(BaseModel):
    employee_code: str = Field(min_length=2, max_length=30)
    full_name: str = Field(min_length=1, max_length=120)
    email: str | None = Field(default=None, max_length=160)
    phone: str | None = Field(default=None, max_length=30)
    position: str = Field(min_length=1, max_length=120)
    skills: list[str] = Field(default_factory=list, max_length=30)
    department_id: str = Field(min_length=1)
    is_active: bool = True


class EmployeeUpdate(BaseModel):
    employee_code: str | None = Field(default=None, min_length=2, max_length=30)
    full_name: str | None = Field(default=None, min_length=1, max_length=120)
    email: str | None = Field(default=None, max_length=160)
    phone: str | None = Field(default=None, max_length=30)
    position: str | None = Field(default=None, min_length=1, max_length=120)
    skills: list[str] | None = Field(default=None, max_length=30)
    department_id: str | None = Field(default=None, min_length=1)
    is_active: bool | None = None


class EmployeeResponse(BaseModel):
    id: str
    employee_code: str
    full_name: str
    email: str | None = None
    phone: str | None = None
    position: str
    skills: list[str] = Field(default_factory=list)
    department_id: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
