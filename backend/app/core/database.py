from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import timezone

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo.errors import PyMongoError

from app.core.config import Settings


class MongoDatabase:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client: AsyncIOMotorClient | None = None
        self.database: AsyncIOMotorDatabase | None = None

    async def connect(self) -> None:
        self.client = AsyncIOMotorClient(
            self.settings.mongo_uri,
            serverSelectionTimeoutMS=5000,
            tz_aware=True,
            tzinfo=timezone.utc,
        )
        await self.client.admin.command("ping")
        self.database = self.client[self.settings.database_name]

    async def disconnect(self) -> None:
        if self.client is not None:
            self.client.close()
            self.client = None
            self.database = None

    async def ping(self) -> bool:
        if self.client is None:
            return False
        try:
            await self.client.admin.command("ping")
            return True
        except PyMongoError:
            return False

    def get_database(self) -> AsyncIOMotorDatabase:
        if self.database is None:
            raise RuntimeError("MongoDB chưa được kết nối")
        return self.database


mongo_database: MongoDatabase | None = None


@asynccontextmanager
async def database_lifespan(settings: Settings) -> AsyncGenerator[MongoDatabase, None]:
    global mongo_database
    mongo_database = MongoDatabase(settings)
    await mongo_database.connect()
    try:
        yield mongo_database
    finally:
        await mongo_database.disconnect()
        mongo_database = None


def get_mongo_database() -> MongoDatabase:
    if mongo_database is None:
        raise RuntimeError("MongoDB chưa được khởi tạo")
    return mongo_database
