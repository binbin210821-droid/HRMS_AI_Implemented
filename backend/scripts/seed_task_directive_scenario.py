"""Tạo công việc quá hạn phát sinh sau chỉ thị để kiểm thử luồng bổ sung.

Script không xóa dữ liệu và có thể chạy lặp lại. Công việc được nhận diện bằng
``seed_key`` ổn định nên không tạo bản ghi trùng.
"""

import argparse
import asyncio
import sys
from datetime import datetime, time, timedelta, timezone
from pathlib import Path

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings
from app.core.time import business_clock
from app.repositories.task_repository import TaskRepository


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Tạo công việc quá hạn mới để kiểm thử bổ sung vào chỉ thị"
    )
    parser.add_argument("--department-code", default="KT", help="Mã phòng ban cần kiểm thử")
    parser.add_argument(
        "--scenario-key",
        default="followup-1",
        help="Khóa kịch bản; dùng khóa khác để tạo một công việc mới khác",
    )
    return parser.parse_args()


async def seed(args: argparse.Namespace) -> None:
    settings = get_settings()
    client = AsyncIOMotorClient(settings.mongo_uri, serverSelectionTimeoutMS=5000)
    try:
        database = client[settings.database_name]
        department = await database["departments"].find_one(
            {"code": args.department_code, "is_active": True}
        )
        if department is None:
            raise RuntimeError(
                f"Không tìm thấy phòng ban đang hoạt động mã {args.department_code}. "
                "Hãy chạy seed_base_data.py trước."
            )

        employee = await database["employees"].find_one(
            {"department_id": department["_id"], "is_active": True},
            sort=[("employee_code", 1)],
        )
        if employee is None:
            raise RuntimeError(
                f"Phòng ban {args.department_code} chưa có nhân viên đang hoạt động."
            )

        manager = await database["users"].find_one(
            {
                "role": "manager",
                "department_id": department["_id"],
                "is_active": True,
            }
        )
        if manager is None:
            raise RuntimeError(
                f"Phòng ban {args.department_code} chưa có Manager đang hoạt động."
            )

        now = datetime.now(timezone.utc)
        overdue_date = business_clock.today() - timedelta(days=1)
        seed_key = f"demo-task-directive-{args.department_code}-{args.scenario_key}"
        task = {
            "seed_key": seed_key,
            "title": "Công việc quá hạn phát sinh sau chỉ thị",
            "description": (
                "Dữ liệu mẫu phát sinh sau chỉ thị cũ, dùng để kiểm thử bổ sung "
                "vào chỉ thị đang chờ."
            ),
            "subtasks": ["Rà soát nguyên nhân", "Cập nhật kế hoạch xử lý"],
            "employee_id": employee["_id"],
            "department_id": department["_id"],
            "priority": "high",
            "status": "in_progress",
            "due_date": datetime.combine(overdue_date, time.min, tzinfo=timezone.utc),
            "completed_at": None,
            "created_by": manager["_id"],
            "created_at": now,
            "updated_at": now,
        }
        tasks = database["tasks"]
        await TaskRepository(database).ensure_indexes()
        await tasks.update_one(
            {"seed_key": seed_key},
            {"$set": task, "$setOnInsert": {"_id": ObjectId()}},
            upsert=True,
        )
        stored = await tasks.find_one({"seed_key": seed_key})
        directed = await database["department_task_directives"].find_one(
            {"task_ids": stored["_id"]}, {"_id": 1}
        )

        print(f"Đã seed công việc: {stored['_id']}")
        print(f"Phòng ban: {department['name']} ({department['code']})")
        print(f"Nhân viên nhận việc: {employee['full_name']}")
        print(f"Hạn công việc: {overdue_date.isoformat()}")
        if directed:
            print("Công việc đã nằm trong chỉ thị; không còn việc mới để bổ sung.")
        else:
            print(
                "Công việc chưa nằm trong chỉ thị. Đăng nhập Leadership và bấm "
                "'Bổ sung vào chỉ thị'."
            )
    finally:
        client.close()


if __name__ == "__main__":
    asyncio.run(seed(parse_args()))
