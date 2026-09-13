from typing import Any

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.mongo_types import normalize_mongo_value
from app.core.pagination import Page, paginate_aggregate
from app.models.alert import AlertDocument


class AlertRepository:
    def __init__(self, database: AsyncIOMotorDatabase) -> None:
        self.collection = database["alerts"]

    async def ensure_indexes(self) -> None:
        await self.collection.create_index("fingerprint", unique=True)
        await self.collection.create_index([("department_id", 1), ("status", 1)])

    async def find_many(
        self,
        department_id: ObjectId | None,
        status: str | None = None,
        alert_type: str | None = None,
        limit: int | None = None,
    ) -> list[AlertDocument]:
        query: dict = {}
        if department_id is not None:
            query["department_id"] = department_id
        if status:
            query["status"] = status
        if alert_type:
            query["alert_type"] = alert_type
        cursor = self.collection.find(query).sort("created_at", -1)
        if limit is not None:
            cursor = cursor.limit(limit)
        documents = await cursor.to_list(length=None)
        return [AlertDocument.model_validate(document) for document in documents]

    async def find_many_page(
        self,
        department_id: ObjectId | None,
        status: str | None,
        alert_type: str | None,
        offset: int,
        limit: int,
    ) -> Page[AlertDocument]:
        query: dict = {}
        if department_id is not None:
            query["department_id"] = department_id
        if status:
            query["status"] = status
        if alert_type:
            query["alert_type"] = alert_type
        total = await self.collection.count_documents(query)
        documents = (
            await self.collection.find(query)
            .sort("created_at", -1)
            .skip(offset)
            .limit(limit)
            .to_list(length=None)
        )
        return Page(
            items=[AlertDocument.model_validate(document) for document in documents],
            total=total,
        )

    async def find_many_page_v1(
        self,
        department_id: ObjectId | None,
        status: str | None,
        alert_type: str | None,
        severity: str | None,
        created_at: dict[str, Any] | None,
        sort_stage: dict[str, int],
        page: int,
        page_size: int,
    ) -> Page[AlertDocument]:
        query: dict[str, Any] = {}
        if department_id is not None:
            query["department_id"] = department_id
        if status:
            query["status"] = status
        if alert_type:
            query["alert_type"] = alert_type
        if severity:
            query["severity"] = severity
        if created_at:
            query["created_at"] = created_at
        result = await paginate_aggregate(
            self.collection, query, sort_stage, page, page_size
        )
        return Page(
            items=[AlertDocument.model_validate(document) for document in result.items],
            total=result.total,
        )

    async def list_department_summaries(self) -> list[dict[str, Any]]:
        pipeline: list[dict[str, Any]] = [
            {
                "$group": {
                    "_id": "$department_id",
                    "total_count": {"$sum": 1},
                    "open_count": {"$sum": {"$cond": [{"$eq": ["$status", "open"]}, 1, 0]}},
                    "resolved_count": {"$sum": {"$cond": [{"$eq": ["$status", "resolved"]}, 1, 0]}},
                    "early_warning_count": {
                        "$sum": {"$cond": [{"$eq": ["$alert_type", "early_warning"]}, 1, 0]}
                    },
                    "overload_count": {
                        "$sum": {"$cond": [{"$eq": ["$alert_type", "overload"]}, 1, 0]}
                    },
                    "high_count": {"$sum": {"$cond": [{"$eq": ["$severity", "high"]}, 1, 0]}},
                    "latest_created_at": {"$max": "$created_at"},
                    "alert_ids": {"$push": {"$toString": "$_id"}},
                }
            },
            {
                "$lookup": {
                    "from": "departments",
                    "localField": "_id",
                    "foreignField": "_id",
                    "as": "department",
                }
            },
            {"$unwind": {"path": "$department", "preserveNullAndEmptyArrays": True}},
            {
                "$project": {
                    "_id": 0,
                    "department_id": {"$toString": "$_id"},
                    "department_name": {"$ifNull": ["$department.name", "Phòng ban chưa xác định"]},
                    "department_code": "$department.code",
                    "total_count": 1,
                    "open_count": 1,
                    "resolved_count": 1,
                    "early_warning_count": 1,
                    "overload_count": 1,
                    "high_count": 1,
                    "latest_created_at": 1,
                    "alert_ids": 1,
                }
            },
            {"$sort": {"latest_created_at": -1, "department_name": 1}},
        ]
        return await self.collection.aggregate(pipeline).to_list(None)

    async def list_department_summaries_page(
        self, offset: int, limit: int
    ) -> Page[dict[str, Any]]:
        pipeline: list[dict[str, Any]] = [
            {
                "$group": {
                    "_id": "$department_id",
                    "total_count": {"$sum": 1},
                    "open_count": {"$sum": {"$cond": [{"$eq": ["$status", "open"]}, 1, 0]}},
                    "resolved_count": {
                        "$sum": {"$cond": [{"$eq": ["$status", "resolved"]}, 1, 0]}
                    },
                    "early_warning_count": {
                        "$sum": {"$cond": [{"$eq": ["$alert_type", "early_warning"]}, 1, 0]}
                    },
                    "overload_count": {
                        "$sum": {"$cond": [{"$eq": ["$alert_type", "overload"]}, 1, 0]}
                    },
                    "high_count": {"$sum": {"$cond": [{"$eq": ["$severity", "high"]}, 1, 0]}},
                    "latest_created_at": {"$max": "$created_at"},
                    "alert_ids": {"$push": {"$toString": "$_id"}},
                }
            },
            {
                "$lookup": {
                    "from": "departments",
                    "localField": "_id",
                    "foreignField": "_id",
                    "as": "department",
                }
            },
            {"$unwind": {"path": "$department", "preserveNullAndEmptyArrays": True}},
            {
                "$project": {
                    "_id": 0,
                    "department_id": {"$toString": "$_id"},
                    "department_name": {"$ifNull": ["$department.name", "Phòng ban chưa xác định"]},
                    "department_code": "$department.code",
                    "total_count": 1,
                    "open_count": 1,
                    "resolved_count": 1,
                    "early_warning_count": 1,
                    "overload_count": 1,
                    "high_count": 1,
                    "latest_created_at": 1,
                    "alert_ids": 1,
                }
            },
            {"$sort": {"latest_created_at": -1, "department_name": 1}},
            {
                "$facet": {
                    "metadata": [{"$count": "total"}],
                    "items": [{"$skip": offset}, {"$limit": limit}],
                }
            },
        ]
        result = await self.collection.aggregate(pipeline).to_list(1)
        payload = result[0] if result else {}
        metadata = payload.get("metadata") or []
        return Page(items=payload.get("items") or [], total=metadata[0]["total"] if metadata else 0)

    async def find_by_id(self, alert_id: ObjectId) -> AlertDocument | None:
        document = await self.collection.find_one({"_id": alert_id})
        return AlertDocument.model_validate(document) if document else None

    async def find_by_fingerprint(self, fingerprint: str) -> AlertDocument | None:
        document = await self.collection.find_one({"fingerprint": fingerprint})
        return AlertDocument.model_validate(document) if document else None

    async def insert(self, document: dict) -> AlertDocument:
        result = await self.collection.insert_one(normalize_mongo_value(document))
        created = await self.collection.find_one({"_id": result.inserted_id})
        return AlertDocument.model_validate(created)

    async def update(self, alert_id: ObjectId, values: dict) -> AlertDocument | None:
        await self.collection.update_one({"_id": alert_id}, {"$set": normalize_mongo_value(values)})
        return await self.find_by_id(alert_id)

    async def resolve_if_open(
        self, alert_id: ObjectId, values: dict[str, Any]
    ) -> AlertDocument | None:
        """Resolve only an alert that is still open, avoiding a stale-read overwrite."""
        result = await self.collection.update_one(
            {"_id": alert_id, "status": {"$ne": "resolved"}},
            {"$set": normalize_mongo_value(values)},
        )
        if result.matched_count != 1:
            return None
        return await self.find_by_id(alert_id)
