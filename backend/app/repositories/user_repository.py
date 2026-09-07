from bson import ObjectId
from bson.errors import InvalidId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models.user import UserDocument


class UserRepository:
    def __init__(self, database: AsyncIOMotorDatabase) -> None:
        self.collection = database["users"]

    async def find_by_username(self, username: str) -> UserDocument | None:
        document = await self.collection.find_one({"username": username})
        return UserDocument.model_validate(document) if document else None

    async def find_by_id(self, user_id: str) -> UserDocument | None:
        try:
            object_id = ObjectId(user_id)
        except (InvalidId, TypeError):
            return None
        document = await self.collection.find_one({"_id": object_id})
        return UserDocument.model_validate(document) if document else None
