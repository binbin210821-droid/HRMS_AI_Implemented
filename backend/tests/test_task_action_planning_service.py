from datetime import date, datetime, timezone

import pytest
from bson import ObjectId

from app.models.employee import EmployeeDocument
from app.models.performance import PerformanceMetricDocument
from app.models.task import TaskDocument, TaskPriority, TaskResponse, TaskStatus
from app.models.task_planning import TaskActionType
from app.services.task_action_planning_service import TaskActionPlanningService


class FixedClock:
    def today(self) -> date:
        return date(2026, 9, 10)


def employee(employee_id: ObjectId, name: str, skills: list[str]) -> EmployeeDocument:
    now = datetime.now(timezone.utc)
    return EmployeeDocument(
        _id=employee_id,
        employee_code=f"KD-{str(employee_id)[-3:]}",
        full_name=name,
        position="Nhân viên",
        skills=skills,
        department_id=DEPARTMENT_ID,
        is_active=True,
        created_at=now,
        updated_at=now,
    )


DEPARTMENT_ID = ObjectId()
CURRENT_ID = ObjectId()
CANDIDATE_ID = ObjectId()


def overdue_task_document(employee_id: ObjectId) -> TaskDocument:
    now = datetime.now(timezone.utc)
    return TaskDocument(
        _id=ObjectId(),
        title="Hoàn thiện báo cáo",
        employee_id=employee_id,
        department_id=DEPARTMENT_ID,
        priority=TaskPriority.HIGH,
        status=TaskStatus.IN_PROGRESS,
        due_date=date(2026, 9, 7),
        required_skills=["python"],
        estimated_effort_hours=4,
        created_by=ObjectId(),
        created_at=now,
        updated_at=now,
    )


def task_response(document: TaskDocument) -> TaskResponse:
    now = datetime.now(timezone.utc)
    return TaskResponse(
        id=str(document.id),
        title=document.title,
        description=None,
        subtasks=[],
        estimated_effort_hours=document.estimated_effort_hours,
        required_skills=document.required_skills,
        employee_id=str(document.employee_id),
        employee_name="Nguyễn An",
        employee_code="KD-001",
        department_id=str(document.department_id),
        priority=document.priority,
        status=document.status,
        due_date=document.due_date,
        is_overdue=True,
        created_by=str(document.created_by),
        created_at=now,
        updated_at=now,
    )


class FakeTaskRepository:
    def __init__(self, tasks: list[TaskDocument]) -> None:
        self.tasks = tasks

    async def find_department_tasks(self, _department_id):
        return self.tasks


class FakePerformanceRepository:
    def __init__(self, employees, metrics) -> None:
        self.employees = employees
        self.metrics = metrics

    async def list_department_employees(self, _department_id):
        return self.employees

    async def find_department_metrics(self, _department_id, _start_date, _end_date):
        return self.metrics


def metrics_for(employee_id: ObjectId, quality: float, performance: float):
    return [
        PerformanceMetricDocument(
            _id=ObjectId(),
            employee_id=employee_id,
            date=date(2026, 9, day),
            tasks_completed=1,
            quality_score=quality,
            reviewed_by=ObjectId(),
            performance_score=performance,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        for day in range(1, 10)
    ]


@pytest.mark.asyncio
async def test_planner_ranks_reassignment_and_extension_from_backend_data() -> None:
    current = employee(CURRENT_ID, "Nguyễn An", [])
    candidate = employee(CANDIDATE_ID, "Trần Bình", ["python"])
    task = overdue_task_document(CURRENT_ID)
    service = TaskActionPlanningService(
        FakeTaskRepository([task]),
        FakePerformanceRepository(
            [current, candidate],
            metrics_for(CURRENT_ID, 75, 76) + metrics_for(CANDIDATE_ID, 94, 92),
        ),
        FixedClock(),
    )

    plan = await service.build_plan(task_response(task), DEPARTMENT_ID)

    assert plan.options
    assert all(0 <= option.fit_score <= 100 for option in plan.options)
    reassignment = [
        option
        for option in plan.options
        if option.type == TaskActionType.REASSIGN_AND_EXTEND
    ]
    assert reassignment
    assert reassignment[0].target_employee_id == str(CANDIDATE_ID)
    assert all(
        option.due_date is None or option.due_date >= FixedClock().today()
        for option in plan.options
    )
    reset_option = next(
        option
        for option in plan.options
        if option.type == TaskActionType.REASSIGN_AND_RESET_DEADLINE
    )
    assert reset_option.due_date == date(2026, 9, 11)
    assert plan.options[0].confidence > 0


@pytest.mark.asyncio
async def test_planner_returns_manual_review_when_no_recent_data_exists() -> None:
    current = employee(CURRENT_ID, "Nguyễn An", [])
    task = overdue_task_document(CURRENT_ID)
    service = TaskActionPlanningService(
        FakeTaskRepository([task]),
        FakePerformanceRepository([current], []),
        FixedClock(),
    )

    plan = await service.build_plan(task_response(task), DEPARTMENT_ID)

    assert len(plan.options) == 1
    assert plan.options[0].type == TaskActionType.MANUAL_REVIEW
    assert plan.options[0].fit_score == 0
