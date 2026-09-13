from datetime import date as Date
from datetime import datetime, time, timedelta, timezone
from typing import Any

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.mongo_types import normalize_mongo_value
from app.core.pagination import Page
from app.models.department import DepartmentDocument
from app.models.employee import EmployeeDocument
from app.models.performance import PerformanceMetricDocument


class PerformanceRepository:
    def __init__(self, database: AsyncIOMotorDatabase) -> None:
        self.client = database.client
        self.collection = database["performance_metrics"]
        self.employees = database["employees"]
        self.departments = database["departments"]

    async def ensure_indexes(self) -> None:
        await self.collection.create_index(
            [("employee_id", 1), ("date", 1)], unique=True
        )

    async def find_employee(self, employee_id: ObjectId) -> EmployeeDocument | None:
        document = await self.employees.find_one({"_id": employee_id})
        return EmployeeDocument.model_validate(document) if document else None

    async def find_by_employee_date(
        self, employee_id: ObjectId, metric_date: Date
    ) -> PerformanceMetricDocument | None:
        document = await self.collection.find_one(
            {"employee_id": employee_id, "date": normalize_mongo_value(metric_date)}
        )
        return PerformanceMetricDocument.model_validate(document) if document else None

    async def list_employees(self, department_id: ObjectId | None = None) -> list[EmployeeDocument]:
        query = {"department_id": department_id} if department_id is not None else {}
        documents = await self.employees.find(query).sort("employee_code", 1).to_list(length=None)
        return [EmployeeDocument.model_validate(document) for document in documents]

    async def find_department(self, department_id: ObjectId) -> DepartmentDocument | None:
        document = await self.departments.find_one({"_id": department_id})
        return DepartmentDocument.model_validate(document) if document else None

    async def list_departments(self) -> list[DepartmentDocument]:
        documents = await self.departments.find({}).sort("name", 1).to_list(length=None)
        return [DepartmentDocument.model_validate(document) for document in documents]

    async def list_department_employees(self, department_id: ObjectId) -> list[EmployeeDocument]:
        documents = (
            await self.employees.find({"department_id": department_id})
            .sort("full_name", 1)
            .to_list(length=None)
        )
        return [EmployeeDocument.model_validate(document) for document in documents]

    @staticmethod
    def _date_filter(start_date: Date | None, end_date: Date | None) -> dict[str, Any]:
        date_filter: dict[str, Any] = {}
        if start_date is not None:
            date_filter["$gte"] = datetime.combine(start_date, time.min, tzinfo=timezone.utc)
        if end_date is not None:
            exclusive_end = end_date + timedelta(days=1)
            date_filter["$lt"] = datetime.combine(exclusive_end, time.min, tzinfo=timezone.utc)
        return date_filter

    async def aggregate_employee_trend(
        self,
        employee_id: ObjectId,
        start_date: Date | None = None,
        end_date: Date | None = None,
    ) -> list[dict[str, Any]]:
        match: dict[str, Any] = {"employee_id": employee_id}
        date_filter = self._date_filter(start_date, end_date)
        if date_filter:
            match["date"] = date_filter
        pipeline = [
            {"$match": match},
            {"$sort": {"date": 1}},
            {
                "$project": {
                    "_id": 0,
                    "date": 1,
                    "tasks_completed": 1,
                    "quality_score": 1,
                    "performance_score": 1,
                }
            },
        ]
        return await self.collection.aggregate(pipeline).to_list(length=None)

    async def aggregate_department_trend(
        self,
        department_id: ObjectId,
        start_date: Date | None = None,
        end_date: Date | None = None,
    ) -> list[dict[str, Any]]:
        """Aggregate daily performance for employees in one department."""

        employees = await self.list_department_employees(department_id)
        employee_ids = [employee.id for employee in employees]
        if not employee_ids:
            return []
        match: dict[str, Any] = {"employee_id": {"$in": employee_ids}}
        date_filter = self._date_filter(start_date, end_date)
        if date_filter:
            match["date"] = date_filter
        pipeline = [
            {"$match": match},
            {
                "$group": {
                    "_id": "$date",
                    "average_performance_score": {"$avg": "$performance_score"},
                    "average_quality_score": {"$avg": "$quality_score"},
                    "total_tasks": {"$sum": "$tasks_completed"},
                    "employee_count": {"$addToSet": "$employee_id"},
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "date": "$_id",
                    "average_performance_score": 1,
                    "average_quality_score": 1,
                    "total_tasks": 1,
                    "employee_count": {"$size": "$employee_count"},
                }
            },
            {"$sort": {"date": 1}},
        ]
        return await self.collection.aggregate(pipeline).to_list(length=None)

    async def find_employee_metrics(self, employee_id: ObjectId) -> list[PerformanceMetricDocument]:
        documents = (
            await self.collection.find({"employee_id": employee_id})
            .sort("date", 1)
            .to_list(length=None)
        )
        return [PerformanceMetricDocument.model_validate(document) for document in documents]

    async def find_department_metrics(
        self,
        department_id: ObjectId,
        start_date: Date | None = None,
        end_date: Date | None = None,
    ) -> list[PerformanceMetricDocument]:
        """Read bounded performance history for task-planning candidates."""

        employees = await self.list_department_employees(department_id)
        employee_ids = [employee.id for employee in employees]
        if not employee_ids:
            return []
        match: dict[str, Any] = {"employee_id": {"$in": employee_ids}}
        date_filter = self._date_filter(start_date, end_date)
        if date_filter:
            match["date"] = date_filter
        documents = await self.collection.find(match).sort("date", 1).to_list(length=None)
        return [PerformanceMetricDocument.model_validate(document) for document in documents]

    async def aggregate_department_comparison(
        self,
        department_id: ObjectId,
        start_date: Date | None = None,
        end_date: Date | None = None,
    ) -> list[dict[str, Any]]:
        employees = await self.list_department_employees(department_id)
        employee_ids = [employee.id for employee in employees]
        if not employee_ids:
            return []
        match: dict[str, Any] = {"employee_id": {"$in": employee_ids}}
        date_filter = self._date_filter(start_date, end_date)
        if date_filter:
            match["date"] = date_filter
        pipeline = [
            {"$match": match},
            {
                "$group": {
                    "_id": "$employee_id",
                    "average_performance_score": {"$avg": "$performance_score"},
                    "average_quality_score": {"$avg": "$quality_score"},
                    "total_tasks": {"$sum": "$tasks_completed"},
                    "metric_days": {"$sum": 1},
                }
            },
        ]
        return await self.collection.aggregate(pipeline).to_list(length=None)

    async def aggregate_weekly_average(
        self,
        department_id: ObjectId,
        start_date: Date | None = None,
        end_date: Date | None = None,
    ) -> dict[str, Any]:
        employees = await self.list_department_employees(department_id)
        employee_ids = [employee.id for employee in employees]
        if not employee_ids:
            return {"weeks": [], "overall_average": None}

        match: dict[str, Any] = {"employee_id": {"$in": employee_ids}}
        date_filter = self._date_filter(start_date, end_date)
        if date_filter:
            match["date"] = date_filter

        pipeline = [
            {"$match": match},
            {
                "$facet": {
                    "weeks": [
                        {
                            "$group": {
                                "_id": {
                                    "$dateTrunc": {
                                        "date": "$date",
                                        "unit": "week",
                                        "binSize": 1,
                                        "startOfWeek": "monday",
                                        "timezone": "UTC",
                                    }
                                },
                                "performance": {"$avg": "$performance_score"},
                                "quality": {"$avg": "$quality_score"},
                            }
                        },
                        {"$sort": {"_id": 1}},
                    ],
                    "overall": [
                        {"$group": {"_id": None, "average": {"$avg": "$performance_score"}}}
                    ],
                }
            },
        ]
        result = await self.collection.aggregate(pipeline).to_list(length=1)
        if not result:
            return {"weeks": [], "overall_average": None}

        aggregate = result[0]
        overall = aggregate.get("overall", [])
        return {
            "weeks": aggregate.get("weeks", []),
            "overall_average": overall[0].get("average") if overall else None,
        }

    async def aggregate_company_comparison(
        self,
        start_date: Date | None = None,
        end_date: Date | None = None,
    ) -> list[dict[str, Any]]:
        match: dict[str, Any] = {}
        date_filter = self._date_filter(start_date, end_date)
        if date_filter:
            match["date"] = date_filter
        pipeline: list[dict[str, Any]] = []
        if match:
            pipeline.append({"$match": match})
        pipeline.extend(
            [
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
                    "$group": {
                        "_id": "$employee.department_id",
                        "average_performance_score": {"$avg": "$performance_score"},
                        "average_quality_score": {"$avg": "$quality_score"},
                        "total_tasks": {"$sum": "$tasks_completed"},
                        "metric_days": {"$sum": 1},
                        "employee_ids": {"$addToSet": "$employee_id"},
                    }
                },
                {
                    "$project": {
                        "_id": 1,
                        "average_performance_score": 1,
                        "average_quality_score": 1,
                        "metric_days": 1,
                        "employee_count": {"$size": "$employee_ids"},
                    }
                },
            ]
        )
        return await self.collection.aggregate(pipeline).to_list(length=None)

    async def find_many(
        self,
        scope: ObjectId | None,
        employee_id: ObjectId | None = None,
        department_id: ObjectId | None = None,
        start_date: Date | None = None,
        end_date: Date | None = None,
        limit: int | None = None,
    ) -> list[PerformanceMetricDocument]:
        query = await self._find_many_query(scope, employee_id, department_id, start_date, end_date)
        cursor = self.collection.find(query).sort("date", -1)
        if limit is not None:
            cursor = cursor.limit(limit)
        documents = await cursor.to_list(length=None)
        return [PerformanceMetricDocument.model_validate(document) for document in documents]

    async def find_many_page(
        self,
        scope: ObjectId | None,
        employee_id: ObjectId | None = None,
        department_id: ObjectId | None = None,
        start_date: Date | None = None,
        end_date: Date | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> Page[PerformanceMetricDocument]:
        query = await self._find_many_query(scope, employee_id, department_id, start_date, end_date)
        total = await self.collection.count_documents(query)
        documents = (
            await self.collection.find(query)
            .sort("date", -1)
            .skip(offset)
            .limit(limit)
            .to_list(length=None)
        )
        return Page(
            items=[PerformanceMetricDocument.model_validate(document) for document in documents],
            total=total,
        )

    async def _find_many_query(
        self,
        scope: ObjectId | None,
        employee_id: ObjectId | None,
        department_id: ObjectId | None,
        start_date: Date | None,
        end_date: Date | None,
    ) -> dict:
        query: dict = {}
        employee_query: dict = {}
        if scope is not None:
            employee_query["department_id"] = scope
        elif department_id is not None:
            employee_query["department_id"] = department_id

        if employee_query:
            employee_ids = await self.employees.distinct("_id", employee_query)
            if employee_id is not None:
                if employee_id not in employee_ids:
                    query["employee_id"] = {"$in": []}
                else:
                    query["employee_id"] = employee_id
            else:
                query["employee_id"] = {"$in": employee_ids}
        elif employee_id is not None:
            query["employee_id"] = employee_id

        date_query = self._date_filter(start_date, end_date)
        if date_query:
            query["date"] = date_query
        return query

    async def insert(self, document: dict) -> PerformanceMetricDocument:
        result = await self.collection.insert_one(normalize_mongo_value(document))
        created = await self.collection.find_one({"_id": result.inserted_id})
        return PerformanceMetricDocument.model_validate(created)

    async def upsert_daily_review(
        self,
        employee_id: ObjectId,
        metric_date: Date,
        values: dict,
        session: Any | None = None,
    ) -> PerformanceMetricDocument:
        normalized = normalize_mongo_value(values)
        created_at = normalized.pop("created_at", None)
        set_on_insert = {
            "_id": ObjectId(),
            "employee_id": employee_id,
            "date": normalize_mongo_value(metric_date),
        }
        if created_at is not None:
            set_on_insert["created_at"] = created_at
        update_options: dict[str, Any] = {"upsert": True}
        if session is not None:
            update_options["session"] = session
        await self.collection.update_one(
            {"employee_id": employee_id, "date": normalize_mongo_value(metric_date)},
            {"$set": normalized, "$setOnInsert": set_on_insert}, **update_options
        )
        find_options = {"session": session} if session is not None else {}
        document = await self.collection.find_one(
            {"employee_id": employee_id, "date": normalize_mongo_value(metric_date)},
            **find_options,
        )
        return PerformanceMetricDocument.model_validate(document)
