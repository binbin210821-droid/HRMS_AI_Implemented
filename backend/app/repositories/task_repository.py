from datetime import date, datetime, timedelta
from typing import Any

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import InsertOne

from app.core.mongo_types import normalize_mongo_value, to_mongo_datetime
from app.core.pagination import Page, paginate_aggregate
from app.core.time import business_clock
from app.models.department import DepartmentDocument
from app.models.employee import EmployeeDocument
from app.models.task import DepartmentTaskDirectiveDocument, TaskDocument
from app.models.user import UserDocument


class TaskRepository:
    """Mongo queries dedicated to employee tasks and deadlines."""

    def __init__(self, database: AsyncIOMotorDatabase) -> None:
        self.collection = database["tasks"]
        self.employees = database["employees"]
        self.departments = database["departments"]
        self.users = database["users"]
        self.directives = database["department_task_directives"]
        self.audit_logs = database["audit_logs"]

    async def ensure_indexes(self) -> None:
        await self.collection.create_index(
            "seed_key",
            unique=True,
            partialFilterExpression={"seed_key": {"$exists": True}},
        )
        await self.collection.create_index([("department_id", 1), ("due_date", 1)])
        await self.collection.create_index([("employee_id", 1), ("status", 1)])
        await self.directives.create_index(
            [("target_department_id", 1), ("status", 1), ("focus", 1)],
            name="pending_task_directive_focus_unique",
            unique=True,
            partialFilterExpression={"status": "pending"},
        )
        # Không tạo unique index trên task_ids: một task được phép xuất hiện
        # trong chỉ thị mới sau khi chỉ thị cũ đã accepted. Việc chặn phát hành
        # chỉ thị trùng đang được áp dụng theo ACTIVE_DIRECTIVE_STATUSES ở service.
        await self.directives.create_index(
            [("target_department_id", 1), ("issued_at", -1)]
        )
        await self.audit_logs.create_index([("action", 1), ("created_at", -1)])

    async def find_employee(
        self, employee_id: ObjectId, scope: ObjectId | None = None
    ) -> EmployeeDocument | None:
        query: dict[str, Any] = {"_id": employee_id, "is_active": True}
        if scope is not None:
            query["department_id"] = scope
        document = await self.employees.find_one(query)
        return EmployeeDocument.model_validate(document) if document else None

    async def find_many(
        self,
        scope: ObjectId | None,
        employee_id: ObjectId | None = None,
        status: str | None = None,
        overdue_only: bool = False,
    ) -> list[TaskDocument]:
        query: dict[str, Any] = {}
        if scope is not None:
            query["department_id"] = scope
        if employee_id is not None:
            query["employee_id"] = employee_id
        if status:
            query["status"] = status
        if overdue_only:
            today = business_clock.today()
            query["due_date"] = {"$lt": to_mongo_datetime(today)}
            query["status"] = {"$ne": "done"}
        documents = (
            await self.collection.find(query)
            .sort([("due_date", 1), ("created_at", -1)])
            .to_list(None)
        )
        return [TaskDocument.model_validate(document) for document in documents]

    async def find_many_page(
        self,
        scope: ObjectId | None,
        employee_id: ObjectId | None = None,
        status: str | None = None,
        overdue_only: bool = False,
        offset: int = 0,
        limit: int = 100,
    ) -> Page[TaskDocument]:
        query: dict[str, Any] = {}
        if scope is not None:
            query["department_id"] = scope
        if employee_id is not None:
            query["employee_id"] = employee_id
        if status:
            query["status"] = status
        if overdue_only:
            today = business_clock.today()
            query["due_date"] = {"$lt": to_mongo_datetime(today)}
            query["status"] = {"$ne": "done"}
        total = await self.collection.count_documents(query)
        documents = (
            await self.collection.find(query)
            .sort([("due_date", 1), ("created_at", -1)])
            .skip(offset)
            .limit(limit)
            .to_list(None)
        )
        return Page(
            items=[TaskDocument.model_validate(document) for document in documents],
            total=total,
        )

    async def find_many_page_v1(
        self,
        scope: ObjectId | None,
        employee_id: ObjectId | None,
        department_id: ObjectId | None,
        status: str | None,
        overdue_only: bool,
        due_date: dict[str, datetime] | None,
        excluded_task_ids: set[ObjectId] | None,
        sort_stage: dict[str, int],
        page: int,
        page_size: int,
    ) -> Page[TaskDocument]:
        query: dict[str, Any] = {}
        if scope is not None:
            query["department_id"] = scope
        elif department_id is not None:
            query["department_id"] = department_id
        if employee_id is not None:
            query["employee_id"] = employee_id
        if status:
            query["status"] = status
        if overdue_only:
            query["status"] = {"$ne": "done"}
            today_cutoff = to_mongo_datetime(business_clock.today())
            if due_date is None:
                due_date = {"$lt": today_cutoff}
            else:
                due_date = dict(due_date)
                current_cutoff = due_date.get("$lt")
                if current_cutoff is None or today_cutoff < current_cutoff:
                    due_date["$lt"] = today_cutoff
        if due_date:
            query["due_date"] = due_date
        if excluded_task_ids:
            query["_id"] = {"$nin": list(excluded_task_ids)}
        result = await paginate_aggregate(
            self.collection, query, sort_stage, page, page_size
        )
        return Page(
            items=[TaskDocument.model_validate(document) for document in result.items],
            total=result.total,
        )

    async def find_department_tasks(self, department_id: ObjectId) -> list[TaskDocument]:
        documents = (
            await self.collection.find({"department_id": department_id})
            .sort([("due_date", 1), ("created_at", -1)])
            .to_list(None)
        )
        return [TaskDocument.model_validate(document) for document in documents]

    async def find_tasks_by_ids(self, task_ids: list[ObjectId]) -> list[TaskDocument]:
        if not task_ids:
            return []
        documents = await self.collection.find({"_id": {"$in": task_ids}}).to_list(None)
        return [TaskDocument.model_validate(document) for document in documents]

    async def find_tasks_for_review(
        self, employee_id: ObjectId, review_date: date
    ) -> list[TaskDocument]:
        start = to_mongo_datetime(review_date)
        end = to_mongo_datetime(review_date + timedelta(days=1))
        documents = await self.collection.find(
            {
                "employee_id": employee_id,
                "$or": [
                    {"completed_at": {"$gte": start, "$lt": end}},
                    {"created_at": {"$gte": start, "$lt": end}},
                    {"updated_at": {"$gte": start, "$lt": end}},
                ],
            }
        ).sort([("due_date", 1), ("created_at", 1)]).to_list(None)
        return [TaskDocument.model_validate(document) for document in documents]

    async def list_departments(self) -> list[DepartmentDocument]:
        documents = await self.departments.find({"is_active": True}).sort("name", 1).to_list(None)
        return [DepartmentDocument.model_validate(document) for document in documents]

    async def find_department(self, department_id: ObjectId) -> DepartmentDocument | None:
        document = await self.departments.find_one({"_id": department_id, "is_active": True})
        return DepartmentDocument.model_validate(document) if document else None

    async def list_active_managers(self) -> list[UserDocument]:
        documents = await self.users.find({"role": "manager", "is_active": True}).to_list(None)
        return [UserDocument.model_validate(document) for document in documents]

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

    async def list_directed_task_ids(self, statuses: set[str] | None = None) -> set[ObjectId]:
        query: dict[str, Any] = {"status": {"$in": list(statuses)}} if statuses else {}
        values = await self.directives.distinct("task_ids", query)
        return {value for value in values if isinstance(value, ObjectId)}

    async def insert_department_directive(
        self, document: dict[str, Any]
    ) -> DepartmentTaskDirectiveDocument:
        result = await self.directives.insert_one(normalize_mongo_value(document))
        created = await self.directives.find_one({"_id": result.inserted_id})
        return DepartmentTaskDirectiveDocument.model_validate(created)

    async def append_department_directive_tasks(
        self, directive_id: ObjectId, task_ids: list[ObjectId]
    ) -> DepartmentTaskDirectiveDocument | None:
        """Bổ sung việc mới vào chỉ thị đang chờ cùng phòng ban/nhóm."""
        if not task_ids:
            return await self.find_department_directive(directive_id)
        result = await self.directives.update_one(
            {"_id": directive_id, "status": "pending"},
            [
                {
                    "$set": {
                        "task_ids": {"$setUnion": ["$task_ids", task_ids]},
                    }
                },
                {
                    "$set": {
                        "selected_task_count": {"$size": "$task_ids"},
                    }
                },
            ],
        )
        if result.modified_count != 1:
            return None
        return await self.find_department_directive(directive_id)

    async def find_department_directive(
        self, directive_id: ObjectId
    ) -> DepartmentTaskDirectiveDocument | None:
        document = await self.directives.find_one({"_id": directive_id})
        return DepartmentTaskDirectiveDocument.model_validate(document) if document else None

    async def list_department_directives(
        self, target_department_id: ObjectId | None, status: str | None = None
    ) -> list[DepartmentTaskDirectiveDocument]:
        query: dict[str, Any] = {}
        if target_department_id is not None:
            query["target_department_id"] = target_department_id
        if status:
            query["status"] = status
        documents = (
            await self.directives.find(query)
            .sort([("issued_at", -1), ("_id", -1)])
            .to_list(None)
        )
        return [DepartmentTaskDirectiveDocument.model_validate(document) for document in documents]

    async def list_department_directives_page(
        self,
        target_department_id: ObjectId | None,
        status: str | None,
        offset: int,
        limit: int,
    ) -> Page[DepartmentTaskDirectiveDocument]:
        query: dict[str, Any] = {}
        if target_department_id is not None:
            query["target_department_id"] = target_department_id
        if status:
            query["status"] = status
        total = await self.directives.count_documents(query)
        documents = (
            await self.directives.find(query)
            .sort([("issued_at", -1), ("_id", -1)])
            .skip(offset)
            .limit(limit)
            .to_list(None)
        )
        return Page(
            items=[DepartmentTaskDirectiveDocument.model_validate(document) for document in documents],
            total=total,
        )

    async def acknowledge_department_directive(
        self,
        directive_id: ObjectId,
        acknowledged_by: ObjectId,
        acknowledged_at: datetime,
        action_note: str,
        commitment_date: date,
    ) -> DepartmentTaskDirectiveDocument | None:
        result = await self.directives.update_one(
            {"_id": directive_id, "status": "pending"},
            {
                "$set": normalize_mongo_value(
                    {
                        "status": "acknowledged",
                        "acknowledged_by": acknowledged_by,
                        "acknowledged_at": acknowledged_at,
                        "action_note": action_note,
                        "commitment_date": commitment_date,
                    }
                )
            },
        )
        if result.modified_count != 1:
            return None
        return await self.find_department_directive(directive_id)

    async def transition_department_directive(
        self,
        directive_id: ObjectId,
        expected_statuses: list[str],
        values: dict[str, Any],
    ) -> DepartmentTaskDirectiveDocument | None:
        result = await self.directives.update_one(
            {"_id": directive_id, "status": {"$in": expected_statuses}},
            {"$set": normalize_mongo_value(values)},
        )
        if result.modified_count != 1:
            return None
        return await self.find_department_directive(directive_id)

    async def insert_audit_log(self, document: dict[str, Any]) -> None:
        await self.audit_logs.insert_one(normalize_mongo_value(document))

    async def insert_audit_logs(
        self, documents: list[dict[str, Any]], session: Any | None = None
    ) -> None:
        if not documents:
            return
        options: dict[str, Any] = {"ordered": True}
        if session is not None:
            options["session"] = session
        await self.audit_logs.bulk_write(
            [InsertOne(normalize_mongo_value(document)) for document in documents], **options
        )

    async def find_by_id(
        self, task_id: ObjectId, scope: ObjectId | None = None
    ) -> TaskDocument | None:
        query: dict[str, Any] = {"_id": task_id}
        if scope is not None:
            query["department_id"] = scope
        document = await self.collection.find_one(query)
        return TaskDocument.model_validate(document) if document else None

    async def insert(self, document: dict[str, Any]) -> TaskDocument:
        result = await self.collection.insert_one(normalize_mongo_value(document))
        created = await self.collection.find_one({"_id": result.inserted_id})
        return TaskDocument.model_validate(created)

    async def update(
        self,
        task_id: ObjectId,
        values: dict[str, Any],
        scope: ObjectId | None = None,
        expected_updated_at: datetime | None = None,
    ) -> TaskDocument | None:
        query: dict[str, Any] = {"_id": task_id}
        if scope is not None:
            query["department_id"] = scope
        if expected_updated_at is not None:
            query["updated_at"] = to_mongo_datetime(expected_updated_at)
        result = await self.collection.update_one(query, {"$set": normalize_mongo_value(values)})
        if result.matched_count != 1:
            return None
        return await self.find_by_id(task_id, scope)

    async def delete(self, task_id: ObjectId, scope: ObjectId | None = None) -> bool:
        query: dict[str, Any] = {"_id": task_id}
        if scope is not None:
            query["department_id"] = scope
        result = await self.collection.delete_one(query)
        return result.deleted_count == 1


__all__ = ["TaskRepository"]
