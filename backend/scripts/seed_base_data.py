import argparse
import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings
from app.core.security import hash_password
from app.models.user import UserRole

DEPARTMENT_SPECS = [
    ("KD", "Kinh doanh", "Phụ trách hoạt động kinh doanh và phát triển khách hàng."),
    ("KT", "Kỹ thuật", "Phụ trách sản phẩm, nền tảng và vận hành kỹ thuật."),
    ("CSKH", "Chăm sóc khách hàng", "Phụ trách hỗ trợ và duy trì trải nghiệm khách hàng."),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Tạo dữ liệu nền WorkMind cho môi trường phát triển"
    )
    parser.add_argument(
        "--password", default="DemoPassword123!", help="Mật khẩu chung cho tài khoản demo"
    )
    parser.add_argument("--employees-per-department", type=int, default=5)
    return parser.parse_args()


async def upsert_departments(database) -> dict[str, ObjectId]:
    collection = database["departments"]
    now = datetime.now(timezone.utc)
    department_ids: dict[str, ObjectId] = {}
    for code, name, description in DEPARTMENT_SPECS:
        await collection.update_one(
            {"code": code},
            {
                "$set": {
                    "name": name,
                    "description": description,
                    "is_active": True,
                    "updated_at": now,
                },
                "$setOnInsert": {"_id": ObjectId(), "code": code, "created_at": now},
            },
            upsert=True,
        )
        document = await collection.find_one({"code": code}, {"_id": 1})
        department_ids[code] = document["_id"]
    return department_ids


async def upsert_users(database, department_ids: dict[str, ObjectId], password: str) -> None:
    collection = database["users"]
    now = datetime.now(timezone.utc)
    users = [
        ("demo.leadership", "Lãnh đạo Demo", UserRole.LEADERSHIP.value, None),
        ("demo.manager", "Quản lý Kinh doanh", UserRole.MANAGER.value, department_ids["KD"]),
        ("demo.manager.tech", "Quản lý Kỹ thuật", UserRole.MANAGER.value, department_ids["KT"]),
        (
            "demo.manager.cskh",
            "Quản lý Chăm sóc khách hàng",
            UserRole.MANAGER.value,
            department_ids["CSKH"],
        ),
    ]
    for username, full_name, role, department_id in users:
        await collection.update_one(
            {"username": username},
            {
                "$set": {
                    "password_hash": hash_password(password),
                    "full_name": full_name,
                    "role": role,
                    "department_id": department_id,
                    "is_active": True,
                },
                "$setOnInsert": {"_id": ObjectId(), "created_at": now},
            },
            upsert=True,
        )


async def upsert_employees(database, department_ids: dict[str, ObjectId], count: int) -> int:
    collection = database["employees"]
    now = datetime.now(timezone.utc)
    total = 0
    for code, name, _ in DEPARTMENT_SPECS:
        for index in range(1, count + 1):
            employee_code = f"{code}-NV-{index:03d}"
            await collection.update_one(
                {"employee_code": employee_code},
                {
                    "$set": {
                        "full_name": f"Nhân viên {name} {index}",
                        "email": f"{code.lower()}.nhanvien{index}@hrms.local",
                        "phone": f"090{index:07d}",
                        "position": "Chuyên viên",
                        "department_id": department_ids[code],
                        "is_active": True,
                        "updated_at": now,
                    },
                    "$setOnInsert": {"_id": ObjectId(), "created_at": now},
                },
                upsert=True,
            )
            total += 1
    return total


async def seed(args: argparse.Namespace) -> None:
    if not 5 <= args.employees_per_department <= 8:
        raise ValueError("--employees-per-department phải nằm trong khoảng 5-8")
    settings = get_settings()
    client = AsyncIOMotorClient(settings.mongo_uri, serverSelectionTimeoutMS=5000)
    try:
        database = client[settings.database_name]
        await database["departments"].create_index("code", unique=True)
        await database["users"].create_index("username", unique=True)
        await database["employees"].create_index("employee_code", unique=True)
        department_ids = await upsert_departments(database)
        await upsert_users(database, department_ids, args.password)
        employee_count = await upsert_employees(
            database, department_ids, args.employees_per_department
        )
        print("Đã seed 3 phòng ban, 1 Leadership, 3 Manager.")
        print(f"Đã seed {employee_count} nhân viên ({args.employees_per_department}/phòng ban).")
        for code, department_id in department_ids.items():
            print(f"{code}: {department_id}")
    finally:
        client.close()


if __name__ == "__main__":
    asyncio.run(seed(parse_args()))
