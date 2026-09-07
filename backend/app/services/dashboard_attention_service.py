from bson import ObjectId

from app.core.time import BusinessClock
from app.models.alert import AlertDocument, AlertSeverity
from app.models.dashboard_attention import (
    AttentionCategory,
    AttentionEmployeeDetailResponse,
    AttentionItemResponse,
    AttentionSummaryResponse,
    DepartmentAttentionDetailResponse,
)
from app.models.employee import EmployeeDocument
from app.models.task import TaskDocument
from app.repositories.alert_repository import AlertRepository
from app.repositories.department_directive_repository import DepartmentDirectiveRepository
from app.repositories.department_repository import DepartmentRepository
from app.repositories.employee_repository import EmployeeRepository
from app.repositories.task_repository import TaskRepository


class DashboardAttentionService:
    """Read-only dashboard projection combining scoped alerts and overdue tasks."""

    def __init__(
        self,
        alert_repository: AlertRepository,
        task_repository: TaskRepository,
        employee_repository: EmployeeRepository,
        department_repository: DepartmentRepository,
        department_directive_repository: DepartmentDirectiveRepository | None = None,
        clock: BusinessClock | None = None,
    ) -> None:
        self.alert_repository = alert_repository
        self.task_repository = task_repository
        self.employee_repository = employee_repository
        self.department_repository = department_repository
        self.department_directive_repository = department_directive_repository
        self._clock = clock or BusinessClock()

    async def get_summary(self, scope: ObjectId | None) -> AttentionSummaryResponse:
        alerts = await self.alert_repository.find_many(scope, status="open", alert_type=None)
        overdue_tasks = await self.task_repository.find_many(scope, overdue_only=True)
        employees = await self.employee_repository.find_many(scope)
        departments = await self.department_repository.find_many(scope)

        if self.department_directive_repository is not None:
            directed_alert_ids = await self.department_directive_repository.list_alert_ids(scope)
            alerts = [alert for alert in alerts if alert.id not in directed_alert_ids]

        # Leadership chỉ theo dõi các công việc chưa được đưa vào chỉ thị.
        # Manager vẫn cần thấy công việc trong phạm vi của mình để tiếp tục xử lý.
        if scope is None:
            directed_task_ids = await self.task_repository.list_directed_task_ids()
            overdue_tasks = [task for task in overdue_tasks if task.id not in directed_task_ids]

        employee_map = {employee.id: employee for employee in employees}
        department_map = {department.id: department.name for department in departments}
        items = [self._alert_item(alert, department_map) for alert in alerts]
        items.extend(self._overdue_task_items(overdue_tasks, employee_map, department_map))
        items.sort(key=self._sort_key)

        early_warning_count = sum(item.category == "early_warning" for item in items)
        overload_count = sum(item.category == "overload" for item in items)
        overdue_task_count = sum(item.category == "overdue_task" for item in items)
        department_details = self._department_details(
            alerts, overdue_tasks, employee_map, department_map, items
        )
        early_warning_department_count = sum(
            detail.early_warning_employee_count > 0 for detail in department_details
        )
        overloaded_department_count = sum(
            detail.overload_employee_count > 0 for detail in department_details
        )
        overdue_department_count = sum(
            detail.overdue_task_count > 0 for detail in department_details
        )

        # Leadership theo dõi theo phòng ban, nên mỗi loại vấn đề của một
        # phòng ban chỉ được tính một lần. Manager vẫn giữ tổng item để không
        # thay đổi luồng xử lý theo từng nhân viên hiện có.
        total = (
            early_warning_department_count + overloaded_department_count + overdue_department_count
            if scope is None
            else len(items)
        )
        return AttentionSummaryResponse(
            total=total,
            early_warning_count=early_warning_count,
            overload_count=overload_count,
            overdue_task_count=overdue_task_count,
            overdue_task_total=len(overdue_tasks),
            overloaded_department_count=overloaded_department_count,
            early_warning_department_count=early_warning_department_count,
            overdue_department_count=overdue_department_count,
            department_details=department_details,
            items=items[:10],
            generated_at=self._clock.now(),
        )

    @staticmethod
    def _department_details(
        alerts: list[AlertDocument],
        overdue_tasks: list[TaskDocument],
        employee_map: dict[ObjectId, EmployeeDocument],
        department_map: dict[ObjectId, str],
        items: list[AttentionItemResponse],
    ) -> list[DepartmentAttentionDetailResponse]:
        departments: dict[str, dict] = {}

        def get_department(department_id: ObjectId) -> dict:
            department_key = str(department_id)
            return departments.setdefault(
                department_key,
                {
                    "department_id": department_key,
                    "department_name": department_map.get(department_id, "Phòng ban chưa xác định"),
                    "employees": {},
                },
            )

        def get_employee(department: dict, employee_id: ObjectId, name: str | None = None) -> dict:
            employee_key = str(employee_id)
            employee = employee_map.get(employee_id)
            return department["employees"].setdefault(
                employee_key,
                {
                    "employee_id": employee_key,
                    "employee_name": name
                    or (employee.full_name if employee else "Nhân viên chưa xác định"),
                    "employee_code": employee.employee_code if employee else None,
                    "early_warning_count": 0,
                    "overload_count": 0,
                    "overdue_task_count": 0,
                },
            )

        for alert in alerts:
            department = get_department(alert.department_id)
            employee = get_employee(department, alert.employee_id, alert.employee_name)
            if alert.alert_type == "overload":
                employee["overload_count"] += 1
            else:
                employee["early_warning_count"] += 1

        for task in overdue_tasks:
            department = get_department(task.department_id)
            employee = get_employee(department, task.employee_id)
            employee["overdue_task_count"] += 1

        for item in items:
            department_detail = departments.get(item.department_id)
            if department_detail is not None and "first_item_id" not in department_detail:
                department_detail["first_item_id"] = item.id
                department_detail["first_item_source"] = item.source

        details = []
        for department in departments.values():
            employee_details = [
                AttentionEmployeeDetailResponse(**employee)
                for employee in department["employees"].values()
            ]
            employee_details.sort(key=lambda employee: employee.employee_name)
            details.append(
                DepartmentAttentionDetailResponse(
                    department_id=department["department_id"],
                    department_name=department["department_name"],
                    early_warning_employee_count=sum(
                        employee.early_warning_count > 0 for employee in employee_details
                    ),
                    overload_employee_count=sum(
                        employee.overload_count > 0 for employee in employee_details
                    ),
                    overdue_employee_count=sum(
                        employee.overdue_task_count > 0 for employee in employee_details
                    ),
                    overdue_task_count=sum(
                        employee.overdue_task_count for employee in employee_details
                    ),
                    employees=employee_details,
                    first_item_id=department.get("first_item_id"),
                    first_item_source=department.get("first_item_source"),
                )
            )

        details.sort(
            key=lambda detail: (
                -int(detail.overload_employee_count > 0),
                -int(detail.early_warning_employee_count > 0),
                -int(detail.overdue_task_count > 0),
                detail.department_name,
            )
        )
        return details

    @staticmethod
    def _alert_item(
        alert: AlertDocument, department_map: dict[ObjectId, str]
    ) -> AttentionItemResponse:
        category: AttentionCategory = (
            "overload" if alert.alert_type == "overload" else "early_warning"
        )
        return AttentionItemResponse(
            id=str(alert.id),
            source="alert",
            category=category,
            title=alert.title,
            message=alert.message,
            employee_id=str(alert.employee_id),
            employee_name=alert.employee_name,
            employee_code=alert.employee_code,
            department_id=str(alert.department_id),
            department_name=department_map.get(alert.department_id),
            severity=alert.severity.value,
            created_at=alert.created_at,
        )

    def _overdue_task_items(
        self,
        tasks: list[TaskDocument],
        employee_map: dict[ObjectId, EmployeeDocument],
        department_map: dict[ObjectId, str],
    ) -> list[AttentionItemResponse]:
        grouped: dict[tuple[ObjectId, ObjectId], list[TaskDocument]] = {}
        for task in tasks:
            grouped.setdefault((task.department_id, task.employee_id), []).append(task)

        return [
            self._overdue_employee_item(
                employee_tasks, employee_map, department_map
            )
            for employee_tasks in grouped.values()
        ]

    def _overdue_employee_item(
        self,
        tasks: list[TaskDocument],
        employee_map: dict[ObjectId, EmployeeDocument],
        department_map: dict[ObjectId, str],
    ) -> AttentionItemResponse:
        oldest_task = min(tasks, key=lambda item: item.due_date)
        employee = employee_map.get(oldest_task.employee_id)
        today = self._clock.today()
        days_overdue = max(0, (today - oldest_task.due_date).days)
        employee_name = employee.full_name if employee else "Nhân viên chưa xác định"
        employee_code = employee.employee_code if employee else None
        return AttentionItemResponse(
            id=str(oldest_task.id),
            source="task",
            category="overdue_task",
            title=f"{len(tasks)} công việc quá hạn",
            message=f"Đang có {len(tasks)} công việc chưa hoàn thành sau hạn.",
            employee_id=str(oldest_task.employee_id),
            employee_name=employee_name,
            employee_code=employee_code,
            department_id=str(oldest_task.department_id),
            department_name=department_map.get(oldest_task.department_id),
            created_at=max(item.created_at for item in tasks),
            due_date=oldest_task.due_date,
            days_overdue=days_overdue,
            overdue_task_count=len(tasks),
        )

    @staticmethod
    def _sort_key(item: AttentionItemResponse) -> tuple[int, int, float]:
        if item.category == "overload" and item.severity == AlertSeverity.HIGH.value:
            rank = 0
        elif item.category == "overdue_task":
            rank = 1
        elif item.category == "overload":
            rank = 2
        else:
            rank = 3
        overdue_rank = -(item.days_overdue or 0) if item.category == "overdue_task" else 0
        return rank, overdue_rank, -item.created_at.timestamp()


__all__ = ["DashboardAttentionService"]
