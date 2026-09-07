from datetime import datetime
from typing import Any

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.mongo_types import normalize_mongo_value
from app.models.attachment import UploadSessionDocument


class AttachmentUploadRepository:
    """MongoDB access for temporary direct-upload sessions."""

    def __init__(self, database: AsyncIOMotorDatabase) -> None:
        self.sessions = database["attachment_upload_sessions"]
        self.departments = database["departments"]
        self.tasks = database["tasks"]

    async def ensure_indexes(self) -> None:
        await self.sessions.create_index("expires_at", name="attachment_upload_expiry")
        await self.sessions.create_index(
            [("owner_id", 1), ("status", 1)], name="attachment_upload_owner_status"
        )
        await self.sessions.create_index(
            [("generated_storage_key", 1), ("status", 1)],
            name="attachment_upload_storage_status",
            unique=True,
        )

    async def insert(self, values: dict[str, Any]) -> UploadSessionDocument:
        await self.sessions.insert_one(normalize_mongo_value(values))
        return UploadSessionDocument.model_validate(values)

    async def find_by_id(self, session_id: str) -> UploadSessionDocument | None:
        document = await self.sessions.find_one({"_id": session_id})
        return UploadSessionDocument.model_validate(document) if document else None

    async def find_uploaded_for_owner(
        self, session_ids: list[str], owner_id: str
    ) -> list[UploadSessionDocument]:
        documents = await self.sessions.find(
            {
                "_id": {"$in": session_ids},
                "owner_id": owner_id,
                "status": "uploaded",
            }
        ).to_list(None)
        return [UploadSessionDocument.model_validate(item) for item in documents]

    async def find_for_owner(
        self, session_ids: list[str], owner_id: str
    ) -> list[UploadSessionDocument]:
        documents = await self.sessions.find(
            {"_id": {"$in": session_ids}, "owner_id": owner_id}
        ).to_list(None)
        return [UploadSessionDocument.model_validate(item) for item in documents]

    async def department_is_active(self, department_id: ObjectId) -> bool:
        return bool(await self.departments.find_one({"_id": department_id, "is_active": True}, {"_id": 1}))

    async def task_belongs_to_department(
        self, task_id: ObjectId, department_id: ObjectId
    ) -> bool:
        return bool(await self.tasks.find_one({"_id": task_id, "department_id": department_id}, {"_id": 1}))

    async def update_status(
        self, session_id: str, status: str, updated_at: datetime
    ) -> UploadSessionDocument | None:
        await self.sessions.update_one(
            {"_id": session_id},
            {"$set": {"status": status, "updated_at": updated_at}},
        )
        return await self.find_by_id(session_id)

    async def mark_committed(self, session_ids: list[str], now: datetime) -> None:
        await self.sessions.update_many(
            {"_id": {"$in": session_ids}, "status": "uploaded"},
            {"$set": {"status": "committed", "updated_at": now}},
        )

    async def mark_failed(self, session_ids: list[str], now: datetime) -> None:
        await self.sessions.update_many(
            {"_id": {"$in": session_ids}, "status": {"$in": ["pending", "uploaded"]}},
            {"$set": {"status": "failed", "updated_at": now}},
        )

    async def delete_expired(self, now: datetime) -> list[UploadSessionDocument]:
        cursor = self.sessions.find(
            {"expires_at": {"$lt": now}, "status": {"$in": ["pending", "uploaded"]}}
        )
        documents = [UploadSessionDocument.model_validate(item) async for item in cursor]
        if documents:
            await self.sessions.update_many(
                {"_id": {"$in": [item.id for item in documents]}},
                {"$set": {"status": "expired", "updated_at": now}},
            )
        return documents


__all__ = ["AttachmentUploadRepository"]
