"""Seed công việc mẫu bám theo nhân viên đang có trong MongoDB.

Script an toàn để chạy lặp lại: mỗi công việc có seed_key ổn định nên không tạo bản ghi trùng.
"""

import argparse
import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings
from app.models.user import UserRole
from app.repositories.task_repository import TaskRepository


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Tạo công việc mẫu theo nhân viên đã có trong MongoDB"
    )
    parser.add_argument(
        "--tasks-per-employee",
        type=int,
        default=3,
        choices=range(1, 4),
        help="Số công việc mẫu cho mỗi nhân viên (1-3)",
    )
    return parser.parse_args()


def build_task(employee: dict, index: int, now: datetime, created_by: ObjectId) -> dict:
    employee_id = employee["_id"]
    employee_code = employee["employee_code"]
    due_dates = (now - timedelta(days=2), now + timedelta(days=2), now + timedelta(days=7))
    statuses = ("in_progress", "todo", "done")
    priorities = ("high", "medium", "low")
    status = statuses[index]
    return {
        "_id": ObjectId(),
        "seed_key": f"demo-{employee_code}-task-{index + 1}",
        "title": (
            ("Xử lý công việc ưu tiên" if index == 0 else "Rà soát hồ sơ công việc")
            if index < 2
            else "Hoàn tất báo cáo tuần"
        ),
        "description": f"Công việc mẫu dành cho {employee['full_name']}.",
        "subtasks": ["Kiểm tra yêu cầu", "Cập nhật kết quả"] if index < 2 else [],
        "employee_id": employee_id,
        "department_id": employee["department_id"],
        "priority": priorities[index],
        "status": status,
        "due_date": due_dates[index].replace(hour=0, minute=0, second=0, microsecond=0),
        "completed_at": now if status == "done" else None,
        "created_by": created_by,
        "created_at": now,
        "updated_at": now,
    }


async def resolve_task_creators(database, employees: list[dict]) -> dict[ObjectId, ObjectId]:
    """Resolve one real task creator per department without hardcoded IDs."""
    users = database["users"]
    department_ids = {employee["department_id"] for employee in employees}
    creators: dict[ObjectId, ObjectId] = {}
    missing_departments: list[ObjectId] = []
    for department_id in department_ids:
        manager = await users.find_one(
            {
                "role": UserRole.MANAGER.value,
                "department_id": department_id,
                "is_active": True,
            },
            {"_id": 1},
            sort=[("username", 1)],
        )
        if manager is None:
            missing_departments.append(department_id)
        else:
            creators[department_id] = manager["_id"]

    leadership = None
    if missing_departments:
        leadership = await users.find_one(
            {"role": UserRole.LEADERSHIP.value, "is_active": True},
            {"_id": 1},
            sort=[("username", 1)],
        )
        if leadership is None:
            raise RuntimeError(
                "Không tìm thấy Manager phù hợp và cũng không có tài khoản Leadership đang hoạt động."
            )
        for department_id in missing_departments:
            creators[department_id] = leadership["_id"]
    return creators


async def seed(args: argparse.Namespace) -> None:
    settings = get_settings()
    client = AsyncIOMotorClient(settings.mongo_uri, serverSelectionTimeoutMS=5000)
    try:
        database = client[settings.database_name]
        employees = (
            await database["employees"]
            .find({"is_active": True})
            .sort("employee_code", 1)
            .to_list(None)
        )
        if not employees:
            raise RuntimeError(
                "Chưa có nhân viên đang hoạt động. Hãy chạy seed_base_data.py trước."
            )
        creators = await resolve_task_creators(database, employees)

        tasks = database["tasks"]
        await TaskRepository(database).ensure_indexes()
        await database.command(
            {"collMod": "tasks", "changeStreamPreAndPostImages": {"enabled": True}}
        )
        now = datetime.now(timezone.utc)
        seeded = 0
        for employee in employees:
            for index in range(args.tasks_per_employee):
                task = build_task(employee, index, now, creators[employee["department_id"]])
                task_id = task.pop("_id")
                seed_key = task.pop("seed_key")
                created_by = task.pop("created_by")
                await tasks.update_one(
                    {"seed_key": seed_key},
                    {
                        "$set": task,
                        "$setOnInsert": {
                            "_id": task_id,
                            "seed_key": seed_key,
                            "created_by": created_by,
                        },
                    },
                    upsert=True,
                )
                seeded += 1

        print(f"Đã đồng bộ {seeded} công việc mẫu cho {len(employees)} nhân viên hiện có.")
        print("Dữ liệu gồm việc đang làm, việc chưa bắt đầu, việc đã hoàn thành và việc quá hạn.")
    finally:
        client.close()


if __name__ == "__main__":
    asyncio.run(seed(parse_args()))
