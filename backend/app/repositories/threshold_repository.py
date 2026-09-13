from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.mongo_types import normalize_mongo_value
from app.core.pagination import Page
from app.models.threshold import ThresholdConfigDocument, ThresholdConfigStatus


class ThresholdConfigRepository:
    def __init__(self, database: AsyncIOMotorDatabase) -> None:
        self.collection = database["threshold_configs"]

    async def ensure_indexes(self) -> None:
        await self.collection.create_index(
            [("department_id", 1), ("status", 1), ("updated_at", -1)],
            name="threshold_department_status_updated",
        )
        await self.collection.create_index(
            [("created_at", -1)],
            name="threshold_created_at",
        )

    async def find_many(self, department_id: ObjectId | None) -> list[ThresholdConfigDocument]:
        query = {"department_id": department_id} if department_id is not None else {}
        documents = await self.collection.find(query).sort("created_at", -1).to_list(length=None)
        return [ThresholdConfigDocument.model_validate(document) for document in documents]

    async def find_many_page(
        self, department_id: ObjectId | None, offset: int, limit: int
    ) -> Page[ThresholdConfigDocument]:
        query = {"department_id": department_id} if department_id is not None else {}
        total = await self.collection.count_documents(query)
        documents = (
            await self.collection.find(query)
            .sort("created_at", -1)
            .skip(offset)
            .limit(limit)
            .to_list(length=None)
        )
        return Page(
            items=[ThresholdConfigDocument.model_validate(document) for document in documents],
            total=total,
        )

    async def find_approved(self, department_id: ObjectId | None) -> ThresholdConfigDocument | None:
        query: dict[str, object] = {"status": ThresholdConfigStatus.APPROVED.value}
        query["$or"] = [{"department_id": department_id}, {"department_id": None}]
        document = await self.collection.find_one(query, sort=[("updated_at", -1)])
        return ThresholdConfigDocument.model_validate(document) if document else None

    async def insert(self, document: dict) -> ThresholdConfigDocument:
        result = await self.collection.insert_one(normalize_mongo_value(document))
        created = await self.collection.find_one({"_id": result.inserted_id})
        return ThresholdConfigDocument.model_validate(created)

    async def find_by_id(self, config_id: ObjectId) -> ThresholdConfigDocument | None:
        document = await self.collection.find_one({"_id": config_id})
        return ThresholdConfigDocument.model_validate(document) if document else None

    async def approve(
        self, config_id: ObjectId, approver_id: ObjectId, updated_at
    ) -> ThresholdConfigDocument | None:
        await self.collection.update_one(
            {"_id": config_id},
            {
                "$set": {
                    "status": ThresholdConfigStatus.APPROVED.value,
                    "approved_by": approver_id,
                    "updated_at": normalize_mongo_value(updated_at),
                }
            },
        )
        return await self.find_by_id(config_id)
