from datetime import date as Date
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

AttentionSource = Literal["alert", "task"]
AttentionCategory = Literal["early_warning", "overload", "overdue_task"]


class AttentionItemResponse(BaseModel):
    id: str
    source: AttentionSource
    category: AttentionCategory
    title: str
    message: str
    employee_id: str | None = None
    employee_name: str
    employee_code: str | None = None
    department_id: str
    department_name: str | None = None
    severity: str | None = None
    created_at: datetime
    due_date: Date | None = None
    days_overdue: int | None = None
    overdue_task_count: int | None = None


class AttentionEmployeeDetailResponse(BaseModel):
    employee_id: str
    employee_name: str
    employee_code: str | None = None
    early_warning_count: int = 0
    overload_count: int = 0
    overdue_task_count: int = 0


class DepartmentAttentionDetailResponse(BaseModel):
    department_id: str
    department_name: str
    early_warning_employee_count: int
    overload_employee_count: int
    overdue_employee_count: int
    overdue_task_count: int
    employees: list[AttentionEmployeeDetailResponse]
    first_item_id: str | None = None
    first_item_source: AttentionSource | None = None


class AttentionSummaryResponse(BaseModel):
    total: int
    early_warning_count: int
    overload_count: int
    overdue_task_count: int
    overdue_task_total: int
    overloaded_department_count: int
    early_warning_department_count: int
    overdue_department_count: int
    department_details: list[DepartmentAttentionDetailResponse] = Field(default_factory=list)
    items: list[AttentionItemResponse]
    generated_at: datetime


__all__ = [
    "AttentionEmployeeDetailResponse",
    "AttentionItemResponse",
    "AttentionSummaryResponse",
    "DepartmentAttentionDetailResponse",
]
