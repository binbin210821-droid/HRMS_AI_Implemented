"""Read-only kiểm tra số liệu task và index seed_key trước khi migration."""

import asyncio
import sys
from pathlib import Path

from motor.motor_asyncio import AsyncIOMotorClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings


async def main() -> None:
    settings = get_settings()
    client = AsyncIOMotorClient(settings.mongo_uri, serverSelectionTimeoutMS=5000)
    try:
        collection = client[settings.database_name]["tasks"]
        seed_key_count = await collection.count_documents({"seed_key": {"$exists": True}})
        distinct_seed_key_count = len(await collection.distinct("seed_key"))
        missing_seed_key_count = await collection.count_documents(
            {"seed_key": {"$exists": False}}
        )
        indexes = await collection.list_indexes().to_list(None)
        seed_index = next(
            (index for index in indexes if index.get("name") == "seed_key_1"),
            None,
        )
        print(f"tasks có seed_key: {seed_key_count}")
        print(f"seed_key phân biệt: {distinct_seed_key_count}")
        print(f"tasks thiếu seed_key: {missing_seed_key_count}")
        print(f"index seed_key_1: {seed_index}")
    finally:
        client.close()


if __name__ == "__main__":
    asyncio.run(main())
