from datetime import date, datetime, timezone

import pytest
from bson import ObjectId
from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError

from app.models.department import DepartmentDocument
from app.models.employee import EmployeeDocument
from app.models.task import (
    ACTIVE_DIRECTIVE_STATUSES,
    AcknowledgeDepartmentTaskDirectiveRequest,
    DepartmentTaskDirectiveDocument,
    DepartmentTaskDirectiveStatus,
    IssueDepartmentTaskDirectiveRequest,
    ReviewDepartmentTaskDirectiveRequest,
    SubmitDepartmentTaskDirectiveRequest,
    TaskCreate,
    TaskDirectiveFocus,
    TaskDocument,
    TaskPriority,
    TaskStatus,
    TaskUpdate,
)
from app.models.user import UserDocument, UserRole
from app.services.task_service import TaskService
from tests.time_fixtures import FixedBusinessClock


def make_employee(department_id: ObjectId, employee_id: ObjectId | None = None) -> EmployeeDocument:
    now = datetime.now(timezone.utc)
    return EmployeeDocument(
        _id=employee_id or ObjectId(),
        employee_code="KD-001",
        full_name="Nguyễn Văn A",
        position="Chuyên viên",
        department_id=department_id,
        is_active=True,
        created_at=now,
        updated_at=now,
    )


def make_department(department_id: ObjectId) -> DepartmentDocument:
    now = datetime.now(timezone.utc)
    return DepartmentDocument(
        _id=department_id,
        name="Kinh doanh",
        code="KD",
        is_active=True,
        created_at=now,
        updated_at=now,
    )


def make_manager(department_id: ObjectId, user_id: ObjectId | None = None) -> UserDocument:
    return UserDocument(
        _id=user_id or ObjectId(),
        username="manager.kd",
        password_hash="hash",
        full_name="Quản lý Kinh doanh",
        role=UserRole.MANAGER,
        department_id=department_id,
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )


class FakeTaskRepository:
    def __init__(self, employees: list[EmployeeDocument]) -> None:
        self.employees = {employee.id: employee for employee in employees}
        self.documents: dict[ObjectId, TaskDocument] = {}
        self.departments: dict[ObjectId, DepartmentDocument] = {}
        self.users: dict[ObjectId, UserDocument] = {}
        self.directives: dict[ObjectId, DepartmentTaskDirectiveDocument] = {}
        self.audits: list[dict] = []

    async def ensure_indexes(self) -> None:
        return None

    async def find_employee(
        self, employee_id: ObjectId, scope: ObjectId | None = None
    ) -> EmployeeDocument | None:
        employee = self.employees.get(employee_id)
        if employee is None or (scope is not None and employee.department_id != scope):
            return None
        return employee

    async def find_many(
        self,
        scope: ObjectId | None,
        employee_id: ObjectId | None = None,
        status: str | None = None,
        overdue_only: bool = False,
    ) -> list[TaskDocument]:
        return [
            document
            for document in self.documents.values()
            if (scope is None or document.department_id == scope)
            and (employee_id is None or document.employee_id == employee_id)
            and (status is None or document.status.value == status)
            and (not overdue_only or document.due_date < date.today())
        ]

    async def find_by_id(
        self, task_id: ObjectId, scope: ObjectId | None = None
    ) -> TaskDocument | None:
        document = self.documents.get(task_id)
        if document is None or (scope is not None and document.department_id != scope):
            return None
        return document

    async def insert(self, document: dict) -> TaskDocument:
        created = TaskDocument.model_validate(document)
        self.documents[created.id] = created
        return created

    async def update(
        self,
        task_id: ObjectId,
        values: dict,
        scope: ObjectId | None = None,
        expected_updated_at: datetime | None = None,
    ) -> TaskDocument | None:
        current = await self.find_by_id(task_id, scope)
        if current is None:
            return None
        if expected_updated_at is not None and current.updated_at != expected_updated_at:
            return None
        updated = current.model_dump(by_alias=True)
        updated.update(values)
        document = TaskDocument.model_validate(updated)
        self.documents[task_id] = document
        return document

    async def delete(self, task_id: ObjectId, scope: ObjectId | None = None) -> bool:
        if await self.find_by_id(task_id, scope) is None:
            return False
        del self.documents[task_id]
        return True

    async def find_department_tasks(self, department_id: ObjectId) -> list[TaskDocument]:
        return [item for item in self.documents.values() if item.department_id == department_id]

    async def find_tasks_by_ids(self, task_ids: list[ObjectId]) -> list[TaskDocument]:
        return [item for task_id, item in self.documents.items() if task_id in task_ids]

    async def list_departments(self) -> list[DepartmentDocument]:
        return list(self.departments.values())

    async def find_department(self, department_id: ObjectId) -> DepartmentDocument | None:
        return self.departments.get(department_id)

    async def list_active_managers(self) -> list[UserDocument]:
        return list(self.users.values())

    async def find_active_manager_by_department(
        self, department_id: ObjectId
    ) -> UserDocument | None:
        return next(
            (user for user in self.users.values() if user.department_id == department_id), None
        )

    async def find_user(self, user_id: ObjectId) -> UserDocument | None:
        return self.users.get(user_id)

    async def list_directed_task_ids(self, statuses: set[str] | None = None) -> set[ObjectId]:
        return {
            task_id
            for item in self.directives.values()
            if not statuses or item.status.value in statuses
            for task_id in item.task_ids
        }

    async def insert_department_directive(
        self, document: dict
    ) -> DepartmentTaskDirectiveDocument:
        directive = DepartmentTaskDirectiveDocument.model_validate(document)
        self.directives[directive.id] = directive
        return directive

    async def append_department_directive_tasks(
        self, directive_id: ObjectId, task_ids: list[ObjectId]
    ) -> DepartmentTaskDirectiveDocument | None:
        directive = self.directives.get(directive_id)
        if directive is None or directive.status.value != "pending":
            return None
        values = directive.model_dump(by_alias=True)
        values["task_ids"] = list(dict.fromkeys([*directive.task_ids, *task_ids]))
        values["selected_task_count"] = len(values["task_ids"])
        self.directives[directive_id] = DepartmentTaskDirectiveDocument.model_validate(values)
        return self.directives[directive_id]

    async def find_department_directive(
        self, directive_id: ObjectId
    ) -> DepartmentTaskDirectiveDocument | None:
        return self.directives.get(directive_id)

    async def list_department_directives(
        self, department_id: ObjectId | None, status: str | None = None
    ) -> list[DepartmentTaskDirectiveDocument]:
        return [
            item
            for item in self.directives.values()
            if (department_id is None or item.target_department_id == department_id)
            and (status is None or item.status.value == status)
        ]

    async def acknowledge_department_directive(
        self,
        directive_id: ObjectId,
        acknowledged_by: ObjectId,
        acknowledged_at: datetime,
        action_note: str,
        commitment_date: date,
    ) -> DepartmentTaskDirectiveDocument | None:
        directive = self.directives.get(directive_id)
        if directive is None or directive.status.value != "pending":
            return None
        values = directive.model_dump(by_alias=True)
        values.update(
            {
                "status": "acknowledged",
                "acknowledged_by": acknowledged_by,
                "acknowledged_at": acknowledged_at,
                "action_note": action_note,
                "commitment_date": commitment_date,
            }
        )
        self.directives[directive_id] = DepartmentTaskDirectiveDocument.model_validate(values)
        return self.directives[directive_id]

    async def transition_department_directive(
        self, directive_id: ObjectId, expected_statuses: list[str], values: dict
    ) -> DepartmentTaskDirectiveDocument | None:
        directive = self.directives.get(directive_id)
        if directive is None or directive.status.value not in expected_statuses:
            return None
        updated = directive.model_dump(by_alias=True)
        updated.update(values)
        self.directives[directive_id] = DepartmentTaskDirectiveDocument.model_validate(updated)
        return self.directives[directive_id]

    async def insert_audit_log(self, document: dict) -> None:
        self.audits.append(document)


class AppendDuplicateTaskRepository(FakeTaskRepository):
    async def append_department_directive_tasks(self, _directive_id, _task_ids):
        raise DuplicateKeyError("trùng chỉ thị trong lúc bổ sung công việc")


def task_request(
    employee_id: ObjectId,
    title: str = "Chuẩn bị báo cáo",
    due_date: date | None = None,
) -> TaskCreate:
    return TaskCreate(
        title=title,
        employee_id=str(employee_id),
        due_date=due_date or date.today(),
    )


@pytest.mark.asyncio
async def test_manager_cannot_create_task_for_another_department() -> None:
    own_department = ObjectId()
    other_department = ObjectId()
    own_employee = make_employee(own_department)
    other_employee = make_employee(other_department)
    service = TaskService(FakeTaskRepository([own_employee, other_employee]))

    with pytest.raises(HTTPException) as forbidden:
        await service.create(task_request(other_employee.id), own_department, str(ObjectId()))

    assert forbidden.value.status_code == 404


@pytest.mark.asyncio
async def test_leadership_cannot_create_and_manager_sees_only_own_scope() -> None:
    first_department = ObjectId()
    second_department = ObjectId()
    first_employee = make_employee(first_department)
    second_employee = make_employee(second_department)
    repository = FakeTaskRepository([first_employee, second_employee])
    service = TaskService(repository)

    first = await service.create(
        task_request(first_employee.id), first_department, str(ObjectId())
    )
    await service.create(
        task_request(second_employee.id, title="Kiểm thử hệ thống"),
        second_department,
        str(ObjectId()),
    )

    with pytest.raises(HTTPException) as forbidden:
        await service.create(task_request(first_employee.id), None, str(ObjectId()))

    assert forbidden.value.status_code == 403
    assert len(await service.list(first_department)) == 1
    assert len(await service.list(None)) == 2
    assert first.employee_name == "Nguyễn Văn A"


@pytest.mark.asyncio
async def test_leadership_overdue_list_includes_tasks_already_in_directive() -> None:
    department_id = ObjectId()
    employee = make_employee(department_id)
    repository = FakeTaskRepository([employee])
    repository.departments[department_id] = make_department(department_id)
    manager = make_manager(department_id)
    repository.users[manager.id] = manager
    service = TaskService(repository)

    await service.create(
        task_request(employee.id, due_date=date(2020, 1, 1)),
        department_id,
        str(manager.id),
    )
    await service.issue_department_directive(
        str(department_id),
        str(ObjectId()),
        IssueDepartmentTaskDirectiveRequest(focus=TaskDirectiveFocus.OVERDUE),
    )

    assert len(await service.list(None, overdue_only=True)) == 1
    assert len(await service.list(department_id, overdue_only=True)) == 1


@pytest.mark.asyncio
async def test_update_done_sets_completion_and_overdue_is_calculated() -> None:
    department_id = ObjectId()
    employee = make_employee(department_id)
    repository = FakeTaskRepository([employee])
    service = TaskService(
        repository, clock=FixedBusinessClock(datetime(2026, 9, 6, tzinfo=timezone.utc))
    )
    created = await service.create(
        task_request(employee.id, due_date=date(2020, 1, 1)),
        department_id,
        str(ObjectId()),
    )

    assert created.is_overdue is True
    updated = await service.update(created.id, TaskUpdate(status=TaskStatus.DONE), department_id)

    assert updated.status == TaskStatus.DONE
    assert updated.is_overdue is False
    assert updated.completed_at is not None


@pytest.mark.asyncio
async def test_applying_ai_plan_rechecks_candidate_capacity_and_overdue_state() -> None:
    department_id = ObjectId()
    current_employee = make_employee(department_id)
    candidate = make_employee(department_id)
    repository = FakeTaskRepository([current_employee, candidate])
    service = TaskService(
        repository, clock=FixedBusinessClock(datetime(2026, 9, 6, tzinfo=timezone.utc))
    )
    overdue = await service.create(
        task_request(current_employee.id, due_date=date(2020, 1, 1)),
        department_id,
        str(ObjectId()),
    )
    await service.create(
        task_request(candidate.id, title="Việc ứng viên đã quá hạn", due_date=date(2020, 1, 1)),
        department_id,
        str(ObjectId()),
    )

    with pytest.raises(HTTPException) as conflict:
        await service.update(
            overdue.id,
            TaskUpdate(
                employee_id=str(candidate.id),
                expected_updated_at=overdue.updated_at,
                planning_version="plan-version",
            ),
            department_id,
        )

    assert conflict.value.status_code == 409
    assert "tải lại đề xuất" in conflict.value.detail


@pytest.mark.asyncio
@pytest.mark.parametrize("new_due_date", [None, date(2026, 9, 6)])
async def test_applying_ai_plan_rejects_a_past_or_missing_new_deadline(
    new_due_date: date | None,
) -> None:
    department_id = ObjectId()
    current_employee = make_employee(department_id)
    candidate = make_employee(department_id)
    repository = FakeTaskRepository([current_employee, candidate])
    service = TaskService(
        repository, clock=FixedBusinessClock(datetime(2026, 9, 6, tzinfo=timezone.utc))
    )
    overdue = await service.create(
        task_request(current_employee.id, due_date=date(2020, 1, 1)),
        department_id,
        str(ObjectId()),
    )
    update = {
        "employee_id": str(candidate.id),
        "expected_updated_at": overdue.updated_at,
        "planning_version": "safe-plan",
    }
    if new_due_date is not None:
        update["due_date"] = new_due_date

    with pytest.raises(HTTPException) as conflict:
        await service.update(overdue.id, TaskUpdate(**update), department_id)

    assert conflict.value.status_code == 409
    assert "hạn hoàn thành mới" in conflict.value.detail


@pytest.mark.asyncio
async def test_leadership_overview_groups_risk_by_department_without_employee_fields() -> None:
    department_id = ObjectId()
    employee = make_employee(department_id)
    repository = FakeTaskRepository([employee])
    department = make_department(department_id)
    manager = make_manager(department_id)
    repository.departments[department_id] = department
    repository.users[manager.id] = manager
    service = TaskService(repository)
    today = date.today()

    await service.create(
        TaskCreate(
            title="Việc quá hạn",
            employee_id=str(employee.id),
            due_date=today.replace(year=today.year - 1),
            priority=TaskPriority.HIGH,
        ),
        department_id,
        str(manager.id),
    )
    await service.create(
        TaskCreate(
            title="Việc sắp đến hạn",
            employee_id=str(employee.id),
            due_date=today,
        ),
        department_id,
        str(manager.id),
    )

    overview = await service.leadership_overview("30d")
    portfolio = await service.department_portfolio(str(department_id), "30d", "all")

    assert overview.departments_with_tasks == 1
    assert overview.departments_need_attention == 1
    assert overview.departments_overdue == 1
    assert overview.departments_due_soon == 1
    assert overview.departments[0].undirected_at_risk_count == 2
    assert overview.departments[0].undirected_overdue_count == 1
    assert portfolio.overdue[0].title == "Việc quá hạn"
    assert "employee_id" not in portfolio.model_dump()["overdue"][0]
    assert "employee_name" not in portfolio.model_dump()["overdue"][0]

    not_directed = await service.department_portfolio(str(department_id), "30d", "not_directed")
    assert [item.title for item in not_directed.overdue] == ["Việc quá hạn"]


@pytest.mark.asyncio
async def test_accepted_directive_does_not_hide_reopened_overdue_task() -> None:
    department_id = ObjectId()
    employee = make_employee(department_id)
    repository = FakeTaskRepository([employee])
    repository.departments[department_id] = make_department(department_id)
    manager = make_manager(department_id)
    repository.users[manager.id] = manager
    service = TaskService(repository)

    task = await service.create(
        task_request(employee.id, title="Công việc mở lại", due_date=date(2020, 1, 1)),
        department_id,
        str(manager.id),
    )
    directive = await service.issue_department_directive(
        str(department_id),
        str(ObjectId()),
        IssueDepartmentTaskDirectiveRequest(focus=TaskDirectiveFocus.OVERDUE),
    )
    directive_object_id = ObjectId(directive.id)
    repository.directives[directive_object_id] = repository.directives[
        directive_object_id
    ].model_copy(update={"status": DepartmentTaskDirectiveStatus.ACCEPTED})
    task_object_id = ObjectId(task.id)
    repository.documents[task_object_id] = repository.documents[task_object_id].model_copy(
        update={"status": TaskStatus.TODO, "completed_at": None}
    )

    overview = await service.leadership_overview("30d")
    portfolio = await service.department_portfolio(str(department_id), "30d", "not_directed")
    reissued = await service.issue_department_directive(
        str(department_id),
        str(ObjectId()),
        IssueDepartmentTaskDirectiveRequest(focus=TaskDirectiveFocus.OVERDUE),
    )

    assert overview.departments[0].undirected_overdue_count == 1
    assert [item.title for item in portfolio.overdue] == ["Công việc mở lại"]
    assert portfolio.overdue[0].directive_status == "accepted"
    assert portfolio.overdue[0].has_active_directive is False
    assert reissued.id != directive.id
    assert reissued.status == DepartmentTaskDirectiveStatus.PENDING


@pytest.mark.asyncio
@pytest.mark.parametrize("active_status", sorted(ACTIVE_DIRECTIVE_STATUSES))
async def test_active_directive_status_still_hides_task_from_new_directive(
    active_status: str,
) -> None:
    department_id = ObjectId()
    employee = make_employee(department_id)
    repository = FakeTaskRepository([employee])
    repository.departments[department_id] = make_department(department_id)
    manager = make_manager(department_id)
    repository.users[manager.id] = manager
    service = TaskService(repository)

    await service.create(
        task_request(employee.id, title="Công việc đang xử lý", due_date=date(2020, 1, 1)),
        department_id,
        str(manager.id),
    )
    directive = await service.issue_department_directive(
        str(department_id),
        str(ObjectId()),
        IssueDepartmentTaskDirectiveRequest(focus=TaskDirectiveFocus.OVERDUE),
    )
    directive_object_id = ObjectId(directive.id)
    repository.directives[directive_object_id] = repository.directives[
        directive_object_id
    ].model_copy(update={"status": DepartmentTaskDirectiveStatus(active_status)})

    overview = await service.leadership_overview("30d")
    portfolio = await service.department_portfolio(str(department_id), "30d", "not_directed")
    repeated = await service.issue_department_directive(
        str(department_id),
        str(ObjectId()),
        IssueDepartmentTaskDirectiveRequest(focus=TaskDirectiveFocus.OVERDUE),
    )

    assert overview.departments[0].undirected_overdue_count == 0
    assert portfolio.overdue == []
    assert repeated.id == directive.id
    assert len(repository.directives) == 1


@pytest.mark.asyncio
async def test_department_task_directive_selects_new_tasks_and_manager_acknowledges() -> None:
    department_id = ObjectId()
    employee = make_employee(department_id)
    repository = FakeTaskRepository([employee])
    department = make_department(department_id)
    manager = make_manager(department_id)
    leadership_id = ObjectId()
    repository.departments[department_id] = department
    repository.users[manager.id] = manager
    service = TaskService(repository)
    created = await service.create(
        TaskCreate(
            title="Việc cần xử lý",
            employee_id=str(employee.id),
            due_date=date.today().replace(year=date.today().year - 1),
        ),
        department_id,
        str(manager.id),
    )

    directive = await service.issue_department_directive(
        str(department_id),
        str(leadership_id),
        IssueDepartmentTaskDirectiveRequest(
            focus=TaskDirectiveFocus.OVERDUE, task_ids=[created.id]
        ),
    )

    assert directive.selected_task_count == 1
    assert directive.status.value == "pending"
    portfolio = await service.department_portfolio(str(department_id), "30d", "all")
    assert portfolio.overdue[0].directive_id == str(directive.id)
    assert portfolio.overdue[0].directive_status == "pending"
    assert portfolio.overdue[0].has_active_directive is True
    repeated = await service.issue_department_directive(
        str(department_id),
        str(leadership_id),
        IssueDepartmentTaskDirectiveRequest(focus=TaskDirectiveFocus.OVERDUE),
    )
    assert repeated.id == directive.id
    assert repeated.selected_task_count == 1
    assert len(repository.directives) == 1

    acknowledged = await service.acknowledge_department_directive(
        directive.id,
        department_id,
        str(manager.id),
        AcknowledgeDepartmentTaskDirectiveRequest(
            action_note="Rà soát và phân bổ lại công việc",
            commitment_date=date.today(),
        ),
    )
    assert acknowledged.status.value == "acknowledged"
    assert acknowledged.action_note == "Rà soát và phân bổ lại công việc"
    assert len(repository.audits) == 2


@pytest.mark.asyncio
async def test_pending_task_directive_accepts_new_matching_tasks_without_duplicate_directive() -> None:
    department_id = ObjectId()
    employee = make_employee(department_id)
    repository = FakeTaskRepository([employee])
    department = make_department(department_id)
    manager = make_manager(department_id)
    repository.departments[department_id] = department
    repository.users[manager.id] = manager
    service = TaskService(repository)
    leadership_id = ObjectId()

    await service.create(
        task_request(employee.id, title="Công việc quá hạn 1", due_date=date(2020, 1, 1)),
        department_id,
        str(manager.id),
    )
    first = await service.issue_department_directive(
        str(department_id),
        str(leadership_id),
        IssueDepartmentTaskDirectiveRequest(focus=TaskDirectiveFocus.OVERDUE),
    )

    await service.create(
        task_request(employee.id, title="Công việc quá hạn 2", due_date=date(2020, 1, 1)),
        department_id,
        str(manager.id),
    )
    merged = await service.issue_department_directive(
        str(department_id),
        str(leadership_id),
        IssueDepartmentTaskDirectiveRequest(focus=TaskDirectiveFocus.OVERDUE),
    )

    assert merged.id == first.id
    assert merged.selected_task_count == 2
    assert len(repository.directives) == 1
    assert repository.audits[-1]["action"] == "department_task_directive_tasks_appended"


@pytest.mark.asyncio
async def test_append_directive_duplicate_returns_vietnamese_409_instead_of_500() -> None:
    department_id = ObjectId()
    employee = make_employee(department_id)
    repository = AppendDuplicateTaskRepository([employee])
    department = make_department(department_id)
    manager = make_manager(department_id)
    repository.departments[department_id] = department
    repository.users[manager.id] = manager
    service = TaskService(repository)
    leadership_id = ObjectId()

    first_task = await service.create(
        task_request(employee.id, title="Công việc quá hạn 1", due_date=date(2020, 1, 1)),
        department_id,
        str(manager.id),
    )
    await service.issue_department_directive(
        str(department_id),
        str(leadership_id),
        IssueDepartmentTaskDirectiveRequest(focus=TaskDirectiveFocus.OVERDUE, task_ids=[first_task.id]),
    )
    second_task = await service.create(
        task_request(employee.id, title="Công việc quá hạn 2", due_date=date(2020, 1, 1)),
        department_id,
        str(manager.id),
    )

    with pytest.raises(HTTPException) as error:
        await service.issue_department_directive(
            str(department_id),
            str(leadership_id),
            IssueDepartmentTaskDirectiveRequest(
                focus=TaskDirectiveFocus.OVERDUE, task_ids=[second_task.id]
            ),
        )

    assert error.value.status_code == 409
    assert "vui lòng tải lại" in error.value.detail


@pytest.mark.asyncio
async def test_department_task_directive_only_allows_overdue_focus() -> None:
    department_id = ObjectId()
    employee = make_employee(department_id)
    repository = FakeTaskRepository([employee])
    department = make_department(department_id)
    manager = make_manager(department_id)
    repository.departments[department_id] = department
    repository.users[manager.id] = manager
    service = TaskService(repository)

    with pytest.raises(HTTPException) as error:
        await service.issue_department_directive(
            str(department_id),
            str(ObjectId()),
            IssueDepartmentTaskDirectiveRequest(focus=TaskDirectiveFocus.DUE_SOON),
        )

    assert error.value.status_code == 422
    assert "công việc quá hạn" in error.value.detail


@pytest.mark.asyncio
async def test_leadership_and_other_department_cannot_acknowledge_task_directive() -> None:
    department_id = ObjectId()
    employee = make_employee(department_id)
    repository = FakeTaskRepository([employee])
    department = make_department(department_id)
    manager = make_manager(department_id)
    repository.departments[department_id] = department
    repository.users[manager.id] = manager
    service = TaskService(repository)
    await service.create(
        TaskCreate(
            title="Việc cần xử lý",
            employee_id=str(employee.id),
            due_date=date.today().replace(year=date.today().year - 1),
        ),
        department_id,
        str(manager.id),
    )
    directive = await service.issue_department_directive(
        str(department_id),
        str(ObjectId()),
        IssueDepartmentTaskDirectiveRequest(focus=TaskDirectiveFocus.OVERDUE),
    )
    request = AcknowledgeDepartmentTaskDirectiveRequest(
        action_note="Đã tiếp nhận", commitment_date=date.today()
    )

    with pytest.raises(HTTPException) as leadership_forbidden:
        await service.acknowledge_department_directive(
            directive.id, None, str(ObjectId()), request
        )
    with pytest.raises(HTTPException) as outside_scope:
        await service.acknowledge_department_directive(
            directive.id, ObjectId(), str(ObjectId()), request
        )

    assert leadership_forbidden.value.status_code == 403
    assert outside_scope.value.status_code == 403


@pytest.mark.asyncio
async def test_task_directive_requires_completion_before_submit_and_can_be_accepted() -> None:
    department_id = ObjectId()
    employee = make_employee(department_id)
    repository = FakeTaskRepository([employee])
    department = make_department(department_id)
    manager = make_manager(department_id)
    repository.departments[department_id] = department
    repository.users[manager.id] = manager
    service = TaskService(repository)
    task = await service.create(
        task_request(employee.id, due_date=date.today().replace(year=date.today().year - 1)),
        department_id,
        str(manager.id),
    )
    directive = await service.issue_department_directive(
        str(department_id),
        str(ObjectId()),
        IssueDepartmentTaskDirectiveRequest(focus=TaskDirectiveFocus.OVERDUE),
    )
    await service.acknowledge_department_directive(
        directive.id,
        department_id,
        str(manager.id),
        AcknowledgeDepartmentTaskDirectiveRequest(
            action_note="Đã lập kế hoạch xử lý", commitment_date=date.today()
        ),
    )

    with pytest.raises(HTTPException) as incomplete:
        await service.submit_department_directive(
            directive.id,
            department_id,
            str(manager.id),
            SubmitDepartmentTaskDirectiveRequest(),
        )
    assert incomplete.value.status_code == 409

    stored_task_id = ObjectId(task.id)
    repository.documents[stored_task_id] = repository.documents[stored_task_id].model_copy(
        update={"status": TaskStatus.DONE}
    )
    submitted = await service.submit_department_directive(
        directive.id,
        department_id,
        str(manager.id),
        SubmitDepartmentTaskDirectiveRequest(completion_note="Đã hoàn tất."),
    )
    revised = await service.request_department_directive_revision(
        submitted.id,
        str(ObjectId()),
        ReviewDepartmentTaskDirectiveRequest(note="Bổ sung bằng chứng."),
    )
    resubmitted = await service.submit_department_directive(
        revised.id,
        department_id,
        str(manager.id),
        SubmitDepartmentTaskDirectiveRequest(completion_note="Đã bổ sung."),
    )
    accepted = await service.accept_department_directive(
        resubmitted.id,
        str(ObjectId()),
        ReviewDepartmentTaskDirectiveRequest(note="Đã nghiệm thu."),
    )

    assert submitted.status.value == "submitted"
    assert submitted.progress_percent == 100
    assert accepted.status.value == "accepted"
    assert accepted.acknowledged_at is not None
    assert accepted.acknowledged_at == revised.acknowledged_at
    assert repository.documents[stored_task_id].status == TaskStatus.DONE
