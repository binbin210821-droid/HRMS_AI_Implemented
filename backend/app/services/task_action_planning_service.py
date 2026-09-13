from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from datetime import date as Date
from datetime import timedelta

from bson import ObjectId
from fastapi import HTTPException, status

from app.core.time import BusinessClock
from app.models.employee import EmployeeDocument
from app.models.performance import PerformanceMetricDocument
from app.models.task import TaskDocument, TaskResponse, TaskStatus
from app.models.task_planning import (
    OverdueTaskPlanningResponse,
    TaskActionOption,
    TaskActionType,
    TaskPlanningEmployee,
)
from app.repositories.performance_repository import PerformanceRepository
from app.repositories.task_repository import TaskRepository


class TaskActionPlanningService:
    """Deterministic, explainable planning for one overdue task."""

    MAX_OPEN_TASKS = 4
    MIN_QUALITY = 80.0
    HISTORY_DAYS = 14
    MAX_OPTIONS = 8

    def __init__(
        self,
        task_repository: TaskRepository,
        performance_repository: PerformanceRepository,
        clock: BusinessClock | None = None,
    ) -> None:
        self.task_repository = task_repository
        self.performance_repository = performance_repository
        self.clock = clock or BusinessClock()

    async def build_plan(
        self, task: TaskResponse, scope: ObjectId | None
    ) -> OverdueTaskPlanningResponse:
        if scope is None or task.department_id != str(scope):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Công việc nằm ngoài phạm vi phòng ban của bạn",
            )
        if not task.is_overdue or task.status == TaskStatus.DONE:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Công việc không còn ở trạng thái quá hạn để đề xuất xử lý",
            )

        today = self.clock.today()
        department_id = ObjectId(task.department_id)
        employees = [
            employee
            for employee in await self.performance_repository.list_department_employees(department_id)
            if employee.is_active
        ]
        tasks = await self.task_repository.find_department_tasks(department_id)
        metrics = await self.performance_repository.find_department_metrics(
            department_id, today - timedelta(days=self.HISTORY_DAYS - 1), today
        )
        profiles = self._build_profiles(employees, tasks, metrics, task, today)
        plan_version = self._plan_version(task, profiles, today)
        options = self._build_options(task, profiles, today, plan_version)
        if not options:
            options = [
                TaskActionOption(
                    option_id=self._option_id(plan_version, TaskActionType.MANUAL_REVIEW),
                    type=TaskActionType.MANUAL_REVIEW,
                    fit_score=0,
                    confidence=0.0,
                    rationale="Chưa có đủ dữ liệu hoặc nhân viên phù hợp để tự tin đề xuất.",
                    evidence=["Cần Manager rà soát thủ công trước khi thay đổi công việc."],
                )
            ]

        return OverdueTaskPlanningResponse(
            task_id=task.id,
            summary=self._summary(options),
            options=options,
            data_as_of=today,
            plan_version=plan_version,
        )

    def _build_profiles(
        self,
        employees: list[EmployeeDocument],
        tasks: list[TaskDocument],
        metrics: list[PerformanceMetricDocument],
        overdue_task: TaskResponse,
        today: Date,
    ) -> list[TaskPlanningEmployee]:
        employee_tasks: dict[str, list[TaskDocument]] = defaultdict(list)
        for task in tasks:
            employee_tasks[str(task.employee_id)].append(task)
        employee_metrics: dict[str, list[PerformanceMetricDocument]] = defaultdict(list)
        for metric in metrics:
            employee_metrics[str(metric.employee_id)].append(metric)

        profiles: list[TaskPlanningEmployee] = []
        for employee in employees:
            employee_id = str(employee.id)
            assigned = employee_tasks[employee_id]
            open_tasks = [task for task in assigned if task.status != TaskStatus.DONE]
            overdue_count = sum(1 for task in open_tasks if task.due_date < today)
            history = sorted(employee_metrics[employee_id], key=lambda item: item.date)
            recent = history[-self.HISTORY_DAYS :]
            qualities = [float(item.quality_score) for item in recent]
            performances = [float(item.performance_score) for item in recent]
            average_quality = self._average(qualities)
            average_performance = self._average(performances)
            trend = self._trend(performances)
            latest_tasks = recent[-1].tasks_completed if recent else None
            capacity_score = self._capacity_score(
                len(open_tasks), overdue_count, overdue_task.estimated_effort_hours
            )
            reliability_score = max(0.0, 100.0 - overdue_count * 25.0)
            confidence = self._confidence(recent, today)
            skill_fit_score = self._skill_fit(overdue_task.required_skills, employee.skills)
            is_current = employee_id == overdue_task.employee_id
            eligible = (
                not is_current
                and bool(recent)
                and average_quality is not None
                and average_quality >= self.MIN_QUALITY
                and len(open_tasks) < self.MAX_OPEN_TASKS
                and overdue_count == 0
                and (not overdue_task.required_skills or skill_fit_score >= 50)
            )
            exclusion_reason = None
            if not eligible and not is_current:
                exclusion_reason = self._exclusion_reason(
                    recent,
                    average_quality,
                    len(open_tasks),
                    overdue_count,
                    skill_fit_score,
                    bool(overdue_task.required_skills),
                )
            profiles.append(
                TaskPlanningEmployee(
                    employee_id=employee_id,
                    employee_name=employee.full_name,
                    employee_code=employee.employee_code,
                    open_task_count=len(open_tasks),
                    overdue_task_count=overdue_count,
                    average_performance_score=average_performance,
                    average_quality_score=average_quality,
                    performance_trend=trend,
                    latest_tasks_completed=latest_tasks,
                    capacity_score=capacity_score,
                    reliability_score=reliability_score,
                    skill_fit_score=skill_fit_score,
                    confidence=confidence,
                    eligible=eligible or is_current,
                    exclusion_reason=exclusion_reason,
                )
            )
        return profiles

    def _build_options(
        self,
        task: TaskResponse,
        profiles: list[TaskPlanningEmployee],
        today: Date,
        plan_version: str,
    ) -> list[TaskActionOption]:
        current = next((item for item in profiles if item.employee_id == task.employee_id), None)
        options: list[TaskActionOption] = []
        for extension_days in (1, 3, 5):
            due_date = today + timedelta(days=extension_days)
            if current is not None and current.confidence > 0:
                score = self._option_score(current, task, extension_days, reassigned=False)
                options.append(
                    self._option(
                        plan_version,
                        TaskActionType.KEEP_AND_EXTEND,
                        task,
                        current,
                        due_date,
                        score,
                        extension_days,
                    )
                )

        for candidate in [item for item in profiles if item.eligible and item.employee_id != task.employee_id]:
            reset_days = 1
            reset_due_date = today + timedelta(days=reset_days)
            score = self._option_score(candidate, task, reset_days, reassigned=True)
            options.append(
                self._option(
                    plan_version,
                    TaskActionType.REASSIGN_AND_RESET_DEADLINE,
                    task,
                    candidate,
                    reset_due_date,
                    score,
                    reset_days,
                )
            )
            extended_score = self._option_score(candidate, task, 3, reassigned=True)
            options.append(
                self._option(
                    plan_version,
                    TaskActionType.REASSIGN_AND_EXTEND,
                    task,
                    candidate,
                    today + timedelta(days=3),
                    extended_score,
                    3,
                )
            )
        options.sort(key=lambda item: (-item.fit_score, item.option_id))
        return options[: self.MAX_OPTIONS]

    def _option(
        self,
        plan_version: str,
        action_type: TaskActionType,
        task: TaskResponse,
        profile: TaskPlanningEmployee,
        due_date: Date,
        score: int,
        extension_days: int,
    ) -> TaskActionOption:
        reassigned = action_type != TaskActionType.KEEP_AND_EXTEND
        reasons = [
            f"Khả năng nhận thêm việc: {profile.capacity_score:.0f}/100",
            f"Điểm chất lượng gần đây: {profile.average_quality_score:.1f}/100"
            if profile.average_quality_score is not None
            else "Chưa có đủ lịch sử chất lượng gần đây",
            f"Khả năng hoàn thành đúng hạn: {profile.reliability_score:.0f}/100",
            f"Mức khớp với yêu cầu công việc: {profile.skill_fit_score:.0f}/100",
        ]
        if action_type == TaskActionType.REASSIGN_AND_RESET_DEADLINE:
            reasons.append(f"Đặt lại hạn tối thiểu {extension_days} ngày để không chuyển quá hạn")
        elif extension_days:
            reasons.append(f"Gia hạn {extension_days} ngày để có thời gian xử lý lại")
        if reassigned:
            reasons.append("Đổi người phụ trách để giảm tải cho người đang xử lý")
        return TaskActionOption(
            option_id=self._option_id(plan_version, action_type, profile.employee_id, due_date),
            type=action_type,
            target_employee_id=profile.employee_id if reassigned else task.employee_id,
            target_employee_name=profile.employee_name,
            due_date=due_date,
            fit_score=score,
            confidence=profile.confidence,
            rationale="; ".join(reasons),
            evidence=reasons[:6],
        )

    def _option_score(
        self,
        profile: TaskPlanningEmployee,
        task: TaskResponse,
        extension_days: int,
        reassigned: bool,
    ) -> int:
        quality = profile.average_quality_score if profile.average_quality_score is not None else 50.0
        performance = (
            profile.average_performance_score
            if profile.average_performance_score is not None
            else quality
        )
        overdue_days = max(1, (self.clock.today() - task.due_date).days)
        deadline_recovery = min(100.0, max(0.0, 100.0 - overdue_days * 12 + extension_days * 8))
        skill_fit = profile.skill_fit_score
        penalty = 5.0 if reassigned else 0.0
        score = (
            profile.capacity_score * 0.30
            + quality * 0.20
            + deadline_recovery * 0.20
            + skill_fit * 0.10
            + profile.reliability_score * 0.10
            + performance * 0.10
            - penalty
        )
        return max(0, min(100, round(score)))

    @staticmethod
    def _capacity_score(
        open_count: int, overdue_count: int, effort_hours: float | None
    ) -> float:
        effort_load = min(2.0, (effort_hours or 0.0) / 8.0)
        return max(
            0.0,
            min(
                100.0,
                100.0 - (open_count + effort_load) / 4.0 * 100.0 - overdue_count * 20.0,
            ),
        )

    @staticmethod
    def _skill_fit(required_skills: list[str], employee_skills: list[str]) -> float:
        if not required_skills:
            return 70.0
        required = {item.strip().casefold() for item in required_skills if item.strip()}
        available = {item.strip().casefold() for item in employee_skills if item.strip()}
        return round(len(required & available) / len(required) * 100.0, 2) if required else 70.0

    @staticmethod
    def _confidence(history: list[PerformanceMetricDocument], today: Date) -> float:
        if not history:
            return 0.0
        sample_score = min(1.0, len(history) / 10.0) * 0.7
        age_days = max(0, (today - history[-1].date).days)
        recency_score = max(0.0, 1.0 - age_days / 14.0) * 0.3
        return round(min(1.0, sample_score + recency_score), 2)

    @staticmethod
    def _trend(values: list[float]) -> float | None:
        if len(values) < 2:
            return None
        midpoint = max(1, len(values) // 2)
        return round(sum(values[midpoint:]) / len(values[midpoint:]) - sum(values[:midpoint]) / len(values[:midpoint]), 2)

    @staticmethod
    def _average(values: list[float]) -> float | None:
        return round(sum(values) / len(values), 2) if values else None

    @staticmethod
    def _exclusion_reason(
        history: list[PerformanceMetricDocument],
        average_quality: float | None,
        open_count: int,
        overdue_count: int,
        skill_fit_score: float,
        has_required_skills: bool,
    ) -> str:
        if not history:
            return "Chưa có dữ liệu hiệu suất đủ mới"
        if average_quality is not None and average_quality < TaskActionPlanningService.MIN_QUALITY:
            return "Điểm chất lượng gần đây dưới ngưỡng an toàn"
        if overdue_count:
            return "Đang có công việc quá hạn"
        if has_required_skills and skill_fit_score < 50:
            return "Chưa khớp đủ kỹ năng yêu cầu"
        if open_count >= TaskActionPlanningService.MAX_OPEN_TASKS:
            return "Đã gần hoặc vượt sức chứa công việc"
        return "Chưa đạt điều kiện an toàn"

    @staticmethod
    def _option_id(
        plan_version: str,
        action_type: TaskActionType,
        employee_id: str | None = None,
        due_date: Date | None = None,
    ) -> str:
        value = f"{plan_version}|{action_type.value}|{employee_id or ''}|{due_date or ''}"
        return hashlib.sha256(value.encode()).hexdigest()[:20]

    @staticmethod
    def _plan_version(
        task: TaskResponse, profiles: list[TaskPlanningEmployee], data_as_of: Date
    ) -> str:
        payload = {
            "task_id": task.id,
            "updated_at": task.updated_at.isoformat(),
            "data_as_of": data_as_of.isoformat(),
            "profiles": [profile.model_dump(mode="json") for profile in profiles],
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:24]

    @staticmethod
    def _summary(options: list[TaskActionOption]) -> str:
        actionable = [item for item in options if item.type != TaskActionType.MANUAL_REVIEW]
        if not actionable:
            return "Chưa có phương án đủ an toàn; bạn có thể xử lý thủ công."
        return f"Đã tính {len(actionable)} phương án, phương án cao nhất đạt {actionable[0].fit_score}/100."


__all__ = ["TaskActionPlanningService"]
