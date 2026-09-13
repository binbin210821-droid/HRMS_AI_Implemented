from datetime import date as Date
from datetime import datetime
from typing import Any

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import UpdateOne
from pymongo.errors import OperationFailure

from app.core.mongo_types import normalize_mongo_value
from app.infrastructure.evidence_storage import validate_attachment_metadata
from app.models.task_execution import TaskExecutionReportDocument


class TaskExecutionRepository:
    """Truy vấn báo cáo thực thi task và review của quản lý."""

    def __init__(self, database: AsyncIOMotorDatabase) -> None:
        self.collection = database["task_execution_reports"]

    async def ensure_indexes(self) -> None:
        await self._ensure_seed_key_index()
        await self.collection.create_index(
            [("task_id", 1), ("work_date", 1)], unique=True
        )
        await self.collection.create_index([("employee_id", 1), ("work_date", -1)])
        await self.collection.create_index([("department_id", 1), ("work_date", -1)])

    async def _ensure_seed_key_index(self) -> None:
        """Giữ index seed tương thích với report nghiệp vụ không có seed_key.

        Một số database được tạo bởi script cũ có unique index không sparse. Khi
        report thật không có ``seed_key``, MongoDB coi giá trị thiếu là null và
        chỉ cho phép một report như vậy. Index có partial filter chỉ áp dụng cho
        seed_key dạng chuỗi, nên không ảnh hưởng report do Manager lưu.
        """
        list_indexes = getattr(self.collection, "list_indexes", None)
        if list_indexes is None:
            await self.collection.create_index(
                "seed_key",
                unique=True,
                partialFilterExpression={"seed_key": {"$type": "string"}},
            )
            return

        indexes = await list_indexes().to_list(None)
        expected_filter = {"seed_key": {"$type": "string"}}
        for index in indexes:
            if dict(index.get("key", {})) != {"seed_key": 1}:
                continue
            if (
                index.get("unique") is True
                and index.get("partialFilterExpression") == expected_filter
            ):
                return
            try:
                await self.collection.drop_index(index["name"])
            except OperationFailure:
                # Có thể worker khác vừa hoàn tất migration index.
                pass

        await self.collection.create_index(
            "seed_key",
            unique=True,
            partialFilterExpression=expected_filter,
        )

    @staticmethod
    def _date_value(value: Date) -> datetime:
        return normalize_mongo_value(value)

    async def list_for_employee_date(
        self, employee_id: ObjectId, work_date: Date
    ) -> list[TaskExecutionReportDocument]:
        documents = await self.collection.find(
            {"employee_id": employee_id, "work_date": self._date_value(work_date)}
        ).to_list(None)
        return [TaskExecutionReportDocument.model_validate(document) for document in documents]

    async def find_by_task_date(
        self, task_id: ObjectId, work_date: Date
    ) -> TaskExecutionReportDocument | None:
        document = await self.collection.find_one(
            {"task_id": task_id, "work_date": self._date_value(work_date)}
        )
        return TaskExecutionReportDocument.model_validate(document) if document else None

    async def upsert_report(self, document: dict[str, Any]) -> TaskExecutionReportDocument:
        values = normalize_mongo_value(document)
        for attachment in values.get("attachments", []):
            validate_attachment_metadata(attachment)
        task_id = values["task_id"]
        work_date = values["work_date"]
        await self.collection.update_one(
            {"task_id": task_id, "work_date": work_date},
            {"$set": values, "$setOnInsert": {"_id": values.get("_id", ObjectId())}},
            upsert=True,
        )
        created = await self.collection.find_one({"task_id": task_id, "work_date": work_date})
        return TaskExecutionReportDocument.model_validate(created)

    async def update_manager_review(
        self,
        report_id: ObjectId,
        review: dict[str, Any],
        updated_at: datetime,
    ) -> TaskExecutionReportDocument | None:
        result = await self.collection.update_one(
            {"_id": report_id},
            {"$set": normalize_mongo_value({"manager_review": review, "updated_at": updated_at})},
        )
        if result.modified_count != 1:
            return None
        document = await self.collection.find_one({"_id": report_id})
        return TaskExecutionReportDocument.model_validate(document) if document else None

    async def bulk_update_manager_reviews(
        self, entries: list[dict[str, Any]], session: Any | None = None
    ) -> dict[ObjectId, TaskExecutionReportDocument]:
        if not entries:
            return {}
        operations = []
        task_ids: list[ObjectId] = []
        work_date = None
        for entry in entries:
            report = entry.get("report")
            placeholder = normalize_mongo_value(entry["placeholder"])
            for attachment in placeholder.get("attachments", []):
                validate_attachment_metadata(attachment)
            review = normalize_mongo_value(entry["review"])
            updated_at = entry["updated_at"]
            task_ids.append(placeholder["task_id"])
            work_date = placeholder["work_date"]
            if report is not None:
                query = {"_id": report.id}
                set_on_insert: dict[str, Any] = {}
            else:
                query = {
                    "task_id": placeholder["task_id"],
                    "work_date": placeholder["work_date"],
                }
                set_on_insert = {
                    key: value
                    for key, value in placeholder.items()
                    if key not in {"_id", "updated_at"}
                }
                set_on_insert["_id"] = placeholder.get("_id", ObjectId())
            update: dict[str, Any] = {
                "$set": {"manager_review": review, "updated_at": updated_at}
            }
            if report is None:
                update["$setOnInsert"] = set_on_insert
            operations.append(UpdateOne(query, update, upsert=report is None))
        write_options: dict[str, Any] = {"ordered": True}
        if session is not None:
            write_options["session"] = session
        await self.collection.bulk_write(operations, **write_options)
        find_options = {"session": session} if session is not None else {}
        documents = await self.collection.find(
            {"task_id": {"$in": task_ids}, "work_date": work_date}, **find_options
        ).to_list(None)
        reports = [TaskExecutionReportDocument.model_validate(document) for document in documents]
        return {report.task_id: report for report in reports}


__all__ = ["TaskExecutionRepository"]
