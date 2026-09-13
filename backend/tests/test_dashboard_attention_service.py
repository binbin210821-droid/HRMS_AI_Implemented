from datetime import date, datetime, timedelta, timezone

import pytest
from bson import ObjectId

from app.models.alert import AlertDocument, AlertSeverity, AlertStatus
from app.models.department import DepartmentDocument
from app.models.employee import EmployeeDocument
from app.models.task import TaskDocument, TaskStatus
from app.services.dashboard_attention_service import DashboardAttentionService


def make_alert(
    department_id: ObjectId,
    alert_type: str,
    severity: AlertSeverity,
    employee_id: ObjectId,
    created_at: datetime,
) -> AlertDocument:
    return AlertDocument(
        _id=ObjectId(),
        alert_type=alert_type,
        severity=severity,
        status=AlertStatus.OPEN,
        employee_id=employee_id,
        department_id=department_id,
        employee_code="KD-001",
        employee_name="Nguyễn Văn A",
        title="Cảnh báo hiệu suất",
        message="Cần theo dõi.",
        suggested_action="Kiểm tra và xử lý.",
        detected_dates=[created_at.date()],
        fingerprint=str(ObjectId()),
        created_at=created_at,
        updated_at=created_at,
    )


def make_task(department_id: ObjectId, employee_id: ObjectId) -> TaskDocument:
    now = datetime.now(timezone.utc)
    return TaskDocument(
        _id=ObjectId(),
        title="Công việc quá hạn",
        employee_id=employee_id,
        department_id=department_id,
        priority="high",
        status=TaskStatus.IN_PROGRESS,
        due_date=date.today() - timedelta(days=3),
        created_by=ObjectId(),
        created_at=now,
        updated_at=now,
    )


class FakeAlertRepository:
    def __init__(self, alerts: list[AlertDocument]) -> None:
        self.alerts = alerts
        self.calls: list[tuple[ObjectId | None, str | None, str | None]] = []

    async def find_many(
        self,
        scope: ObjectId | None,
        status: str | None = None,
        alert_type: str | None = None,
    ) -> list[AlertDocument]:
        self.calls.append((scope, status, alert_type))
        return self.alerts


class FakeTaskRepository:
    def __init__(self, tasks: list[TaskDocument]) -> None:
        self.tasks = tasks
        self.calls: list[tuple[ObjectId | None, bool]] = []
        self.directed_task_ids: set[ObjectId] = set()

    async def find_many(
        self,
        scope: ObjectId | None,
        employee_id: ObjectId | None = None,
        status: str | None = None,
        overdue_only: bool = False,
    ) -> list[TaskDocument]:
        self.calls.append((scope, overdue_only))
        return self.tasks

    async def list_directed_task_ids(
        self, statuses: set[str] | None = None
    ) -> set[ObjectId]:
        return self.directed_task_ids


class FakeEmployeeRepository:
    def __init__(self, employees: list[EmployeeDocument]) -> None:
        self.employees = employees
        self.scopes: list[ObjectId | None] = []

    async def find_many(self, scope: ObjectId | None) -> list[EmployeeDocument]:
        self.scopes.append(scope)
        return self.employees


class FakeDepartmentRepository:
    def __init__(self, departments: list[DepartmentDocument]) -> None:
        self.departments = departments
        self.scopes: list[ObjectId | None] = []

    async def find_many(self, scope: ObjectId | None) -> list[DepartmentDocument]:
        self.scopes.append(scope)
        return self.departments


class FakeDepartmentDirectiveRepository:
    def __init__(self, alert_ids: set[ObjectId] | None = None) -> None:
        self.alert_ids = alert_ids or set()
        self.scopes: list[ObjectId | None] = []

    async def list_alert_ids(self, scope: ObjectId | None) -> set[ObjectId]:
        self.scopes.append(scope)
        return self.alert_ids


def make_dependencies():
    department_id = ObjectId()
    employee_id = ObjectId()
    now = datetime.now(timezone.utc)
    employee = EmployeeDocument(
        _id=employee_id,
        employee_code="KD-001",
        full_name="Nguyễn Văn A",
        position="Chuyên viên",
        department_id=department_id,
        created_at=now,
        updated_at=now,
    )
    department = DepartmentDocument(
        _id=department_id,
        name="Kinh doanh",
        code="KD",
        created_at=now,
        updated_at=now,
    )
    alerts = [
        make_alert(department_id, "early_warning", AlertSeverity.MEDIUM, employee_id, now),
        make_alert(
            department_id,
            "overload",
            AlertSeverity.HIGH,
            employee_id,
            now + timedelta(minutes=1),
        ),
    ]
    alert_repository = FakeAlertRepository(alerts)
    task_repository = FakeTaskRepository([make_task(department_id, employee_id)])
    employee_repository = FakeEmployeeRepository([employee])
    department_repository = FakeDepartmentRepository([department])
    directive_repository = FakeDepartmentDirectiveRepository()
    service = DashboardAttentionService(
        alert_repository,
        task_repository,
        employee_repository,
        department_repository,
        directive_repository,
    )
    return (
        service,
        department_id,
        alert_repository,
        task_repository,
        employee_repository,
        department_repository,
        directive_repository,
    )


@pytest.mark.asyncio
async def test_summary_counts_categories_and_prioritizes_action_items() -> None:
    (
        service,
        department_id,
        alert_repository,
        task_repository,
        employee_repository,
        department_repository,
        directive_repository,
    ) = make_dependencies()

    summary = await service.get_summary(department_id)

    assert summary.total == 3
    assert summary.early_warning_count == 1
    assert summary.overload_count == 1
    assert summary.overdue_task_count == 1
    assert summary.overdue_task_total == 1
    assert summary.overloaded_department_count == 1
    assert [item.category for item in summary.items] == [
        "overload",
        "overdue_task",
        "early_warning",
    ]
    assert summary.items[1].department_name == "Kinh doanh"
    assert summary.items[1].employee_name == "Nguyễn Văn A"
    assert summary.items[1].days_overdue == 3
    assert alert_repository.calls == [(department_id, "open", None)]
    assert task_repository.calls == [(department_id, True)]
    assert employee_repository.scopes == [department_id]
    assert department_repository.scopes == [department_id]
    assert directive_repository.scopes == [department_id]


@pytest.mark.asyncio
async def test_leadership_summary_uses_company_scope() -> None:
    (
        service,
        _,
        alert_repository,
        task_repository,
        employee_repository,
        department_repository,
        directive_repository,
    ) = make_dependencies()
    alert_repository.alerts.append(
        make_alert(
            alert_repository.alerts[0].department_id,
            "overload",
            AlertSeverity.HIGH,
            alert_repository.alerts[0].employee_id,
            alert_repository.alerts[-1].created_at + timedelta(minutes=1),
        )
    )

    summary = await service.get_summary(None)

    assert summary.total == 3
    assert summary.overload_count == 2
    assert summary.early_warning_department_count == 1
    assert summary.overloaded_department_count == 1
    assert summary.overdue_department_count == 1
    assert summary.department_details[0].department_name == "Kinh doanh"
    assert summary.department_details[0].overdue_task_count == 1
    assert summary.department_details[0].overdue_employee_count == 1
    assert summary.department_details[0].employees[0].employee_name == "Nguyễn Văn A"
    assert summary.department_details[0].employees[0].early_warning_count == 1
    assert summary.department_details[0].employees[0].overload_count == 2
    assert summary.department_details[0].employees[0].overdue_task_count == 1
    assert alert_repository.calls[0][0] is None
    assert task_repository.calls[0][0] is None
    assert employee_repository.scopes == [None]
    assert department_repository.scopes == [None]
    assert directive_repository.scopes == [None]


@pytest.mark.asyncio
async def test_summary_excludes_directed_alerts_and_groups_overdue_tasks_by_employee() -> None:
    (
        service,
        department_id,
        alert_repository,
        task_repository,
        _,
        _,
        directive_repository,
    ) = make_dependencies()
    directive_repository.alert_ids = {alert_repository.alerts[0].id}
    task_repository.tasks.append(make_task(department_id, task_repository.tasks[0].employee_id))

    summary = await service.get_summary(department_id)

    assert summary.total == 2
    assert summary.early_warning_count == 0
    assert summary.overload_count == 1
    assert summary.overdue_task_count == 1
    assert summary.overdue_task_total == 2
    assert summary.overloaded_department_count == 1
    assert summary.items[0].category == "overload"
    assert summary.items[1].category == "overdue_task"
    assert summary.items[1].title == "2 công việc quá hạn"


@pytest.mark.asyncio
async def test_leadership_summary_includes_directed_overdue_tasks() -> None:
    (
        service,
        _,
        _,
        task_repository,
        _,
        _,
        _,
    ) = make_dependencies()
    task_repository.directed_task_ids = {task_repository.tasks[0].id}

    summary = await service.get_summary(None)

    assert summary.overdue_task_count == 1
    assert summary.overdue_task_total == 1
    assert summary.overdue_department_count == 1
    assert any(item.category == "overdue_task" for item in summary.items)
