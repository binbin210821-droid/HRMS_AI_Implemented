import argparse
import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient

from app.core.config import get_settings
from app.core.security import hash_password
from app.models.user import UserRole


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Tạo hoặc cập nhật tài khoản demo cho môi trường phát triển"
    )
    parser.add_argument("--username", default="demo.manager")
    parser.add_argument("--password", default="DemoPassword123!")
    parser.add_argument(
        "--role", choices=[role.value for role in UserRole], default=UserRole.MANAGER.value
    )
    parser.add_argument("--department-id", default=None)
    return parser.parse_args()


async def seed_user(args: argparse.Namespace) -> None:
    settings = get_settings()
    client = AsyncIOMotorClient(settings.mongo_uri, serverSelectionTimeoutMS=5000)
    try:
        department_id = ObjectId(args.department_id) if args.department_id else None
        if args.role == UserRole.MANAGER.value and department_id is None:
            department_id = ObjectId()

        user_id = ObjectId()
        await client[settings.database_name]["users"].update_one(
            {"username": args.username},
            {
                "$set": {
                    "password_hash": hash_password(args.password),
                    "full_name": "Tài khoản demo",
                    "role": args.role,
                    "department_id": department_id,
                    "is_active": True,
                },
                "$setOnInsert": {"_id": user_id, "created_at": datetime.now(timezone.utc)},
            },
            upsert=True,
        )
        print(f"Đã sẵn sàng tài khoản demo: {args.username} ({args.role})")
        if department_id:
            print(f"Department scope: {department_id}")
    finally:
        client.close()


if __name__ == "__main__":
    asyncio.run(seed_user(parse_args()))
