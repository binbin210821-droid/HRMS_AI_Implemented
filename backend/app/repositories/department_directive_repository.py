from typing import Any

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase


class DepartmentDirectiveRepository:
    """Read-only queries for department-level directives used by dashboard projections."""

    def __init__(self, database: AsyncIOMotorDatabase) -> None:
        self.collection = database["department_alert_directives"]

    async def list_alert_ids(self, target_department_id: ObjectId | None) -> set[ObjectId]:
        query: dict[str, Any] = {}
        if target_department_id is not None:
            query["target_department_id"] = target_department_id

        documents = await self.collection.find(query, {"alert_ids": 1}).to_list(None)
        return {
            alert_id
            for document in documents
            for alert_id in document.get("alert_ids", [])
            if isinstance(alert_id, ObjectId)
        }


__all__ = ["DepartmentDirectiveRepository"]
