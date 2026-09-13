from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.mongo_types import normalize_mongo_value
from app.core.pagination import Page, paginate_aggregate
from app.models.department import DepartmentDocument


class DepartmentRepository:
    def __init__(self, database: AsyncIOMotorDatabase) -> None:
        self.collection = database["departments"]
        self.employees = database["employees"]

    async def find_many(self, scope: ObjectId | None) -> list[DepartmentDocument]:
        query = {"_id": scope} if scope is not None else {}
        documents = await self.collection.find(query).sort("name", 1).to_list(length=None)
        return [DepartmentDocument.model_validate(document) for document in documents]

    async def find_many_page(
        self, scope: ObjectId | None, offset: int, limit: int
    ) -> Page[DepartmentDocument]:
        query = {"_id": scope} if scope is not None else {}
        total = await self.collection.count_documents(query)
        documents = (
            await self.collection.find(query)
            .sort("name", 1)
            .skip(offset)
            .limit(limit)
            .to_list(length=None)
        )
        return Page(
            items=[DepartmentDocument.model_validate(document) for document in documents],
            total=total,
        )

    async def find_many_page_v1(
        self, scope: ObjectId | None, page: int, page_size: int
    ) -> Page[DepartmentDocument]:
        query = {"_id": scope} if scope is not None else {}
        result = await paginate_aggregate(
            self.collection, query, {"name": 1}, page, page_size
        )
        return Page(
            items=[DepartmentDocument.model_validate(document) for document in result.items],
            total=result.total,
        )

    async def find_by_id(self, department_id: ObjectId) -> DepartmentDocument | None:
        document = await self.collection.find_one({"_id": department_id})
        return DepartmentDocument.model_validate(document) if document else None

    async def find_by_specialty(
        self, specialty: str, exclude_id: ObjectId
    ) -> list[DepartmentDocument]:
        documents = (
            await self.collection.find(
                {"is_active": True, "specialty": specialty, "_id": {"$ne": exclude_id}}
            )
            .sort("name", 1)
            .to_list(length=None)
        )
        return [DepartmentDocument.model_validate(document) for document in documents]

    async def insert(self, document: dict) -> DepartmentDocument:
        result = await self.collection.insert_one(normalize_mongo_value(document))
        created = await self.collection.find_one({"_id": result.inserted_id})
        return DepartmentDocument.model_validate(created)

    async def update(self, department_id: ObjectId, values: dict) -> DepartmentDocument | None:
        await self.collection.update_one(
            {"_id": department_id}, {"$set": normalize_mongo_value(values)}
        )
        return await self.find_by_id(department_id)

    async def delete(self, department_id: ObjectId) -> bool:
        result = await self.collection.delete_one({"_id": department_id})
        return result.deleted_count == 1

    async def count_employees(self, department_id: ObjectId) -> int:
        return await self.employees.count_documents({"department_id": department_id})
