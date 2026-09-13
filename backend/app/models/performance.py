from datetime import date as Date
from datetime import datetime

from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field


class PerformanceMetricDocument(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)

    id: ObjectId = Field(alias="_id")
    employee_id: ObjectId
    date: Date
    tasks_completed: int
    quality_score: float
    reviewed_by: ObjectId
    performance_score: float
    note: str | None = None
    reviewed_task_count: int = 0
    evidence_task_count: int = 0
    total_review_task_count: int = 0
    created_at: datetime
    updated_at: datetime


class PerformanceMetricCreate(BaseModel):
    employee_id: str = Field(min_length=1)
    date: Date
    tasks_completed: int = Field(ge=0)
    quality_score: float = Field(ge=0, le=100)
    note: str | None = Field(default=None, max_length=1000)


class PerformanceMetricResponse(BaseModel):
    id: str
    employee_id: str
    date: Date
    tasks_completed: int
    quality_score: float
    reviewed_by: str
    performance_score: float
    note: str | None = None
    reviewed_task_count: int = 0
    evidence_task_count: int = 0
    total_review_task_count: int = 0
    created_at: datetime
    updated_at: datetime


class PerformanceTrendPoint(BaseModel):
    date: Date
    tasks_completed: int
    quality_score: float
    performance_score: float


class EmployeePerformanceAnalyticsResponse(BaseModel):
    employee_id: str
    employee_code: str
    full_name: str
    department_id: str
    department_name: str
    metrics: list[PerformanceTrendPoint]


class EmployeePerformanceComparison(BaseModel):
    employee_id: str
    employee_code: str
    full_name: str
    average_performance_score: float | None = None
    average_quality_score: float | None = None
    total_tasks: int = 0
    metric_days: int = 0


class DepartmentPerformanceAnalyticsResponse(BaseModel):
    department_id: str
    department_name: str
    employees: list[EmployeePerformanceComparison]


class WeeklyPerformanceTrendPoint(BaseModel):
    week_start: Date
    week_label: str
    performance: float
    quality: float | None = None


class DepartmentWeeklyPerformanceTrendResponse(BaseModel):
    department_id: str
    department_name: str
    weeks: list[WeeklyPerformanceTrendPoint]
    overall_average: float | None = None


class DepartmentPerformanceComparison(BaseModel):
    department_id: str
    department_name: str
    average_performance_score: float | None = None
    average_quality_score: float | None = None
    employee_count: int = 0
    metric_days: int = 0


class CompanyPerformanceAnalyticsResponse(BaseModel):
    departments: list[DepartmentPerformanceComparison]
