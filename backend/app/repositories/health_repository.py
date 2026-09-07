from app.core.database import get_mongo_database


class HealthRepository:
    async def is_database_available(self) -> bool:
        return await get_mongo_database().ping()
