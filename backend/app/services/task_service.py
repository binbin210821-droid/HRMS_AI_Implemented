from __future__ import annotations

from datetime import date as Date
from datetime import datetime, timedelta, timezone
from typing import ClassVar, List, Literal, cast

from bson import ObjectId
from fastapi import HTTPException, status
from pymongo.errors import DuplicateKeyError, PyMongoError

from app.core.mongo_types import to_mongo_datetime
from app.core.pagination import Page
from app.core.time import BusinessClock
from app.models.task import (
    ACTIVE_DIRECTIVE_STATUSES,
    AcknowledgeDepartmentTaskDirectiveRequest,
    DepartmentTaskDirectiveDocument,
    DepartmentTaskDirectiveResponse,
    DepartmentTaskDirectiveStatus,
    DepartmentTaskOverviewResponse,
    DepartmentTaskPortfolioItemResponse,
    DepartmentTaskPortfolioResponse,
    IssueDepartmentTaskDirectiveRequest,
    LeadershipTaskOverviewResponse,
    ReviewDepartmentTaskDirectiveRequest,
    SubmitDepartmentTaskDirectiveRequest,
    TaskCompletionTrendPoint,
    TaskCreate,
    TaskDirectiveFocus,
    TaskDocument,
    TaskPriority,
    TaskResponse,
    TaskStatus,
    TaskUpdate,
)
from app.repositories.task_repository import TaskRepository
from app.services.department_service import parse_object_id


class TaskService:
    """Business rules for assigning and tracking employee work."""

    MAX_SAFE_OPEN_TASKS: ClassVar[int] = 4
    MIN_PLANNED_DUE_DAYS: ClassVar[int] = 1

    def __init__(self, repository: TaskRepository, clock: BusinessClock | None = None) -> None:
        self.repository = repository
        self._clock = clock or BusinessClock()

    RANGE_DAYS: ClassVar[dict[str, int]] = {"7d": 7, "30d": 30, "90d": 90}

    async def list(
        self,
        scope: ObjectId | None,
        employee_id: str | None = None,
        task_status: TaskStatus | None = None,
        overdue_only: bool = False,
    ) -> list[TaskResponse]:
        await self.repository.ensure_indexes()
        employee_object_id = self._parse_employee_id(employee_id) if employee_id else None
        documents = await self.repository.find_many(
            scope, employee_object_id, task_status.value if task_status else None, overdue_only
        )
        return [await self._response(document) for document in documents]

    async def list_page(
        self,
        scope: ObjectId | None,
        employee_id: str | None,
        task_status: TaskStatus | None,
        overdue_only: bool,
        offset: int,
        limit: int,
    ) -> Page[TaskResponse]:
        await self.repository.ensure_indexes()
        employee_object_id = self._parse_employee_id(employee_id) if employee_id else None
        page = await self.repository.find_many_page(
            scope,
            employee_object_id,
            task_status.value if task_status else None,
            overdue_only,
            offset,
            limit,
        )
        return Page(items=[await self._response(document) for document in page.items], total=page.total)

    async def list_page_v1(
        self,
        scope: ObjectId | None,
        employee_id: str | None,
        department_id: str | None,
        task_status: TaskStatus | None,
        overdue_only: bool,
        from_date: Date | None,
        to_date: Date | None,
        sort_stage: dict[str, int],
        page: int,
        page_size: int,
    ) -> Page[TaskResponse]:
        await self.repository.ensure_indexes()
        employee_object_id = self._parse_employee_id(employee_id) if employee_id else None
        requested_department = (
            parse_object_id(department_id, "Mã phòng ban") if department_id else None
        )
        due_date: dict[str, datetime] = {}
        if from_date is not None:
            due_date["$gte"] = to_mongo_datetime(from_date)
        if to_date is not None:
            due_date["$lt"] = to_mongo_datetime(to_date + timedelta(days=1))
        result = await self.repository.find_many_page_v1(
            scope,
            employee_object_id,
            requested_department,
            task_status.value if task_status else None,
            overdue_only,
            due_date or None,
            None,
            sort_stage,
            page,
            page_size,
        )
        return Page(
            items=[await self._response(document) for document in result.items],
            total=result.total,
        )

    async def get(self, task_id: str, scope: ObjectId | None) -> TaskResponse:
        document = await self.repository.find_by_id(self._parse_task_id(task_id), scope)
        if document is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy công việc"
            )
        return await self._response(document)

    async def create(
        self, request: TaskCreate, scope: ObjectId | None, created_by: str
    ) -> TaskResponse:
        self._require_manager_scope(scope)
        employee_id = self._parse_employee_id(request.employee_id)
        employee = await self.repository.find_employee(employee_id, scope)
        if employee is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Nhân viên không tồn tại hoặc ngoài phạm vi phòng ban",
            )
        now = self._clock.now()
        document = {
            "_id": ObjectId(),
            "title": request.title.strip(),
            "description": request.description.strip() if request.description else None,
            "subtasks": self._clean_subtasks(request.subtasks),
            "estimated_effort_hours": request.estimated_effort_hours,
            "required_skills": self._clean_skills(request.required_skills),
            "employee_id": employee.id,
            "department_id": employee.department_id,
            "priority": request.priority.value,
            "status": request.status.value,
            "due_date": request.due_date,
            "completed_at": now if request.status == TaskStatus.DONE else None,
            "created_by": self._parse_user_id(created_by),
            "created_at": now,
            "updated_at": now,
        }
        try:
            created = await self.repository.insert(document)
        except DuplicateKeyError:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="Không thể tạo công việc trùng lặp"
            ) from None
        return await self._response(created)

    async def update(
        self,
        task_id: str,
        request: TaskUpdate,
        scope: ObjectId | None,
        updated_by: str | None = None,
    ) -> TaskResponse:
        self._require_manager_scope(scope)
        object_id = self._parse_task_id(task_id)
        existing = await self.repository.find_by_id(object_id, scope)
        if existing is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy công việc"
            )
        if (
            request.expected_updated_at is not None
            and existing.updated_at != request.expected_updated_at
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Công việc đã thay đổi, vui lòng tải lại đề xuất trước khi áp dụng",
            )

        values = request.model_dump(exclude_unset=True)
        if "employee_id" in values:
            employee_id = self._parse_employee_id(values["employee_id"])
            employee = await self.repository.find_employee(employee_id, scope)
            if employee is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Nhân viên nhận việc không tồn tại hoặc ngoài phạm vi phòng ban",
                )
            values["employee_id"] = employee.id
            values["department_id"] = employee.department_id
            if request.planning_version and employee.id != existing.employee_id:
                assigned = await self.repository.find_many(scope, employee_id=employee.id)
                open_tasks = [item for item in assigned if item.status != TaskStatus.DONE]
                overdue_tasks = [item for item in open_tasks if item.due_date < self._clock.today()]
                if len(open_tasks) >= self.MAX_SAFE_OPEN_TASKS or overdue_tasks:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=(
                            "Nhân viên được đề xuất đã thay đổi sức chứa hoặc có việc quá hạn; "
                            "vui lòng tải lại đề xuất"
                        ),
                    )
        if "title" in values:
            values["title"] = values["title"].strip()
        if values.get("description"):
            values["description"] = values["description"].strip()
        if "subtasks" in values:
            values["subtasks"] = self._clean_subtasks(values["subtasks"])
        if "required_skills" in values:
            values["required_skills"] = self._clean_skills(values["required_skills"])
        if "priority" in values:
            values["priority"] = values["priority"].value
        if "status" in values:
            values["status"] = values["status"].value
            values["completed_at"] = (
                self._clock.now() if values["status"] == TaskStatus.DONE.value else None
            )
        if request.planning_version:
            planned_status = values.get("status", existing.status.value)
            planned_due_date = values.get("due_date", existing.due_date)
            minimum_due_date = self._clock.today() + timedelta(days=self.MIN_PLANNED_DUE_DAYS)
            if planned_status != TaskStatus.DONE.value and planned_due_date < minimum_due_date:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Phương án phải đặt hạn hoàn thành mới trong tương lai",
                )
        values["updated_at"] = self._clock.now()
        updated = await self.repository.update(
            object_id,
            values,
            scope,
            expected_updated_at=request.expected_updated_at,
        )
        if updated is None:
            if request.expected_updated_at is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Công việc đã thay đổi, vui lòng tải lại đề xuất trước khi áp dụng",
                )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy công việc"
            )
        if updated_by:
            changed_employee = existing.employee_id != updated.employee_id
            changed_deadline = existing.due_date != updated.due_date
            if changed_employee or changed_deadline or request.planning_version:
                await self.repository.insert_audit_log(
                    {
                        "action": "task_ai_plan_applied"
                        if request.planning_version
                        else "task_updated",
                        "actor_id": self._parse_user_id(updated_by),
                        "task_id": updated.id,
                        "department_id": updated.department_id,
                        "previous_employee_id": existing.employee_id,
                        "employee_id": updated.employee_id,
                        "previous_due_date": existing.due_date,
                        "due_date": updated.due_date,
                        "planning_version": request.planning_version,
                        "created_at": self._clock.now(),
                    }
                )
        return await self._response(updated)

    async def delete(self, task_id: str, scope: ObjectId | None) -> None:
        self._require_manager_scope(scope)
        object_id = self._parse_task_id(task_id)
        if await self.repository.find_by_id(object_id, scope) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy công việc"
            )
        await self.repository.delete(object_id, scope)

    async def leadership_overview(self, range_preset: str) -> LeadershipTaskOverviewResponse:
        await self.repository.ensure_indexes()
        period_start, period_end = self._period(range_preset)
        range_value = cast(Literal["7d", "30d", "90d"], range_preset)
        today = period_end
        due_soon_end = today + timedelta(days=7)
        departments = await self.repository.list_departments()
        managers = await self.repository.list_active_managers()
        tasks = await self.repository.find_many(None)
        directed_task_ids = await self.repository.list_directed_task_ids(
            ACTIVE_DIRECTIVE_STATUSES
        )
        manager_map = {
            manager.department_id: manager.full_name
            for manager in managers
            if manager.department_id is not None
        }
        tasks_by_department: dict[ObjectId, list[TaskDocument]] = {}
        for task in tasks:
            tasks_by_department.setdefault(task.department_id, []).append(task)

        department_items: list[DepartmentTaskOverviewResponse] = []
        for department in departments:
            department_tasks = tasks_by_department.get(department.id, [])
            open_tasks = [task for task in department_tasks if task.status != TaskStatus.DONE]
            overdue_tasks = [task for task in open_tasks if task.due_date < today]
            due_soon_tasks = [
                task for task in open_tasks if today <= task.due_date <= due_soon_end
            ]
            high_priority_tasks = [
                task for task in open_tasks if task.priority == TaskPriority.HIGH
            ]
            completed_in_period = [
                task
                for task in department_tasks
                if task.completed_at
                and period_start
                <= self._utc_date(task.completed_at)
                <= period_end
            ]
            at_risk_ids = {
                task.id for task in overdue_tasks + due_soon_tasks + high_priority_tasks
            }
            undirected_overdue_count = len(
                {task.id for task in overdue_tasks} - directed_task_ids
            )
            department_items.append(
                DepartmentTaskOverviewResponse(
                    department_id=str(department.id),
                    department_name=department.name,
                    department_code=department.code,
                    manager_name=manager_map.get(department.id),
                    total_count=len(department_tasks),
                    open_count=len(open_tasks),
                    overdue_count=len(overdue_tasks),
                    due_soon_count=len(due_soon_tasks),
                    high_priority_open_count=len(high_priority_tasks),
                    completed_in_period_count=len(completed_in_period),
                    oldest_overdue_date=(
                        min(task.due_date for task in overdue_tasks) if overdue_tasks else None
                    ),
                    undirected_at_risk_count=len(at_risk_ids - directed_task_ids),
                    undirected_overdue_count=undirected_overdue_count,
                )
            )

        department_items.sort(
            key=lambda item: (
                item.overdue_count == 0,
                -item.overdue_count,
                item.oldest_overdue_date or Date.max,
                -item.due_soon_count,
                item.department_name,
            )
        )
        return LeadershipTaskOverviewResponse(
            range=range_value,
            period_start=period_start,
            period_end=period_end,
            departments_with_tasks=sum(item.open_count > 0 for item in department_items),
            departments_need_attention=sum(
                item.overdue_count > 0
                or item.due_soon_count > 0
                or item.high_priority_open_count > 0
                for item in department_items
            ),
            departments_overdue=sum(item.overdue_count > 0 for item in department_items),
            departments_due_soon=sum(item.due_soon_count > 0 for item in department_items),
            completion_trend=self._completion_trend(tasks, period_start, period_end),
            departments=department_items,
        )

    async def department_portfolio(
        self, department_id: str, range_preset: str, focus: str
    ) -> DepartmentTaskPortfolioResponse:
        await self.repository.ensure_indexes()
        object_id = parse_object_id(department_id, "Mã phòng ban")
        department = await self.repository.find_department(object_id)
        if department is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy phòng ban"
            )
        manager = await self.repository.find_active_manager_by_department(object_id)
        directives = await self.repository.list_department_directives(object_id)
        directive_by_task_id = {
            task_id: directive
            for directive in directives
            for task_id in directive.task_ids
        }
        active_directive_task_ids = {
            task_id
            for directive in directives
            if directive.status.value in ACTIVE_DIRECTIVE_STATUSES
            for task_id in directive.task_ids
        }
        tasks = await self.repository.find_department_tasks(object_id)
        period_start, period_end = self._period(range_preset)
        range_value = cast(Literal["7d", "30d", "90d"], range_preset)
        today = period_end
        due_soon_end = today + timedelta(days=7)

        open_tasks = [task for task in tasks if task.status != TaskStatus.DONE]
        overdue = [task for task in open_tasks if task.due_date < today]
        due_soon = [task for task in open_tasks if today <= task.due_date <= due_soon_end]
        categorized_ids = {task.id for task in overdue + due_soon}
        high_priority = [
            task
            for task in open_tasks
            if task.priority == TaskPriority.HIGH and task.id not in categorized_ids
        ]
        categorized_ids.update(task.id for task in high_priority)
        on_track = [task for task in open_tasks if task.id not in categorized_ids]
        completed = [
            task
            for task in tasks
            if task.completed_at
            and period_start <= self._utc_date(task.completed_at) <= period_end
        ]

        if focus != "all":
            selected = {
                TaskDirectiveFocus.OVERDUE.value: {task.id for task in overdue},
                "not_directed": {
                    task.id for task in overdue if task.id not in active_directive_task_ids
                },
                TaskDirectiveFocus.DUE_SOON.value: {task.id for task in due_soon},
                TaskDirectiveFocus.HIGH_PRIORITY_OPEN.value: {
                    task.id for task in high_priority
                },
                TaskDirectiveFocus.AT_RISK.value: {
                    task.id for task in overdue + due_soon + high_priority
                },
            }.get(focus)
            if selected is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Nhóm công việc không hợp lệ",
                )
            overdue = [task for task in overdue if task.id in selected]
            due_soon = [task for task in due_soon if task.id in selected]
            high_priority = [task for task in high_priority if task.id in selected]
            on_track = [task for task in on_track if task.id in selected]
            completed = []

        return DepartmentTaskPortfolioResponse(
            department_id=str(department.id),
            department_name=department.name,
            department_code=department.code,
            manager_name=manager.full_name if manager else None,
            range=range_value,
            period_start=period_start,
            period_end=period_end,
            overdue=[
                self._portfolio_item(
                    task,
                    today,
                    directive_by_task_id.get(task.id),
                    task.id in active_directive_task_ids,
                )
                for task in overdue
            ],
            due_soon=[
                self._portfolio_item(
                    task,
                    today,
                    directive_by_task_id.get(task.id),
                    task.id in active_directive_task_ids,
                )
                for task in due_soon
            ],
            high_priority=[
                self._portfolio_item(
                    task,
                    today,
                    directive_by_task_id.get(task.id),
                    task.id in active_directive_task_ids,
                )
                for task in high_priority
            ],
            on_track=[
                self._portfolio_item(
                    task,
                    today,
                    directive_by_task_id.get(task.id),
                    task.id in active_directive_task_ids,
                )
                for task in on_track
            ],
            completed_in_period=[
                self._portfolio_item(
                    task,
                    today,
                    directive_by_task_id.get(task.id),
                    task.id in active_directive_task_ids,
                )
                for task in completed
            ],
        )

    async def issue_department_directive(
        self,
        department_id: str,
        issued_by: str,
        request: IssueDepartmentTaskDirectiveRequest,
    ) -> DepartmentTaskDirectiveResponse:
        if request.focus != TaskDirectiveFocus.OVERDUE:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Chỉ thị công việc chỉ được phát hành cho công việc quá hạn",
            )
        await self.repository.ensure_indexes()
        department_object_id = parse_object_id(department_id, "Mã phòng ban")
        department = await self.repository.find_department(department_object_id)
        if department is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy phòng ban"
            )
        manager = await self.repository.find_active_manager_by_department(department_object_id)
        if manager is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Phòng ban chưa có Quản lý đang hoạt động để tiếp nhận chỉ thị",
            )
        tasks = await self.repository.find_department_tasks(department_object_id)
        today = self._clock.today()
        matching = self._tasks_for_focus(tasks, request.focus, today)
        if not matching:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Không có công việc phù hợp để phát hành chỉ thị",
            )
        directed_task_ids = await self.repository.list_directed_task_ids(
            ACTIVE_DIRECTIVE_STATUSES
        )
        requested_task_ids = (
            {self._parse_task_id(task_id) for task_id in request.task_ids}
            if request.task_ids is not None
            else None
        )
        matching_task_ids = {task.id for task in matching}
        if requested_task_ids is not None:
            invalid_task_ids = requested_task_ids - matching_task_ids
            if invalid_task_ids:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Chỉ được chọn các công việc quá hạn đang mở để phát hành chỉ thị",
                )
        selected = [
            task
            for task in matching
            if task.id not in directed_task_ids
            and (requested_task_ids is None or task.id in requested_task_ids)
        ]
        if not selected:
            # POST lặp lại phải có tính idempotent: bộ lọc đã loại hết việc
            # mới thì trả lại chỉ thị hiện hữu, không tạo thêm và không báo
            # Conflict cho một thao tác đã hoàn tất trước đó.
            existing_directives = await self.repository.list_department_directives(
                department_object_id
            )
            existing = next(
                (
                    directive
                    for directive in existing_directives
                    if any(task.id in directive.task_ids for task in matching)
                ),
                None,
            )
            if existing is not None:
                return await self._directive_response(existing)
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Không còn công việc mới phù hợp để phát hành chỉ thị",
            )
        pending_directives = await self.repository.list_department_directives(
            department_object_id, DepartmentTaskDirectiveStatus.PENDING.value
        )
        existing_pending = next(
            (directive for directive in pending_directives if directive.focus == request.focus),
            None,
        )
        if existing_pending is not None:
            try:
                updated = await self.repository.append_department_directive_tasks(
                    existing_pending.id, [task.id for task in selected]
                )
            except (DuplicateKeyError, PyMongoError) as error:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Chỉ thị công việc vừa được cập nhật, vui lòng tải lại danh sách",
                ) from error
            if updated is None:
                current = await self.repository.find_department_directive(existing_pending.id)
                if current is not None:
                    return await self._directive_response(current)
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Chỉ thị công việc không còn tồn tại để bổ sung công việc",
                )
            now = self._clock.now()
            await self.repository.insert_audit_log(
                {
                    "action": "department_task_directive_tasks_appended",
                    "actor_id": self._parse_user_id(issued_by),
                    "directive_id": updated.id,
                    "department_id": updated.target_department_id,
                    "task_ids": [task.id for task in selected],
                    "focus": updated.focus.value,
                    "created_at": now,
                }
            )
            return await self._directive_response(updated)
        now = self._clock.now()
        selected_task_ids = {task.id for task in selected}
        document = {
            "_id": ObjectId(),
            "target_department_id": department_object_id,
            "target_manager_id": manager.id,
            "task_ids": [task.id for task in selected],
            "focus": request.focus.value,
            "selected_task_count": len(selected),
            "note": request.note.strip() if request.note and request.note.strip() else None,
            "status": DepartmentTaskDirectiveStatus.PENDING.value,
            "issued_by": self._parse_user_id(issued_by),
            "issued_at": now,
            "acknowledged_by": None,
            "acknowledged_at": None,
            "action_note": None,
            "commitment_date": None,
        }
        try:
            directive = await self.repository.insert_department_directive(document)
        except DuplicateKeyError:
            # Hai phiên có thể phát hành đồng thời. Trả lại bản ghi thắng
            # cuộc đua để POST lặp vẫn idempotent thay vì đẩy lỗi 409 lên UI.
            concurrent_directives = await self.repository.list_department_directives(
                department_object_id
            )
            existing = next(
                (
                    item
                    for item in concurrent_directives
                    if item.status in {
                        DepartmentTaskDirectiveStatus.PENDING,
                        DepartmentTaskDirectiveStatus.ACKNOWLEDGED,
                        DepartmentTaskDirectiveStatus.SUBMITTED,
                        DepartmentTaskDirectiveStatus.NEEDS_REVISION,
                    }
                    and (
                        item.focus == request.focus
                        or any(task_id in item.task_ids for task_id in selected_task_ids)
                    )
                ),
                None,
            )
            if existing is not None:
                return await self._directive_response(existing)
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Công việc vừa được cập nhật, vui lòng tải lại danh sách",
            ) from None
        await self.repository.insert_audit_log(
            {
                "action": "department_task_directive_issued",
                "actor_id": directive.issued_by,
                "directive_id": directive.id,
                "department_id": directive.target_department_id,
                "task_ids": directive.task_ids,
                "focus": directive.focus.value,
                "created_at": now,
            }
        )
        return await self._directive_response(directive)

    async def list_department_directives(
        self, scope: ObjectId | None, directive_status: str | None = None
    ) -> List[DepartmentTaskDirectiveResponse]:
        await self.repository.ensure_indexes()
        if directive_status and directive_status not in {
            DepartmentTaskDirectiveStatus.PENDING.value,
            DepartmentTaskDirectiveStatus.ACKNOWLEDGED.value,
            DepartmentTaskDirectiveStatus.SUBMITTED.value,
            DepartmentTaskDirectiveStatus.ACCEPTED.value,
            DepartmentTaskDirectiveStatus.NEEDS_REVISION.value,
        }:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Trạng thái chỉ thị không hợp lệ",
            )
        directives = await self.repository.list_department_directives(scope, directive_status)
        return [await self._directive_response(item) for item in directives]

    async def list_department_directives_page(
        self,
        scope: ObjectId | None,
        directive_status: str | None,
        offset: int,
        limit: int,
    ) -> Page[DepartmentTaskDirectiveResponse]:
        await self.repository.ensure_indexes()
        if directive_status and directive_status not in {
            DepartmentTaskDirectiveStatus.PENDING.value,
            DepartmentTaskDirectiveStatus.ACKNOWLEDGED.value,
            DepartmentTaskDirectiveStatus.SUBMITTED.value,
            DepartmentTaskDirectiveStatus.ACCEPTED.value,
            DepartmentTaskDirectiveStatus.NEEDS_REVISION.value,
        }:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Trạng thái chỉ thị không hợp lệ",
            )
        page = await self.repository.list_department_directives_page(
            scope, directive_status, offset, limit
        )
        return Page(
            items=[await self._directive_response(item) for item in page.items],
            total=page.total,
        )

    async def acknowledge_department_directive(
        self,
        directive_id: str,
        scope: ObjectId | None,
        acknowledged_by: str,
        request: AcknowledgeDepartmentTaskDirectiveRequest,
    ) -> DepartmentTaskDirectiveResponse:
        if scope is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Lãnh đạo không trực tiếp xác nhận chỉ thị công việc",
            )
        object_id = parse_object_id(directive_id, "Mã chỉ thị công việc")
        directive = await self.repository.find_department_directive(object_id)
        if directive is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy chỉ thị công việc"
            )
        if directive.target_department_id != scope:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bạn không có quyền xác nhận chỉ thị của phòng ban khác",
            )
        if directive.status != DepartmentTaskDirectiveStatus.PENDING:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Chỉ thị công việc này đã được xác nhận",
            )
        today = self._clock.today()
        if request.commitment_date < today:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Ngày cam kết không được nằm trong quá khứ",
            )
        now = self._clock.now()
        user_id = self._parse_user_id(acknowledged_by)
        updated = await self.repository.acknowledge_department_directive(
            directive.id,
            user_id,
            now,
            request.action_note.strip(),
            request.commitment_date,
        )
        if updated is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Chỉ thị công việc này vừa được người khác xác nhận",
            )
        await self.repository.insert_audit_log(
            {
                "action": "department_task_directive_acknowledged",
                "actor_id": user_id,
                "directive_id": updated.id,
                "department_id": updated.target_department_id,
                "commitment_date": updated.commitment_date,
                "created_at": now,
            }
        )
        return await self._directive_response(updated)

    async def submit_department_directive(
        self,
        directive_id: str,
        scope: ObjectId | None,
        submitted_by: str,
        request: SubmitDepartmentTaskDirectiveRequest,
    ) -> DepartmentTaskDirectiveResponse:
        self._require_manager_scope(scope)
        object_id = parse_object_id(directive_id, "Mã chỉ thị công việc")
        directive = await self.repository.find_department_directive(object_id)
        if directive is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy chỉ thị công việc"
            )
        if directive.target_department_id != scope:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bạn không có quyền gửi nghiệm thu chỉ thị của phòng ban khác",
            )
        if directive.status not in {
            DepartmentTaskDirectiveStatus.ACKNOWLEDGED,
            DepartmentTaskDirectiveStatus.NEEDS_REVISION,
        }:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Chỉ thị công việc chưa ở trạng thái có thể gửi nghiệm thu",
            )
        progress = await self._directive_progress(directive)
        if progress[2] < 100:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Chỉ thị chỉ được gửi nghiệm thu khi tất cả công việc đã hoàn thành",
            )
        now = self._clock.now()
        user_id = self._parse_user_id(submitted_by)
        updated = await self.repository.transition_department_directive(
            directive.id,
            [
                DepartmentTaskDirectiveStatus.ACKNOWLEDGED.value,
                DepartmentTaskDirectiveStatus.NEEDS_REVISION.value,
            ],
            {
                "status": DepartmentTaskDirectiveStatus.SUBMITTED.value,
                "completion_note": self._clean_note(request.completion_note),
                "submitted_by": user_id,
                "submitted_at": now,
            },
        )
        if updated is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Chỉ thị công việc vừa được cập nhật, vui lòng tải lại",
            )
        await self.repository.insert_audit_log(
            {
                "action": "department_task_directive_submitted",
                "actor_id": user_id,
                "directive_id": updated.id,
                "department_id": updated.target_department_id,
                "completion_note": updated.completion_note,
                "created_at": now,
            }
        )
        return await self._directive_response(updated)

    async def accept_department_directive(
        self,
        directive_id: str,
        accepted_by: str,
        request: ReviewDepartmentTaskDirectiveRequest,
    ) -> DepartmentTaskDirectiveResponse:
        object_id = parse_object_id(directive_id, "Mã chỉ thị công việc")
        directive = await self.repository.find_department_directive(object_id)
        if directive is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy chỉ thị công việc"
            )
        if directive.status != DepartmentTaskDirectiveStatus.SUBMITTED:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Chỉ thị công việc chưa được gửi nghiệm thu",
            )
        if (await self._directive_progress(directive))[2] < 100:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Công việc trong chỉ thị chưa hoàn thành đủ 100%",
            )
        now = self._clock.now()
        user_id = self._parse_user_id(accepted_by)
        updated = await self.repository.transition_department_directive(
            directive.id,
            [DepartmentTaskDirectiveStatus.SUBMITTED.value],
            {
                "status": DepartmentTaskDirectiveStatus.ACCEPTED.value,
                "accepted_by": user_id,
                "accepted_at": now,
                "acceptance_note": self._clean_note(request.note),
            },
        )
        if updated is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Chỉ thị công việc vừa được người khác nghiệm thu",
            )
        await self.repository.insert_audit_log(
            {
                "action": "department_task_directive_accepted",
                "actor_id": user_id,
                "directive_id": updated.id,
                "department_id": updated.target_department_id,
                "acceptance_note": updated.acceptance_note,
                "created_at": now,
            }
        )
        return await self._directive_response(updated)

    async def request_department_directive_revision(
        self,
        directive_id: str,
        requested_by: str,
        request: ReviewDepartmentTaskDirectiveRequest,
    ) -> DepartmentTaskDirectiveResponse:
        note = self._clean_note(request.note)
        if not note:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Vui lòng nhập lý do yêu cầu xử lý lại",
            )
        object_id = parse_object_id(directive_id, "Mã chỉ thị công việc")
        directive = await self.repository.find_department_directive(object_id)
        if directive is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy chỉ thị công việc"
            )
        if directive.status != DepartmentTaskDirectiveStatus.SUBMITTED:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Chỉ thị công việc chưa được gửi nghiệm thu",
            )
        now = self._clock.now()
        user_id = self._parse_user_id(requested_by)
        updated = await self.repository.transition_department_directive(
            directive.id,
            [DepartmentTaskDirectiveStatus.SUBMITTED.value],
            {
                "status": DepartmentTaskDirectiveStatus.NEEDS_REVISION.value,
                "revision_requested_by": user_id,
                "revision_requested_at": now,
                "revision_note": note,
            },
        )
        if updated is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Chỉ thị công việc vừa được cập nhật, vui lòng tải lại",
            )
        await self.repository.insert_audit_log(
            {
                "action": "department_task_directive_revision_requested",
                "actor_id": user_id,
                "directive_id": updated.id,
                "department_id": updated.target_department_id,
                "revision_note": note,
                "created_at": now,
            }
        )
        return await self._directive_response(updated)

    async def _directive_response(
        self, directive: DepartmentTaskDirectiveDocument
    ) -> DepartmentTaskDirectiveResponse:
        department = await self.repository.find_department(directive.target_department_id)
        manager = await self.repository.find_user(directive.target_manager_id)
        completed_count, total_count, progress_percent = await self._directive_progress(directive)
        people = {}
        for field in (
            "acknowledged_by",
            "submitted_by",
            "accepted_by",
            "revision_requested_by",
        ):
            user_id = getattr(directive, field)
            if user_id:
                user = await self.repository.find_user(user_id)
                people[field] = user.full_name if user else None
        return DepartmentTaskDirectiveResponse(
            id=str(directive.id),
            target_department_id=str(directive.target_department_id),
            target_department_name=department.name if department else "Phòng ban không còn hoạt động",
            target_manager_id=str(directive.target_manager_id),
            target_manager_name=manager.full_name if manager else None,
            task_ids=[str(task_id) for task_id in directive.task_ids],
            focus=directive.focus,
            selected_task_count=directive.selected_task_count,
            note=directive.note,
            status=directive.status,
            issued_by=str(directive.issued_by),
            issued_at=directive.issued_at,
            acknowledged_by=(
                str(directive.acknowledged_by) if directive.acknowledged_by else None
            ),
            acknowledged_by_name=people.get("acknowledged_by"),
            acknowledged_at=directive.acknowledged_at,
            action_note=directive.action_note,
            commitment_date=directive.commitment_date,
            completion_note=directive.completion_note,
            submitted_by=str(directive.submitted_by) if directive.submitted_by else None,
            submitted_by_name=people.get("submitted_by"),
            submitted_at=directive.submitted_at,
            accepted_by=str(directive.accepted_by) if directive.accepted_by else None,
            accepted_by_name=people.get("accepted_by"),
            accepted_at=directive.accepted_at,
            acceptance_note=directive.acceptance_note,
            revision_requested_by=(
                str(directive.revision_requested_by)
                if directive.revision_requested_by
                else None
            ),
            revision_requested_by_name=people.get("revision_requested_by"),
            revision_requested_at=directive.revision_requested_at,
            revision_note=directive.revision_note,
            completed_item_count=completed_count,
            total_item_count=total_count,
            progress_percent=progress_percent,
        )

    async def _directive_progress(
        self, directive: DepartmentTaskDirectiveDocument
    ) -> tuple[int, int, int]:
        find_tasks = getattr(self.repository, "find_tasks_by_ids", None)
        if find_tasks is None:
            total = directive.selected_task_count
            return 0, total, 0
        tasks = await find_tasks(directive.task_ids)
        total = len(directive.task_ids)
        completed = sum(task.status == TaskStatus.DONE for task in tasks)
        return completed, total, round(completed * 100 / total) if total else 0

    @staticmethod
    def _clean_note(value: str | None) -> str | None:
        return value.strip() if value and value.strip() else None

    def _period(self, range_preset: str) -> tuple[Date, Date]:
        days = self.RANGE_DAYS.get(range_preset)
        if days is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Khoảng thời gian không hợp lệ",
            )
        end = self._clock.today()
        return end - timedelta(days=days - 1), end

    def _completion_trend(
        self, tasks: List[TaskDocument], period_start: Date, period_end: Date
    ) -> List[TaskCompletionTrendPoint]:
        first_week = period_start - timedelta(days=period_start.weekday())
        counts: dict[Date, int] = {}
        for task in tasks:
            if not task.completed_at:
                continue
            completed_date = self._utc_date(task.completed_at)
            if not period_start <= completed_date <= period_end:
                continue
            week_start = completed_date - timedelta(days=completed_date.weekday())
            counts[week_start] = counts.get(week_start, 0) + 1

        result: List[TaskCompletionTrendPoint] = []
        week = first_week
        while week <= period_end:
            result.append(
                TaskCompletionTrendPoint(
                    week_start=week,
                    label=week.strftime("%d/%m"),
                    completed_count=counts.get(week, 0),
                )
            )
            week += timedelta(days=7)
        return result

    @staticmethod
    def _portfolio_item(
        task: TaskDocument,
        today: Date,
        directive: DepartmentTaskDirectiveDocument | None = None,
        has_active_directive: bool = False,
    ) -> DepartmentTaskPortfolioItemResponse:
        return DepartmentTaskPortfolioItemResponse(
            id=str(task.id),
            title=task.title,
            priority=task.priority,
            status=task.status,
            due_date=task.due_date,
            is_overdue=task.status != TaskStatus.DONE and task.due_date < today,
            subtask_count=len(task.subtasks),
            completed_at=task.completed_at,
            directive_id=str(directive.id) if directive else None,
            directive_status=directive.status.value if directive else None,
            has_active_directive=has_active_directive,
        )

    def _utc_date(self, value: datetime) -> Date:
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(self._clock.timezone).date()

    @staticmethod
    def _tasks_for_focus(
        tasks: List[TaskDocument], focus: TaskDirectiveFocus, today: Date
    ) -> List[TaskDocument]:
        due_soon_end = today + timedelta(days=7)
        open_tasks = [task for task in tasks if task.status != TaskStatus.DONE]
        predicates = {
            TaskDirectiveFocus.OVERDUE: lambda task: task.due_date < today,
            TaskDirectiveFocus.DUE_SOON: lambda task: today <= task.due_date <= due_soon_end,
            TaskDirectiveFocus.HIGH_PRIORITY_OPEN: lambda task: task.priority
            == TaskPriority.HIGH,
            TaskDirectiveFocus.AT_RISK: lambda task: task.due_date <= due_soon_end
            or task.priority == TaskPriority.HIGH,
        }
        return [task for task in open_tasks if predicates[focus](task)]

    @staticmethod
    def _require_manager_scope(scope: ObjectId | None) -> None:
        if scope is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Lãnh đạo không trực tiếp quản lý công việc nhân viên",
            )

    async def _response(self, document: TaskDocument) -> TaskResponse:
        employee = await self.repository.find_employee(document.employee_id)
        if employee is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy nhân viên"
            )
        today = self._clock.today()
        return TaskResponse(
            id=str(document.id),
            title=document.title,
            description=document.description,
            subtasks=document.subtasks,
            estimated_effort_hours=document.estimated_effort_hours,
            required_skills=document.required_skills,
            employee_id=str(document.employee_id),
            employee_name=employee.full_name,
            employee_code=employee.employee_code,
            department_id=str(document.department_id),
            priority=document.priority,
            status=document.status,
            due_date=document.due_date,
            is_overdue=document.status != TaskStatus.DONE and document.due_date < today,
            completed_at=document.completed_at,
            created_by=str(document.created_by),
            created_at=document.created_at,
            updated_at=document.updated_at,
        )

    @staticmethod
    def _clean_subtasks(subtasks: List[str]) -> List[str]:
        return [item.strip() for item in subtasks if item and item.strip()]

    @staticmethod
    def _clean_skills(skills: List[str]) -> List[str]:
        return list(
            dict.fromkeys(item.strip().casefold() for item in skills if item and item.strip())
        )

    @staticmethod
    def _parse_employee_id(value: str) -> ObjectId:
        return parse_object_id(value, "Mã nhân viên")

    @staticmethod
    def _parse_task_id(value: str) -> ObjectId:
        return parse_object_id(value, "Mã công việc")

    @staticmethod
    def _parse_user_id(value: str) -> ObjectId:
        return parse_object_id(value, "Mã người tạo")


__all__ = ["TaskService"]
