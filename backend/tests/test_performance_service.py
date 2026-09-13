from datetime import date, datetime, timezone

import pytest
from bson import ObjectId
from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError

from app.models.department import DepartmentDocument
from app.models.employee import EmployeeDocument
from app.models.performance import (
    PerformanceMetricCreate,
    PerformanceMetricDocument,
)
from app.services.performance_service import PerformanceService


def make_employee(department_id: ObjectId) -> EmployeeDocument:
    now = datetime.now(timezone.utc)
    return EmployeeDocument(
        _id=ObjectId(),
        employee_code="KD-NV-001",
        full_name="Nguyễn Văn A",
        position="Chuyên viên",
        department_id=department_id,
        created_at=now,
        updated_at=now,
    )


def make_metric(employee_id: ObjectId, reviewer_id: ObjectId) -> PerformanceMetricDocument:
    now = datetime.now(timezone.utc)
    return PerformanceMetricDocument(
        _id=ObjectId(),
        employee_id=employee_id,
        date=date(2026, 8, 28),
        tasks_completed=4,
        quality_score=80,
        reviewed_by=reviewer_id,
        performance_score=86,
        note="Đạt yêu cầu",
        created_at=now,
        updated_at=now,
    )


class FakePerformanceRepository:
    def __init__(self, employees: list[EmployeeDocument]) -> None:
        self.employees = {employee.id: employee for employee in employees}
        self.departments: dict[ObjectId, DepartmentDocument] = {}
        self.inserted: list[dict] = []
        self.duplicate = False
        self.last_find_many: tuple = ()
        self.weekly_average: dict = {"weeks": [], "overall_average": None}

    async def find_employee(self, employee_id: ObjectId) -> EmployeeDocument | None:
        return self.employees.get(employee_id)

    async def find_department(self, department_id: ObjectId) -> DepartmentDocument | None:
        return self.departments.get(department_id)

    async def list_department_employees(self, department_id: ObjectId) -> list[EmployeeDocument]:
        return [
            employee
            for employee in self.employees.values()
            if employee.department_id == department_id
        ]

    async def list_departments(self) -> list[DepartmentDocument]:
        return list(self.departments.values())

    async def aggregate_employee_trend(self, *_args) -> list[dict]:
        return []

    async def aggregate_department_comparison(self, *_args) -> list[dict]:
        return []

    async def aggregate_weekly_average(self, *_args) -> dict:
        return self.weekly_average

    async def aggregate_company_comparison(self, *_args) -> list[dict]:
        return []

    async def find_many(self, *args) -> list[PerformanceMetricDocument]:
        self.last_find_many = args
        return []

    async def insert(self, document: dict) -> PerformanceMetricDocument:
        if self.duplicate:
            raise DuplicateKeyError("duplicate performance metric")
        self.inserted.append(document)
        return PerformanceMetricDocument.model_validate(document)


def request_for(employee_id: ObjectId, **values) -> PerformanceMetricCreate:
    return PerformanceMetricCreate(
        employee_id=str(employee_id),
        date=values.get("date", date(2026, 8, 28)),
        tasks_completed=values.get("tasks_completed", 4),
        quality_score=values.get("quality_score", 80),
        note=values.get("note", "  Ghi chú  "),
    )


@pytest.mark.asyncio
async def test_manager_can_create_score_for_employee_in_own_department() -> None:
    department_id = ObjectId()
    employee = make_employee(department_id)
    reviewer_id = ObjectId()
    repository = FakePerformanceRepository([employee])
    service = PerformanceService(repository)

    response = await service.create_daily(request_for(employee.id), department_id, str(reviewer_id))

    assert response.performance_score == 86.0
    assert response.employee_id == str(employee.id)
    assert response.reviewed_by == str(reviewer_id)
    assert repository.inserted[0]["note"] == "Ghi chú"


@pytest.mark.asyncio
async def test_manager_cannot_create_score_for_employee_in_other_department() -> None:
    own_department = ObjectId()
    other_department = ObjectId()
    employee = make_employee(other_department)
    service = PerformanceService(FakePerformanceRepository([employee]))

    with pytest.raises(HTTPException) as forbidden:
        await service.create_daily(request_for(employee.id), own_department, str(ObjectId()))
    assert forbidden.value.status_code == 403


@pytest.mark.asyncio
async def test_create_rejects_missing_employee_and_duplicate_daily_metric() -> None:
    department_id = ObjectId()
    repository = FakePerformanceRepository([])
    service = PerformanceService(repository)
    with pytest.raises(HTTPException) as missing:
        await service.create_daily(request_for(ObjectId()), department_id, str(ObjectId()))
    assert missing.value.status_code == 404

    employee = make_employee(department_id)
    repository.employees[employee.id] = employee
    repository.duplicate = True
    with pytest.raises(HTTPException) as duplicate:
        await service.create_daily(request_for(employee.id), department_id, str(ObjectId()))
    assert duplicate.value.status_code == 409


@pytest.mark.asyncio
async def test_list_parses_filters_and_rejects_reversed_dates() -> None:
    service = PerformanceService(FakePerformanceRepository([]))
    own_department = ObjectId()
    employee_id = ObjectId()
    start = date(2026, 8, 1)
    end = date(2026, 8, 28)
    await service.list(None, str(employee_id), str(own_department), start, end)
    args = service.repository.last_find_many
    assert args[0] is None
    assert args[1] == employee_id
    assert args[2] == own_department
    assert args[3:] == (start, end)

    with pytest.raises(HTTPException) as invalid_range:
        await service.list(None, None, None, end, start)
    assert invalid_range.value.status_code == 422


def make_department(department_id: ObjectId) -> DepartmentDocument:
    now = datetime.now(timezone.utc)
    return DepartmentDocument(
        _id=department_id,
        name="Kinh doanh",
        code="KD",
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_employee_analytics_returns_empty_metrics_without_null_errors() -> None:
    department_id = ObjectId()
    employee = make_employee(department_id)
    repository = FakePerformanceRepository([employee])
    repository.departments[department_id] = make_department(department_id)

    response = await PerformanceService(repository).employee_analytics(None, str(employee.id))

    assert response.full_name == employee.full_name
    assert response.metrics == []


@pytest.mark.asyncio
async def test_analytics_scope_blocks_manager_from_other_employee_and_department() -> None:
    own_department = ObjectId()
    other_department = ObjectId()
    employee = make_employee(other_department)
    repository = FakePerformanceRepository([employee])
    repository.departments[other_department] = make_department(other_department)
    service = PerformanceService(repository)

    with pytest.raises(HTTPException) as employee_forbidden:
        await service.employee_analytics(own_department, str(employee.id))
    with pytest.raises(HTTPException) as department_forbidden:
        await service.department_analytics(own_department, str(other_department))

    assert employee_forbidden.value.status_code == 403
    assert department_forbidden.value.status_code == 403


@pytest.mark.asyncio
async def test_department_analytics_includes_employee_without_metrics() -> None:
    department_id = ObjectId()
    employee = make_employee(department_id)
    repository = FakePerformanceRepository([employee])
    repository.departments[department_id] = make_department(department_id)

    response = await PerformanceService(repository).department_analytics(
        department_id, str(department_id)
    )

    assert len(response.employees) == 1
    assert response.employees[0].average_performance_score is None
    assert response.employees[0].metric_days == 0


@pytest.mark.asyncio
async def test_department_weekly_trend_preserves_monday_week_and_overall_average() -> None:
    department_id = ObjectId()
    employee = make_employee(department_id)
    repository = FakePerformanceRepository([employee])
    repository.departments[department_id] = make_department(department_id)
    repository.weekly_average = {
        "weeks": [
            {
                "_id": datetime(2026, 9, 7, tzinfo=timezone.utc),
                "performance": 86.25,
                "quality": 82.34,
            }
        ],
        "overall_average": 86.25,
    }
    response = await PerformanceService(repository).department_weekly_trend(
        department_id, str(department_id), date(2026, 9, 1), date(2026, 9, 9)
    )

    assert response.department_id == str(department_id)
    assert response.weeks[0].week_start == date(2026, 9, 7)
    assert response.weeks[0].week_label == "07/09"
    assert response.weeks[0].performance == 86.3
    assert response.weeks[0].quality == 82.3
    assert response.overall_average == 86.25


@pytest.mark.asyncio
async def test_department_weekly_trend_keeps_missing_quality_as_null() -> None:
    department_id = ObjectId()
    employee = make_employee(department_id)
    repository = FakePerformanceRepository([employee])
    repository.departments[department_id] = make_department(department_id)
    repository.weekly_average = {
        "weeks": [
            {
                "_id": datetime(2026, 9, 7, tzinfo=timezone.utc),
                "performance": 86.25,
                "quality": None,
            }
        ],
        "overall_average": 86.25,
    }

    response = await PerformanceService(repository).department_weekly_trend(
        department_id, str(department_id), date(2026, 9, 1), date(2026, 9, 9)
    )

    assert response.weeks[0].performance == 86.3
    assert response.weeks[0].quality is None
