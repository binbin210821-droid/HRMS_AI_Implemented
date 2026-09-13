from datetime import date, datetime, timezone
from unittest.mock import AsyncMock

import pytest
from bson import ObjectId
from fastapi import Response

from app.api.v1.departments import create_department_v1
from app.api.v1.employees import create_employee_v1
from app.api.v1.tasks import create_task_v1
from app.api.v1.thresholds import list_threshold_configs_v1
from app.core.pagination import ListQueryParams, Page
from app.models.department import DepartmentCreate, DepartmentResponse
from app.models.employee import EmployeeCreate, EmployeeResponse
from app.models.task import TaskCreate, TaskPriority, TaskResponse, TaskStatus
from app.models.user import CurrentUser, UserRole


def _user(role: UserRole) -> CurrentUser:
    return CurrentUser(
        user_id=str(ObjectId()),
        username="test.user",
        full_name="Người dùng kiểm thử",
        role=role,
        department_id=None,
    )


@pytest.mark.asyncio
async def test_department_create_v1_sets_location_without_changing_body() -> None:
    department_id = str(ObjectId())
    created = DepartmentResponse(
        id=department_id,
        name="Phòng kiểm thử",
        code="TEST",
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    service = AsyncMock()
    service.create.return_value = created
    response = Response()

    result = await create_department_v1(
        DepartmentCreate(name="Phòng kiểm thử", code="TEST"),
        response,
        _user(UserRole.LEADERSHIP),
        service,
    )

    assert result == created
    assert response.headers["Location"] == f"/api/v1/departments/{department_id}"
    service.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_employee_create_v1_sets_location_and_reuses_service() -> None:
    employee_id = str(ObjectId())
    department_id = str(ObjectId())
    created = EmployeeResponse(
        id=employee_id,
        employee_code="TEST-001",
        full_name="Nhân viên kiểm thử",
        position="Chuyên viên",
        department_id=department_id,
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    service = AsyncMock()
    service.create.return_value = created
    response = Response()
    request = EmployeeCreate(
        employee_code="TEST-001",
        full_name="Nhân viên kiểm thử",
        position="Chuyên viên",
        department_id=department_id,
    )

    result = await create_employee_v1(request, response, ObjectId(department_id), service)

    assert result == created
    assert response.headers["Location"] == f"/api/v1/employees/{employee_id}"
    service.create.assert_awaited_once_with(request, ObjectId(department_id))


@pytest.mark.asyncio
async def test_task_create_v1_sets_location_and_passes_creator_to_service() -> None:
    task_id = str(ObjectId())
    employee_id = str(ObjectId())
    department_id = str(ObjectId())
    user = _user(UserRole.MANAGER)
    created = TaskResponse(
        id=task_id,
        title="Công việc kiểm thử",
        subtasks=[],
        employee_id=employee_id,
        employee_name="Nhân viên kiểm thử",
        employee_code="TEST-001",
        department_id=department_id,
        priority=TaskPriority.MEDIUM,
        status=TaskStatus.TODO,
        due_date=date(2026, 1, 15),
        is_overdue=False,
        created_by=user.user_id,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    service = AsyncMock()
    service.create.return_value = created
    response = Response()
    request = TaskCreate(
        title="Công việc kiểm thử",
        employee_id=employee_id,
        due_date=date(2026, 1, 15),
    )

    result = await create_task_v1(request, response, ObjectId(department_id), user, service)

    assert result == created
    assert response.headers["Location"] == f"/api/v1/tasks/{task_id}"
    service.create.assert_awaited_once_with(request, ObjectId(department_id), user.user_id)


@pytest.mark.asyncio
async def test_threshold_list_v1_returns_page_contract() -> None:
    service = AsyncMock()
    service.list_page.return_value = Page(items=[], total=25)

    result = await list_threshold_configs_v1(
        ListQueryParams(page=2, page_size=10), None, _user(UserRole.LEADERSHIP), service
    )

    assert result.page == 2
    assert result.page_size == 10
    assert result.total == 25
    assert result.has_next is True
    service.list_page.assert_awaited_once_with(None, 10, 10)
