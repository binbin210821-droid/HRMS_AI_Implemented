"""Kiểm tra read-only các liên kết dữ liệu của WorkMind."""

import asyncio
import sys
from pathlib import Path

from motor.motor_asyncio import AsyncIOMotorClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings


async def check_task_creators(database) -> int:
    user_ids = {
        document["_id"]
        async for document in database["users"].find({}, {"_id": 1})
    }
    orphan_count = 0
    task_count = 0
    async for task in database["tasks"].find({}, {"created_by": 1}):
        task_count += 1
        if task.get("created_by") not in user_ids:
            orphan_count += 1
    print(f"Kiểm tra {task_count} task: {orphan_count} orphan created_by.")
    return orphan_count


async def main() -> int:
    settings = get_settings()
    client = AsyncIOMotorClient(settings.mongo_uri, serverSelectionTimeoutMS=5000)
    try:
        orphan_count = await check_task_creators(client[settings.database_name])
        return 1 if orphan_count else 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
