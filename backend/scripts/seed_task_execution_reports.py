"""Seed báo cáo thực thi task mẫu, có thể chạy lặp lại an toàn."""

import argparse
import asyncio
import hashlib
import sys
from datetime import datetime, time, timezone
from pathlib import Path

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings
from app.core.time import business_clock


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Tạo báo cáo thực thi task mẫu cho review hàng ngày")
    parser.add_argument("--date", default=None, help="Ngày báo cáo dạng YYYY-MM-DD; mặc định là hôm nay")
    return parser.parse_args()


def _sample_attachment(task: dict, report_date) -> dict | None:
    settings = get_settings()
    if not settings.storage_bucket:
        return None
    content = f"Minh chứng mẫu cho: {task['title']}\nNgày: {report_date.isoformat()}\n".encode()
    checksum = hashlib.sha256(content).hexdigest()
    return {
        "storage_key": f"demo/task-execution/{task['_id']}/{report_date.isoformat()}.txt",
        "file_name": "minh-chung-ket-qua.txt",
        "content_type": "text/plain",
        "file_size": len(content),
        "checksum": checksum,
        "_content": content,
    }


def _upload_if_configured(attachment: dict | None) -> None:
    if not attachment:
        return
    settings = get_settings()
    try:
        import boto3

        client = boto3.client(
            "s3",
            endpoint_url=(
                settings.storage_internal_endpoint_url
                or settings.storage_endpoint_url
                or None
            ),
            region_name=settings.storage_region,
            aws_access_key_id=settings.storage_access_key or None,
            aws_secret_access_key=settings.storage_secret_key or None,
        )
        try:
            client.head_bucket(Bucket=settings.storage_bucket)
        except Exception:
            client.create_bucket(Bucket=settings.storage_bucket)
        client.put_object(
            Bucket=settings.storage_bucket,
            Key=attachment["storage_key"],
            Body=attachment["_content"],
            ContentType=attachment["content_type"],
        )
    except (ImportError, OSError):
        attachment.clear()


async def seed(args: argparse.Namespace) -> None:
    settings = get_settings()
    report_date = (
        datetime.strptime(args.date, "%Y-%m-%d").date()
        if args.date
        else business_clock.today()
    )
    client = AsyncIOMotorClient(settings.mongo_uri, serverSelectionTimeoutMS=5000)
    try:
        database = client[settings.database_name]
        tasks = await database["tasks"].find({}).sort("created_at", 1).to_list(None)
        if not tasks:
            raise RuntimeError("Chưa có task. Hãy chạy seed_tasks_data.py trước.")
        reports = database["task_execution_reports"]
        await reports.create_index([("task_id", 1), ("work_date", 1)], unique=True)
        await reports.create_index(
            "seed_key",
            unique=True,
            partialFilterExpression={"seed_key": {"$type": "string"}},
        )
        now = datetime.now(timezone.utc)
        created = 0
        for index, task in enumerate(tasks):
            attachment = _sample_attachment(task, report_date) if index % 3 == 0 else None
            _upload_if_configured(attachment)
            uploaded = bool(attachment and attachment.get("_content"))
            if attachment:
                attachment.pop("_content", None)
            report = {
                "task_id": task["_id"],
                "employee_id": task["employee_id"],
                "department_id": task["department_id"],
                "work_date": datetime.combine(report_date, time.min, tzinfo=timezone.utc),
                "result_summary": f"Đã cập nhật kết quả cho {task['title']}." if index % 2 else "Đã hoàn tất phần việc được giao.",
                "progress_percent": 100 if task.get("status") == "done" else 60,
                "outcome_status": "completed" if task.get("status") == "done" else "in_progress",
                "attachments": [attachment] if uploaded else [],
                "submitted_by_employee_id": task["employee_id"],
                "submitted_at": now,
                "manager_review": None,
                "updated_at": now,
            }
            if not uploaded:
                report["seed_missing_reason"] = "Minh chứng đang chờ nhân viên bổ sung trong bản demo."
            await reports.update_one(
                {"task_id": task["_id"], "work_date": report["work_date"]},
                {"$set": report, "$setOnInsert": {"_id": ObjectId(), "created_at": now, "seed_key": f"demo-{task['_id']}-{report_date.isoformat()}"}},
                upsert=True,
            )
            created += 1
        print(f"Đã đồng bộ {created} báo cáo thực thi cho ngày {report_date.isoformat()}.")
        if not settings.storage_bucket:
            print("Storage chưa cấu hình: các mẫu không có tệp sẽ yêu cầu nhập lý do thiếu minh chứng khi nghiệm thu.")
    finally:
        client.close()


if __name__ == "__main__":
    asyncio.run(seed(parse_args()))
