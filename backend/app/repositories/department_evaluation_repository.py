from datetime import date as Date
from datetime import timedelta
from typing import Any

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.mongo_types import normalize_mongo_value, to_mongo_datetime
from app.models.department import DepartmentDocument
from app.models.department_evaluation import DepartmentWeeklyEvaluationDocument
from app.models.user import UserDocument


class DepartmentEvaluationRepository:
    """MongoDB access dedicated to weekly department evaluations."""

    def __init__(self, database: AsyncIOMotorDatabase) -> None:
        self.evaluations = database["department_weekly_evaluations"]
        self.departments = database["departments"]
        self.users = database["users"]
        self.employees = database["employees"]
        self.performance_metrics = database["performance_metrics"]
        self.tasks = database["tasks"]
        self.alerts = database["alerts"]
        self.alert_directives = database["department_alert_directives"]
        self.task_directives = database["department_task_directives"]
        self.audit_logs = database["audit_logs"]

    async def ensure_indexes(self) -> None:
        await self.evaluations.create_index(
            [("department_id", 1), ("week_start", 1)],
            name="department_weekly_evaluation_unique",
            unique=True,
        )
        await self.evaluations.create_index(
            [("department_id", 1), ("week_start", -1), ("department_name", 1)],
            name="department_weekly_evaluation_list",
        )

    async def find_department(self, department_id: ObjectId) -> DepartmentDocument | None:
        document = await self.departments.find_one({"_id": department_id, "is_active": True})
        return DepartmentDocument.model_validate(document) if document else None

    async def find_active_manager(self, department_id: ObjectId) -> UserDocument | None:
        document = await self.users.find_one(
            {"role": "manager", "department_id": department_id, "is_active": True}
        )
        return UserDocument.model_validate(document) if document else None

    async def list_performance_metrics(
        self, department_id: ObjectId, start_date: Date, end_date: Date
    ) -> list[dict[str, Any]]:
        employee_ids = await self.employees.distinct("_id", {"department_id": department_id})
        if not employee_ids:
            return []
        return await self.performance_metrics.find(
            {
                "employee_id": {"$in": employee_ids},
                "date": {
                    "$gte": to_mongo_datetime(start_date),
                    "$lt": to_mongo_datetime(end_date + timedelta(days=1)),
                },
            }
        ).to_list(None)

    async def list_tasks(self, department_id: ObjectId) -> list[dict[str, Any]]:
        return await self.tasks.find({"department_id": department_id}).to_list(None)

    async def list_alerts(self, department_id: ObjectId) -> list[dict[str, Any]]:
        return await self.alerts.find({"department_id": department_id}).to_list(None)

    async def list_alert_directives(self, department_id: ObjectId) -> list[dict[str, Any]]:
        return await self.alert_directives.find({"target_department_id": department_id}).to_list(
            None
        )

    async def list_task_directives(self, department_id: ObjectId) -> list[dict[str, Any]]:
        return await self.task_directives.find({"target_department_id": department_id}).to_list(
            None
        )

    async def find_evaluation(
        self, department_id: ObjectId, week_start: Date
    ) -> DepartmentWeeklyEvaluationDocument | None:
        document = await self.evaluations.find_one(
            {"department_id": department_id, "week_start": to_mongo_datetime(week_start)}
        )
        return DepartmentWeeklyEvaluationDocument.model_validate(document) if document else None

    async def find_evaluation_by_id(
        self, evaluation_id: ObjectId
    ) -> DepartmentWeeklyEvaluationDocument | None:
        document = await self.evaluations.find_one({"_id": evaluation_id})
        return DepartmentWeeklyEvaluationDocument.model_validate(document) if document else None

    async def list_evaluations(
        self,
        department_id: ObjectId | None = None,
        page: int = 1,
        page_size: int = 12,
    ) -> tuple[list[DepartmentWeeklyEvaluationDocument], int]:
        query = {"department_id": department_id} if department_id is not None else {}
        total = await self.evaluations.count_documents(query)
        documents = (
            await self.evaluations.find(query)
            .sort([("week_start", -1), ("department_name", 1)])
            .skip((page - 1) * page_size)
            .limit(page_size)
            .to_list(None)
        )
        return [DepartmentWeeklyEvaluationDocument.model_validate(item) for item in documents], total

    async def insert(self, values: dict[str, Any]) -> DepartmentWeeklyEvaluationDocument:
        result = await self.evaluations.insert_one(normalize_mongo_value(values))
        document = await self.evaluations.find_one({"_id": result.inserted_id})
        return DepartmentWeeklyEvaluationDocument.model_validate(document)

    async def update(
        self, evaluation_id: ObjectId, values: dict[str, Any]
    ) -> DepartmentWeeklyEvaluationDocument | None:
        result = await self.evaluations.update_one(
            {"_id": evaluation_id}, {"$set": normalize_mongo_value(values)}
        )
        if result.matched_count != 1:
            return None
        return await self.find_evaluation_by_id(evaluation_id)

    async def insert_audit_log(self, values: dict[str, Any]) -> None:
        await self.audit_logs.insert_one(normalize_mongo_value(values))


__all__ = ["DepartmentEvaluationRepository"]
