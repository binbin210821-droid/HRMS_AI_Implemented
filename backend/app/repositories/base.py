from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase


class MongoRepository:
    def __init__(self, database: AsyncIOMotorDatabase, collection_name: str) -> None:
        self.database = database
        self.collection = database[collection_name]

    async def find_one(self, query: dict[str, Any]) -> dict[str, Any] | None:
        return await self.collection.find_one(query)
