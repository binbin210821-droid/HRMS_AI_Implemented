from datetime import date as Date
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal

from bson import ObjectId
from fastapi import HTTPException, status
from pymongo.errors import DuplicateKeyError

from app.core.pagination import Page
from app.core.time import BusinessClock
from app.events.event_bus import PERFORMANCE_METRIC_CREATED, event_bus
from app.models.performance import (
    CompanyPerformanceAnalyticsResponse,
    DepartmentPerformanceAnalyticsResponse,
    DepartmentPerformanceComparison,
    DepartmentWeeklyPerformanceTrendResponse,
    EmployeePerformanceAnalyticsResponse,
    EmployeePerformanceComparison,
    PerformanceMetricCreate,
    PerformanceMetricDocument,
    PerformanceMetricResponse,
    PerformanceTrendPoint,
    WeeklyPerformanceTrendPoint,
)
from app.repositories.performance_repository import PerformanceRepository
from app.services.department_service import parse_object_id
from app.services.performance_score_calculator import PerformanceScoreCalculator


class PerformanceService:
    def __init__(
        self,
        repository: PerformanceRepository,
        calculator: type[PerformanceScoreCalculator] = PerformanceScoreCalculator,
        clock: BusinessClock | None = None,
    ) -> None:
        self.repository = repository
        self.calculator = calculator
        self._clock = clock or BusinessClock()

    @staticmethod
    def _response(document: PerformanceMetricDocument) -> PerformanceMetricResponse:
        return PerformanceMetricResponse(
            id=str(document.id),
            employee_id=str(document.employee_id),
            date=document.date,
            tasks_completed=document.tasks_completed,
            quality_score=document.quality_score,
            reviewed_by=str(document.reviewed_by),
            performance_score=document.performance_score,
            note=document.note,
            reviewed_task_count=document.reviewed_task_count,
            evidence_task_count=document.evidence_task_count,
            total_review_task_count=document.total_review_task_count,
            created_at=document.created_at,
            updated_at=document.updated_at,
        )

    @staticmethod
    def _validate_date_range(start_date: Date | None, end_date: Date | None) -> None:
        if start_date and end_date and start_date > end_date:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Khoảng thời gian không hợp lệ",
            )

    @staticmethod
    def _forbidden_scope(message: str) -> HTTPException:
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=message)

    async def list(
        self,
        scope: ObjectId | None,
        employee_id: str | None = None,
        department_id: str | None = None,
        start_date: Date | None = None,
        end_date: Date | None = None,
    ) -> list[PerformanceMetricResponse]:
        self._validate_date_range(start_date, end_date)
        requested_employee = parse_object_id(employee_id, "Mã nhân viên") if employee_id else None
        requested_department = (
            parse_object_id(department_id, "Mã phòng ban") if department_id else None
        )
        documents = await self.repository.find_many(
            scope, requested_employee, requested_department, start_date, end_date
        )
        return [self._response(document) for document in documents]

    async def list_page(
        self,
        scope: ObjectId | None,
        employee_id: str | None,
        department_id: str | None,
        start_date: Date | None,
        end_date: Date | None,
        offset: int,
        limit: int,
    ) -> Page[PerformanceMetricResponse]:
        self._validate_date_range(start_date, end_date)
        requested_employee = parse_object_id(employee_id, "Mã nhân viên") if employee_id else None
        requested_department = (
            parse_object_id(department_id, "Mã phòng ban") if department_id else None
        )
        page = await self.repository.find_many_page(
            scope,
            requested_employee,
            requested_department,
            start_date,
            end_date,
            offset,
            limit,
        )
        return Page(items=[self._response(document) for document in page.items], total=page.total)

    async def employee_analytics(
        self,
        scope: ObjectId | None,
        employee_id: str,
        start_date: Date | None = None,
        end_date: Date | None = None,
    ) -> EmployeePerformanceAnalyticsResponse:
        self._validate_date_range(start_date, end_date)
        requested_employee = parse_object_id(employee_id, "Mã nhân viên")
        employee = await self.repository.find_employee(requested_employee)
        if employee is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy nhân viên"
            )
        if scope is not None and employee.department_id != scope:
            raise self._forbidden_scope("Bạn không có quyền xem dữ liệu nhân viên ngoài phòng ban")
        department = await self.repository.find_department(employee.department_id)
        if department is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Không tìm thấy phòng ban của nhân viên",
            )
        documents = await self.repository.aggregate_employee_trend(
            requested_employee, start_date, end_date
        )
        metrics = [
            PerformanceTrendPoint(
                date=value["date"].date() if isinstance(value["date"], datetime) else value["date"],
                tasks_completed=value.get("tasks_completed", 0),
                quality_score=value.get("quality_score", 0),
                performance_score=value.get("performance_score", 0),
            )
            for value in documents
        ]
        return EmployeePerformanceAnalyticsResponse(
            employee_id=str(employee.id),
            employee_code=employee.employee_code,
            full_name=employee.full_name,
            department_id=str(employee.department_id),
            department_name=department.name,
            metrics=metrics,
        )

    async def department_analytics(
        self,
        scope: ObjectId | None,
        department_id: str,
        start_date: Date | None = None,
        end_date: Date | None = None,
    ) -> DepartmentPerformanceAnalyticsResponse:
        self._validate_date_range(start_date, end_date)
        requested_department = parse_object_id(department_id, "Mã phòng ban")
        if scope is not None and requested_department != scope:
            raise self._forbidden_scope("Bạn không có quyền xem dữ liệu phòng ban khác")
        department = await self.repository.find_department(requested_department)
        if department is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy phòng ban"
            )
        employees = await self.repository.list_department_employees(requested_department)
        aggregates = await self.repository.aggregate_department_comparison(
            requested_department, start_date, end_date
        )
        aggregate_by_employee = {value["_id"]: value for value in aggregates}
        comparisons = []
        for employee in employees:
            aggregate = aggregate_by_employee.get(employee.id, {})
            comparisons.append(
                EmployeePerformanceComparison(
                    employee_id=str(employee.id),
                    employee_code=employee.employee_code,
                    full_name=employee.full_name,
                    average_performance_score=aggregate.get("average_performance_score"),
                    average_quality_score=aggregate.get("average_quality_score"),
                    total_tasks=aggregate.get("total_tasks", 0),
                    metric_days=aggregate.get("metric_days", 0),
                )
            )
        return DepartmentPerformanceAnalyticsResponse(
            department_id=str(department.id), department_name=department.name, employees=comparisons
        )

    async def company_analytics(
        self, start_date: Date | None = None, end_date: Date | None = None
    ) -> CompanyPerformanceAnalyticsResponse:
        self._validate_date_range(start_date, end_date)
        departments = await self.repository.list_departments()
        aggregates = await self.repository.aggregate_company_comparison(start_date, end_date)
        aggregate_by_department = {value["_id"]: value for value in aggregates}
        comparisons = [
            DepartmentPerformanceComparison(
                department_id=str(department.id),
                department_name=department.name,
                average_performance_score=aggregate_by_department.get(department.id, {}).get(
                    "average_performance_score"
                ),
                average_quality_score=aggregate_by_department.get(department.id, {}).get(
                    "average_quality_score"
                ),
                employee_count=aggregate_by_department.get(department.id, {}).get(
                    "employee_count", 0
                ),
                metric_days=aggregate_by_department.get(department.id, {}).get("metric_days", 0),
            )
            for department in departments
        ]
        return CompanyPerformanceAnalyticsResponse(departments=comparisons)

    async def department_weekly_trend(
        self,
        scope: ObjectId | None,
        department_id: str,
        start_date: Date | None = None,
        end_date: Date | None = None,
    ) -> DepartmentWeeklyPerformanceTrendResponse:
        self._validate_date_range(start_date, end_date)
        requested_department = parse_object_id(department_id, "Mã phòng ban")
        if scope is not None and requested_department != scope:
            raise self._forbidden_scope("Bạn không có quyền xem dữ liệu phòng ban khác")
        department = await self.repository.find_department(requested_department)
        if department is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy phòng ban"
            )

        aggregate = await self.repository.aggregate_weekly_average(
            requested_department, start_date, end_date
        )
        weeks: list[WeeklyPerformanceTrendPoint] = []
        for value in aggregate.get("weeks", []):
            week_start = value.get("_id")
            if isinstance(week_start, datetime):
                week_start = week_start.date()
            performance = value.get("performance")
            if week_start is None or performance is None:
                continue
            quality = value.get("quality")
            weeks.append(
                WeeklyPerformanceTrendPoint(
                    week_start=week_start,
                    week_label=week_start.strftime("%d/%m"),
                    performance=float(
                        Decimal(str(performance)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
                    ),
                    quality=(
                        float(
                            Decimal(str(quality)).quantize(
                                Decimal("0.1"), rounding=ROUND_HALF_UP
                            )
                        )
                        if quality is not None
                        else None
                    ),
                )
            )

        overall_average = aggregate.get("overall_average")
        return DepartmentWeeklyPerformanceTrendResponse(
            department_id=str(department.id),
            department_name=department.name,
            weeks=weeks,
            overall_average=(float(overall_average) if overall_average is not None else None),
        )

    async def create_daily(
        self,
        request: PerformanceMetricCreate,
        scope: ObjectId,
        reviewed_by: str,
    ) -> PerformanceMetricResponse:
        employee_id = parse_object_id(request.employee_id, "Mã nhân viên")
        employee = await self.repository.find_employee(employee_id)
        if employee is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy nhân viên"
            )
        if employee.department_id != scope:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Không thể nhập điểm cho nhân viên ngoài phòng ban",
            )

        reviewer_id = parse_object_id(reviewed_by, "Mã người chấm")
        now = self._clock.now()
        document = {
            "_id": ObjectId(),
            "employee_id": employee_id,
            "date": datetime.combine(request.date, datetime.min.time(), tzinfo=timezone.utc),
            "tasks_completed": request.tasks_completed,
            "quality_score": request.quality_score,
            "reviewed_by": reviewer_id,
            "performance_score": self.calculator.calculate(
                request.tasks_completed, request.quality_score
            ),
            "note": request.note.strip() if request.note else None,
            "created_at": now,
            "updated_at": now,
        }
        try:
            created = await self.repository.insert(document)
        except DuplicateKeyError:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Nhân viên đã có điểm trong ngày này",
            ) from None
        await event_bus.publish(PERFORMANCE_METRIC_CREATED, {"employee_id": employee_id})
        return self._response(created)
