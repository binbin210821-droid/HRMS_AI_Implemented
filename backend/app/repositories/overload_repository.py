from datetime import date as Date
from datetime import datetime, time, timedelta, timezone
from typing import Any

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.mongo_types import normalize_mongo_value
from app.models.employee import EmployeeDocument
from app.models.overload import OverloadLogDocument, WorkloadCandidateResponse
from app.models.performance import PerformanceMetricDocument


class OverloadRepository:
    """Mongo queries dedicated to overload detection and workload suggestions."""

    def __init__(self, database: AsyncIOMotorDatabase) -> None:
        self.logs = database["overload_logs"]
        self.metrics = database["performance_metrics"]
        self.employees = database["employees"]

    async def ensure_indexes(self) -> None:
        await self.logs.create_index(
            [("employee_id", 1), ("date", 1), ("trigger_reason", 1)], unique=True
        )
        await self.logs.create_index([("department_id", 1), ("date", -1)])

    async def list_employees(self, department_id: ObjectId | None) -> list[EmployeeDocument]:
        query = {"department_id": department_id} if department_id is not None else {}
        documents = await self.employees.find(query).sort("employee_code", 1).to_list(None)
        return [EmployeeDocument.model_validate(document) for document in documents]

    async def find_employee(self, employee_id: ObjectId) -> EmployeeDocument | None:
        document = await self.employees.find_one({"_id": employee_id})
        return EmployeeDocument.model_validate(document) if document else None

    async def find_employees(
        self, employee_ids: list[ObjectId]
    ) -> dict[ObjectId, EmployeeDocument]:
        if not employee_ids:
            return {}
        documents = await self.employees.find({"_id": {"$in": employee_ids}}).to_list(None)
        employees = [EmployeeDocument.model_validate(document) for document in documents]
        return {employee.id: employee for employee in employees}

    async def find_metrics(self, employee_id: ObjectId) -> list[PerformanceMetricDocument]:
        documents = (
            await self.metrics.find({"employee_id": employee_id}).sort("date", 1).to_list(None)
        )
        return [PerformanceMetricDocument.model_validate(document) for document in documents]

    async def find_by_fingerprint(self, employee_id: ObjectId, date: Date, reasons: list[str]):
        date_value = datetime.combine(date, time.min, tzinfo=timezone.utc)
        document = await self.logs.find_one(
            {"employee_id": employee_id, "date": date_value, "trigger_reason": {"$all": reasons}}
        )
        return OverloadLogDocument.model_validate(document) if document else None

    async def insert_log(self, document: dict[str, Any]) -> OverloadLogDocument:
        result = await self.logs.insert_one(normalize_mongo_value(document))
        created = await self.logs.find_one({"_id": result.inserted_id})
        return OverloadLogDocument.model_validate(created)

    async def list_logs(self, department_id: ObjectId | None) -> list[OverloadLogDocument]:
        query = {"department_id": department_id} if department_id is not None else {}
        documents = (
            await self.logs.find(query).sort([("date", -1), ("created_at", -1)]).to_list(None)
        )
        return [OverloadLogDocument.model_validate(document) for document in documents]

    async def find_rebalance_candidates(
        self,
        department_id: ObjectId,
        metric_date: Date,
        excluded_employee_id: ObjectId,
    ) -> list[WorkloadCandidateResponse]:
        return await self._find_rebalance_candidates(
            department_id, metric_date, excluded_employee_id
        )

    async def find_rebalance_candidates_for_group(
        self, department_id: ObjectId, metric_date: Date
    ) -> list[WorkloadCandidateResponse]:
        """Load candidates once for all overload logs sharing a department/date group."""
        return await self._find_rebalance_candidates(department_id, metric_date)

    async def _find_rebalance_candidates(
        self,
        department_id: ObjectId,
        metric_date: Date,
        excluded_employee_id: ObjectId | None = None,
    ) -> list[WorkloadCandidateResponse]:
        start = datetime.combine(metric_date, time.min, tzinfo=timezone.utc)
        end = start + timedelta(days=1)
        match: dict[str, Any] = {
            "date": {"$gte": start, "$lt": end},
            "tasks_completed": {"$lte": 2},
            "quality_score": {"$gte": 80},
        }
        if excluded_employee_id is not None:
            match["employee_id"] = {"$ne": excluded_employee_id}
        pipeline: list[dict[str, Any]] = [
            {"$match": match},
            {
                "$lookup": {
                    "from": "employees",
                    "localField": "employee_id",
                    "foreignField": "_id",
                    "as": "employee",
                }
            },
            {"$unwind": "$employee"},
            {
                "$match": {
                    "employee.department_id": department_id,
                    "employee.is_active": True,
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "employee_id": {"$toString": "$employee_id"},
                    "employee_code": "$employee.employee_code",
                    "employee_name": "$employee.full_name",
                    "tasks_completed": 1,
                    "quality_score": 1,
                }
            },
            {"$sort": {"tasks_completed": 1, "quality_score": -1}},
        ]
        documents = await self.metrics.aggregate(pipeline).to_list(None)
        return [WorkloadCandidateResponse.model_validate(document) for document in documents]
