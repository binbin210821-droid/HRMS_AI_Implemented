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
from app.services.performance_score_calculator import PerformanceScoreCalculator


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Tạo 60 ngày dữ liệu hiệu suất mẫu")
    parser.add_argument("--days", type=int, default=60)
    return parser.parse_args()


def metric_values(employee_code: str, day_offset: int) -> tuple[int, float, str | None]:
    """Tạo dữ liệu ổn định, có chuỗi quá tải chủ đích cho các giai đoạn sau."""
    if employee_code.endswith("-003") and day_offset in {0, 1, 2}:
        # Chuỗi cảnh báo sớm: task tăng dần, chất lượng giảm nhưng chưa giảm 20%.
        return {
            2: (2, 88.0),
            1: (3, 82.0),
            0: (4, 78.0),
        }[
            day_offset
        ] + ("Chuỗi cảnh báo sớm mẫu",)
    if employee_code.endswith("-001") and day_offset in {0, 1, 2}:
        quality_by_offset = {2: 54.0, 1: 49.0, 0: 43.0}
        return 6, quality_by_offset[day_offset], "Chuỗi dữ liệu mẫu có dấu hiệu quá tải"
    if employee_code.endswith("-002") and day_offset in {7, 8, 9}:
        quality_by_offset = {9: 62.0, 8: 60.0, 7: 58.0}
        return 3, quality_by_offset[day_offset], "Chuỗi sụt giảm chất lượng mẫu"
    if employee_code.endswith("-002") and day_offset in {20, 21, 22}:
        return 5, 84.0, "Dữ liệu mẫu vượt ngưỡng khối lượng công việc"

    employee_number = int(employee_code[-3:])
    tasks_completed = 2 + ((day_offset + employee_number) % 3)
    quality_score = float(78 + ((day_offset + employee_number * 2) % 18))
    return tasks_completed, quality_score, None


async def seed(args: argparse.Namespace) -> None:
    if args.days < 3:
        raise ValueError("--days phải lớn hơn hoặc bằng 3 để tạo chuỗi kiểm thử")

    settings = get_settings()
    client = AsyncIOMotorClient(settings.mongo_uri, serverSelectionTimeoutMS=5000)
    try:
        database = client[settings.database_name]
        metrics = database["performance_metrics"]
        employees = await database["employees"].find({}).sort("employee_code", 1).to_list(None)
        managers = await database["users"].find({"role": "manager"}).to_list(None)
        manager_by_department = {manager["department_id"]: manager["_id"] for manager in managers}
        if not employees or len(manager_by_department) == 0:
            raise RuntimeError("Cần chạy seed_base_data.py trước khi seed performance")

        await metrics.create_index([("employee_id", 1), ("date", 1)], unique=True)
        today = business_clock.today()
        total = 0
        for employee in employees:
            reviewer_id = manager_by_department.get(employee["department_id"])
            if reviewer_id is None:
                continue
            for day_offset in range(args.days - 1, -1, -1):
                metric_date = today - timedelta(days=day_offset)
                date_value = datetime.combine(metric_date, time.min, tzinfo=timezone.utc)
                tasks_completed, quality_score, note = metric_values(
                    employee["employee_code"], day_offset
                )
                now = datetime.now(timezone.utc)
                await metrics.update_one(
                    {"employee_id": employee["_id"], "date": date_value},
                    {
                        "$set": {
                            "tasks_completed": tasks_completed,
                            "quality_score": quality_score,
                            "reviewed_by": reviewer_id,
                            "performance_score": PerformanceScoreCalculator.calculate(
                                tasks_completed, quality_score
                            ),
                            "note": note,
                            "updated_at": now,
                        },
                        "$setOnInsert": {"_id": ObjectId(), "created_at": now},
                    },
                    upsert=True,
                )
                total += 1
        print(f"Đã seed {total} bản ghi hiệu suất cho {args.days} ngày.")
    finally:
        client.close()


if __name__ == "__main__":
    asyncio.run(seed(parse_args()))
