from datetime import date as Date
from datetime import datetime, time, timedelta, timezone
from typing import Any

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import OperationFailure

from app.core.mongo_types import normalize_mongo_value
from app.models.alert import AlertDocument
from app.models.coordination import (
    CoordinationDirectiveDocument,
    CoordinationPlanDocument,
    DepartmentAlertDirectiveDocument,
)
from app.models.department import DepartmentDocument
from app.models.employee import EmployeeDocument
from app.models.overload import WorkloadCandidateResponse
from app.models.user import UserDocument


class CoordinationRepository:
    """Mongo queries dedicated to workload coordination and its audit trail."""

    def __init__(self, database: AsyncIOMotorDatabase) -> None:
        self.alerts = database["alerts"]
        self.metrics = database["performance_metrics"]
        self.employees = database["employees"]
        self.plans = database["coordination_plans"]
        self.directives = database["coordination_directives"]
        self.department_directives = database["department_alert_directives"]
        self.departments = database["departments"]
        self.users = database["users"]
        self.audit_logs = database["audit_logs"]

    async def ensure_indexes(self) -> None:
        await self.plans.create_index("alert_id", unique=True)
        await self.plans.create_index([("department_id", 1), ("created_at", -1)])
        await self.directives.create_index("alert_id", unique=True)
        await self.directives.create_index([("target_department_id", 1), ("status", 1)])
        try:
            await self.department_directives.drop_index("target_department_id_1_status_1")
        except OperationFailure:
            pass
        await self.department_directives.create_index(
            [
                ("target_department_id", 1),
                ("status", 1),
                ("selected_alert_type", 1),
                ("selected_severity", 1),
            ],
            name="pending_department_directive_filters_unique",
            unique=True,
            partialFilterExpression={"status": "pending"},
        )
        await self.department_directives.create_index([("department_id", 1), ("issued_at", -1)])
        await self.audit_logs.create_index([("action", 1), ("created_at", -1)])

    async def list_alerts(self, department_id: ObjectId | None) -> list[AlertDocument]:
        query: dict[str, Any] = {}
        if department_id is not None:
            query["department_id"] = department_id
        documents = await self.alerts.find(query).sort("created_at", -1).to_list(None)
        return [AlertDocument.model_validate(document) for document in documents]

    async def find_alert(self, alert_id: ObjectId) -> AlertDocument | None:
        document = await self.alerts.find_one({"_id": alert_id})
        return AlertDocument.model_validate(document) if document else None

    async def list_alerts_by_department(
        self,
        department_id: ObjectId,
        status: str | None = None,
        alert_type: str | None = None,
        severity: str | None = None,
    ) -> list[AlertDocument]:
        query: dict[str, Any] = {"department_id": department_id}
        if status is not None:
            query["status"] = status
        if alert_type is not None:
            query["alert_type"] = alert_type
        if severity is not None:
            query["severity"] = severity
        documents = await self.alerts.find(query).sort("created_at", -1).to_list(None)
        return [AlertDocument.model_validate(document) for document in documents]

    async def find_alerts_by_ids(self, alert_ids: list[ObjectId]) -> list[AlertDocument]:
        if not alert_ids:
            return []
        documents = await self.alerts.find({"_id": {"$in": alert_ids}}).to_list(None)
        return [AlertDocument.model_validate(document) for document in documents]

    async def find_department(self, department_id: ObjectId) -> DepartmentDocument | None:
        document = await self.departments.find_one({"_id": department_id})
        return DepartmentDocument.model_validate(document) if document else None

    async def find_active_manager_by_department(
        self, department_id: ObjectId
    ) -> UserDocument | None:
        document = await self.users.find_one(
            {"role": "manager", "department_id": department_id, "is_active": True}
        )
        return UserDocument.model_validate(document) if document else None

    async def find_user(self, user_id: ObjectId) -> UserDocument | None:
        document = await self.users.find_one({"_id": user_id})
        return UserDocument.model_validate(document) if document else None

    async def find_employee(self, employee_id: ObjectId) -> EmployeeDocument | None:
        document = await self.employees.find_one({"_id": employee_id})
        return EmployeeDocument.model_validate(document) if document else None

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
        """Load candidates once for all alerts sharing a department/date group."""
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

    async def count_rebalance_capacity_by_department(
        self, department_ids: list[ObjectId], metric_date: Date
    ) -> dict[str, int]:
        if not department_ids:
            return {}
        start = datetime.combine(metric_date, time.min, tzinfo=timezone.utc)
        end = start + timedelta(days=1)
        pipeline: list[dict[str, Any]] = [
            {
                "$match": {
                    "date": {"$gte": start, "$lt": end},
                    "tasks_completed": {"$lte": 2},
                    "quality_score": {"$gte": 80},
                }
            },
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
                    "employee.department_id": {"$in": department_ids},
                    "employee.is_active": True,
                }
            },
            {
                "$group": {
                    "_id": "$employee.department_id",
                    "employee_ids": {"$addToSet": "$employee_id"},
                }
            },
            {
                "$project": {
                    "_id": 1,
                    "available_employee_count": {"$size": "$employee_ids"},
                }
            },
        ]
        documents = await self.metrics.aggregate(pipeline).to_list(None)
        return {
            str(document["_id"]): int(document["available_employee_count"])
            for document in documents
        }

    async def find_plan(self, alert_id: ObjectId) -> CoordinationPlanDocument | None:
        document = await self.plans.find_one({"alert_id": alert_id})
        return CoordinationPlanDocument.model_validate(document) if document else None

    async def find_plans(
        self, alert_ids: list[ObjectId]
    ) -> dict[ObjectId, CoordinationPlanDocument]:
        if not alert_ids:
            return {}
        documents = await self.plans.find({"alert_id": {"$in": alert_ids}}).to_list(None)
        plans = [CoordinationPlanDocument.model_validate(document) for document in documents]
        return {plan.alert_id: plan for plan in plans}

    async def insert_plan(self, document: dict[str, Any]) -> CoordinationPlanDocument:
        result = await self.plans.insert_one(normalize_mongo_value(document))
        created = await self.plans.find_one({"_id": result.inserted_id})
        return CoordinationPlanDocument.model_validate(created)

    async def insert_directive(self, document: dict[str, Any]) -> CoordinationDirectiveDocument:
        result = await self.directives.insert_one(normalize_mongo_value(document))
        created = await self.directives.find_one({"_id": result.inserted_id})
        return CoordinationDirectiveDocument.model_validate(created)

    async def insert_department_directive(
        self, document: dict[str, Any]
    ) -> DepartmentAlertDirectiveDocument:
        result = await self.department_directives.insert_one(normalize_mongo_value(document))
        created = await self.department_directives.find_one({"_id": result.inserted_id})
        return DepartmentAlertDirectiveDocument.model_validate(created)

    async def find_department_directive(
        self, directive_id: ObjectId
    ) -> DepartmentAlertDirectiveDocument | None:
        document = await self.department_directives.find_one({"_id": directive_id})
        return DepartmentAlertDirectiveDocument.model_validate(document) if document else None

    async def find_pending_department_directive(
        self,
        department_id: ObjectId,
        alert_type: str | None = None,
        severity: str | None = None,
    ) -> DepartmentAlertDirectiveDocument | None:
        query: dict[str, Any] = {"target_department_id": department_id, "status": "pending"}
        if alert_type is not None:
            query["selected_alert_type"] = alert_type
        if severity is not None:
            query["selected_severity"] = severity
        document = await self.department_directives.find_one(query)
        return DepartmentAlertDirectiveDocument.model_validate(document) if document else None

    async def list_pending_department_directives(
        self, department_id: ObjectId
    ) -> list[DepartmentAlertDirectiveDocument]:
        documents = (
            await self.department_directives.find(
                {"target_department_id": department_id, "status": "pending"}
            )
            .sort("issued_at", -1)
            .to_list(None)
        )
        return [DepartmentAlertDirectiveDocument.model_validate(document) for document in documents]

    async def list_department_directives(
        self, target_department_id: ObjectId | None, status: str | None = None
    ) -> list[DepartmentAlertDirectiveDocument]:
        query: dict[str, Any] = {}
        if target_department_id is not None:
            query["target_department_id"] = target_department_id
        if status is not None:
            query["status"] = status
        documents = await self.department_directives.find(query).sort("issued_at", -1).to_list(None)
        return [DepartmentAlertDirectiveDocument.model_validate(document) for document in documents]

    async def acknowledge_department_directive(
        self,
        directive_id: ObjectId,
        acknowledged_by: ObjectId,
        acknowledged_at: datetime,
        acknowledgement_note: str | None,
        commitment_date,
    ) -> DepartmentAlertDirectiveDocument | None:
        await self.department_directives.update_one(
            {"_id": directive_id, "status": "pending"},
            {
                "$set": normalize_mongo_value(
                    {
                        "status": "acknowledged",
                        "acknowledged_by": acknowledged_by,
                        "acknowledged_at": acknowledged_at,
                        "acknowledgement_note": acknowledgement_note,
                        "commitment_date": commitment_date,
                    }
                )
            },
        )
        return await self.find_department_directive(directive_id)

    async def transition_department_directive(
        self,
        directive_id: ObjectId,
        expected_statuses: list[str],
        values: dict[str, Any],
    ) -> DepartmentAlertDirectiveDocument | None:
        result = await self.department_directives.update_one(
            {"_id": directive_id, "status": {"$in": expected_statuses}},
            {"$set": normalize_mongo_value(values)},
        )
        if result.modified_count != 1:
            return None
        return await self.find_department_directive(directive_id)

    async def find_directive(self, directive_id: ObjectId) -> CoordinationDirectiveDocument | None:
        document = await self.directives.find_one({"_id": directive_id})
        return CoordinationDirectiveDocument.model_validate(document) if document else None

    async def find_directive_by_alert(
        self, alert_id: ObjectId
    ) -> CoordinationDirectiveDocument | None:
        document = await self.directives.find_one({"alert_id": alert_id})
        return CoordinationDirectiveDocument.model_validate(document) if document else None

    async def list_directives(
        self, target_department_id: ObjectId | None, status: str | None = None
    ) -> list[CoordinationDirectiveDocument]:
        query: dict[str, Any] = {}
        if target_department_id is not None:
            query["target_department_id"] = target_department_id
        if status:
            query["status"] = status
        documents = await self.directives.find(query).sort("issued_at", -1).to_list(None)
        return [CoordinationDirectiveDocument.model_validate(document) for document in documents]

    async def mark_directive_fulfilled(
        self,
        directive_id: ObjectId,
        plan_id: ObjectId,
        fulfilled_by: ObjectId,
        fulfilled_at: datetime,
    ) -> CoordinationDirectiveDocument | None:
        await self.directives.update_one(
            {"_id": directive_id, "status": "pending"},
            {
                "$set": normalize_mongo_value(
                    {
                        "status": "fulfilled",
                        "fulfilled_plan_id": plan_id,
                        "fulfilled_by": fulfilled_by,
                        "fulfilled_at": fulfilled_at,
                    }
                )
            },
        )
        return await self.find_directive(directive_id)

    async def insert_audit_log(self, document: dict[str, Any]) -> None:
        await self.audit_logs.insert_one(normalize_mongo_value(document))

    async def resolve_alert_for_coordination(
        self,
        alert_id: ObjectId,
        resolved_by: ObjectId,
        resolution_note: str,
        resolved_at: datetime,
    ) -> AlertDocument | None:
        await self.alerts.update_one(
            {"_id": alert_id, "status": "open"},
            {
                "$set": normalize_mongo_value(
                    {
                        "status": "resolved",
                        "resolution_note": resolution_note,
                        "resolved_by": resolved_by,
                        "resolved_at": resolved_at,
                        "updated_at": resolved_at,
                    }
                )
            },
        )
        return await self.find_alert(alert_id)


__all__ = ["CoordinationRepository"]
