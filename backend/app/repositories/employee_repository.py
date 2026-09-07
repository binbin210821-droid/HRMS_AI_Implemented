from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.mongo_types import normalize_mongo_value
from app.models.employee import EmployeeDocument


class EmployeeRepository:
    def __init__(self, database: AsyncIOMotorDatabase) -> None:
        self.collection = database["employees"]
        self.departments = database["departments"]

    async def department_exists(self, department_id: ObjectId) -> bool:
        return await self.departments.count_documents({"_id": department_id}, limit=1) == 1

    async def find_many(
        self, scope: ObjectId | None, department_id: ObjectId | None = None
    ) -> list[EmployeeDocument]:
        query: dict = {}
        if scope is not None:
            query["department_id"] = scope
        elif department_id is not None:
            query["department_id"] = department_id
        documents = await self.collection.find(query).sort("full_name", 1).to_list(length=None)
        return [EmployeeDocument.model_validate(document) for document in documents]

    async def find_by_id(
        self, employee_id: ObjectId, scope: ObjectId | None = None
    ) -> EmployeeDocument | None:
        query: dict = {"_id": employee_id}
        if scope is not None:
            query["department_id"] = scope
        document = await self.collection.find_one(query)
        return EmployeeDocument.model_validate(document) if document else None

    async def insert(self, document: dict) -> EmployeeDocument:
        result = await self.collection.insert_one(normalize_mongo_value(document))
        created = await self.collection.find_one({"_id": result.inserted_id})
        return EmployeeDocument.model_validate(created)

    async def update(
        self, employee_id: ObjectId, values: dict, scope: ObjectId | None = None
    ) -> EmployeeDocument | None:
        query: dict = {"_id": employee_id}
        if scope is not None:
            query["department_id"] = scope
        await self.collection.update_one(query, {"$set": normalize_mongo_value(values)})
        return await self.find_by_id(employee_id, scope)

    async def delete(self, employee_id: ObjectId, scope: ObjectId | None = None) -> bool:
        query: dict = {"_id": employee_id}
        if scope is not None:
            query["department_id"] = scope
        result = await self.collection.delete_one(query)
        return result.deleted_count == 1
