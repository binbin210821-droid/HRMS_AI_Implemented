"""Seed dữ liệu mẫu cho luồng cảnh báo theo phòng ban và chỉ thị Leadership.

Script không xóa dữ liệu hiện có và có thể chạy lặp lại. Script bám theo mã phòng
ban, mã nhân viên và tài khoản demo đang có trong MongoDB thay vì hard-code ObjectId.
Mặc định script chỉ tạo cảnh báo mở để Leadership phát hành chỉ thị qua giao diện.
Dùng ``--with-pending-directive`` nếu muốn tạo sẵn một chỉ thị để Manager xác nhận.
"""

import argparse
import asyncio
import sys
from datetime import datetime, time, timezone
from pathlib import Path

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings
from app.core.time import business_clock
from app.services.performance_score_calculator import PerformanceScoreCalculator


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Tạo dữ liệu mẫu để kiểm thử chỉ thị cảnh báo cấp phòng ban"
    )
    parser.add_argument("--department-code", default="KD", help="Mã phòng ban cần seed dữ liệu")
    parser.add_argument(
        "--specialty",
        default="Kinh doanh và vận hành",
        help="Chuyên môn dùng chung để kiểm thử nhóm phòng ban",
    )
    parser.add_argument(
        "--with-pending-directive",
        action="store_true",
        help="Tạo thêm một chỉ thị pending để Manager kiểm thử xác nhận",
    )
    parser.add_argument(
        "--reset-alerts",
        action="store_true",
        help="Mở lại các cảnh báo mẫu đã được xử lý trước đó",
    )
    return parser.parse_args()


async def get_department(collection, code: str) -> dict:
    department = await collection.find_one({"code": code, "is_active": True})
    if department is None:
        raise RuntimeError(
            f"Không tìm thấy phòng ban đang hoạt động mã {code}. "
            "Hãy chạy seed_base_data.py trước."
        )
    return department


async def prepare_department(database, args: argparse.Namespace) -> dict:
    departments = database["departments"]
    department = await get_department(departments, args.department_code)
    await departments.update_one(
        {"_id": department["_id"]},
        {"$set": {"specialty": args.specialty, "updated_at": datetime.now(timezone.utc)}},
    )
    department["specialty"] = args.specialty
    return department


async def find_manager(database, department_id: ObjectId) -> dict:
    manager = await database["users"].find_one(
        {"role": "manager", "department_id": department_id, "is_active": True}
    )
    if manager is None:
        raise RuntimeError(f"Phòng ban {department_id} chưa có Manager đang hoạt động.")
    return manager


async def prepare_capacity_metrics(database, department: dict, manager: dict) -> list[dict]:
    employees = (
        await database["employees"]
        .find({"department_id": department["_id"], "is_active": True})
        .sort("employee_code", 1)
        .to_list(None)
    )
    if len(employees) < 2:
        raise RuntimeError("Phòng ban cần ít nhất 2 nhân viên để kiểm thử năng lực nhận việc.")

    today = business_clock.today()
    metric_date = datetime.combine(today, time.min, tzinfo=timezone.utc)
    metrics = database["performance_metrics"]
    await metrics.create_index([("employee_id", 1), ("date", 1)], unique=True)

    candidates = employees[-2:]
    values = ((1, 91.0), (2, 86.0))
    now = datetime.now(timezone.utc)
    for employee, (tasks_completed, quality_score) in zip(candidates, values, strict=True):
        await metrics.update_one(
            {"employee_id": employee["_id"], "date": metric_date},
            {
                "$set": {
                    "tasks_completed": tasks_completed,
                    "quality_score": quality_score,
                    "reviewed_by": manager["_id"],
                    "performance_score": PerformanceScoreCalculator.calculate(
                        tasks_completed, quality_score
                    ),
                    "note": "Dữ liệu mẫu nhân viên còn khả năng nhận thêm việc.",
                    "updated_at": now,
                },
                "$setOnInsert": {"_id": ObjectId(), "created_at": now},
            },
            upsert=True,
        )
    return candidates


async def seed_alerts(
    database, department: dict, employees: list[dict], reset_alerts: bool
) -> list[dict]:
    if len(employees) < 4:
        raise RuntimeError(
            "Phòng ban nguồn cần ít nhất 4 nhân viên để tạo đủ dữ liệu cảnh báo mẫu."
        )

    alerts = database["alerts"]
    now = datetime.now(timezone.utc)
    today = now.date()
    detected_at = datetime.combine(today, time.min, tzinfo=timezone.utc)
    definitions = (
        (employees[0], "overload", "high", "Cảnh báo quá tải mẫu", 6, 72.0),
        (employees[1], "early_warning", "medium", "Dấu hiệu sớm mẫu", 3, 82.0),
        (employees[2], "overload", "high", "Cảnh báo quá tải mẫu", 5, 76.0),
        (employees[3], "early_warning", "medium", "Dấu hiệu sớm mẫu", 4, 78.0),
    )
    seeded: list[dict] = []
    for employee, alert_type, severity, title, tasks_completed, quality_score in definitions:
        fingerprint = f"seed-department-directive:{department['code']}:{employee['employee_code']}:{alert_type}"
        message = (
            f"{employee['full_name']} có dữ liệu mẫu cần được phòng ban rà soát "
            f"({tasks_completed} công việc, chất lượng {quality_score:.0f} điểm)."
        )
        suggested_action = (
            "Rà soát khối lượng công việc và thống nhất hướng xử lý với Manager phòng ban."
        )
        update_fields = {
            "alert_type": alert_type,
            "severity": severity,
            "employee_id": employee["_id"],
            "department_id": department["_id"],
            "employee_code": employee["employee_code"],
            "employee_name": employee["full_name"],
            "title": title,
            "message": message,
            "suggested_action": suggested_action,
            "detected_dates": [detected_at],
            "updated_at": now,
        }
        if reset_alerts:
            update_fields.update(
                {
                    "status": "open",
                    "resolution_note": None,
                    "resolved_by": None,
                    "resolved_at": None,
                }
            )
        set_on_insert = {"_id": ObjectId(), "created_at": now, "fingerprint": fingerprint}
        if not reset_alerts:
            set_on_insert.update(
                {
                    "status": "open",
                    "resolution_note": None,
                    "resolved_by": None,
                    "resolved_at": None,
                }
            )
        await alerts.update_one(
            {"fingerprint": fingerprint},
            {
                "$set": update_fields,
                "$setOnInsert": set_on_insert,
            },
            upsert=True,
        )
        alert = await alerts.find_one({"fingerprint": fingerprint})
        seeded.append(alert)
    return seeded


async def seed_pending_directive(
    database, department: dict, manager: dict, alerts: list[dict]
) -> dict | None:
    leadership = await database["users"].find_one(
        {"username": "demo.leadership", "role": "leadership", "is_active": True}
    )
    if leadership is None:
        raise RuntimeError("Không tìm thấy tài khoản demo.leadership để ghi người phát hành.")

    pending = await database["department_alert_directives"].find_one(
        {"target_department_id": department["_id"], "status": "pending"}
    )
    if pending is not None:
        return pending

    open_alerts = [alert for alert in alerts if alert["status"] == "open"]
    selected_alerts = [alert for alert in open_alerts if alert["severity"] == "high"]
    selected_alerts = selected_alerts or open_alerts
    if not selected_alerts:
        return None

    now = datetime.now(timezone.utc)
    document = {
        "_id": ObjectId(),
        "department_id": department["_id"],
        "target_department_id": department["_id"],
        "target_manager_id": manager["_id"],
        "alert_ids": [alert["_id"] for alert in selected_alerts],
        "selected_alert_type": "all",
        "selected_severity": (
            "high" if any(alert["severity"] == "high" for alert in selected_alerts) else "all"
        ),
        "selected_alert_count": len(selected_alerts),
        "selected_open_count": len(selected_alerts),
        "total_count": len(alerts),
        "open_count": len(open_alerts),
        "resolved_count": len(alerts) - len(open_alerts),
        "early_warning_count": sum(alert["alert_type"] == "early_warning" for alert in alerts),
        "overload_count": sum(alert["alert_type"] == "overload" for alert in alerts),
        "high_count": sum(alert["severity"] == "high" for alert in alerts),
        "note": "Dữ liệu mẫu: đề nghị Manager rà soát nhóm cảnh báo và thống nhất hướng xử lý.",
        "status": "pending",
        "issued_by": leadership["_id"],
        "issued_at": now,
        "acknowledged_by": None,
        "acknowledged_at": None,
        "acknowledgement_note": None,
    }
    await database["department_alert_directives"].insert_one(document)
    await database["audit_logs"].insert_one(
        {
            "action": "department_alert_directive_seeded",
            "actor_id": leadership["_id"],
            "directive_id": document["_id"],
            "department_id": department["_id"],
            "target_department_id": department["_id"],
            "created_at": now,
        }
    )
    return document


async def seed(args: argparse.Namespace) -> None:
    settings = get_settings()
    client = AsyncIOMotorClient(settings.mongo_uri, serverSelectionTimeoutMS=5000)
    try:
        database = client[settings.database_name]
        department = await prepare_department(database, args)
        manager = await find_manager(database, department["_id"])

        employees = (
            await database["employees"]
            .find({"department_id": department["_id"], "is_active": True})
            .sort("employee_code", 1)
            .to_list(None)
        )
        await prepare_capacity_metrics(database, department, manager)
        seeded_alerts = await seed_alerts(database, department, employees, args.reset_alerts)

        pending = None
        if args.with_pending_directive:
            pending = await seed_pending_directive(database, department, manager, seeded_alerts)

        print(f"Đã gán chuyên môn '{args.specialty}' cho phòng {department['code']}.")
        print(f"Đã tạo/cập nhật {len(seeded_alerts)} cảnh báo mẫu tại phòng {department['code']}.")
        if not args.reset_alerts:
            print(
                "Trạng thái cảnh báo đã xử lý được giữ nguyên; dùng --reset-alerts nếu cần mở lại."
            )
        print(
            f"Đã chuẩn bị 2 nhân viên có thể nhận việc hôm nay tại phòng {department['code']} "
            f"(Manager: {manager['full_name']})."
        )
        if pending:
            print(f"Đã tạo chỉ thị pending: {pending['_id']}")
        else:
            print(
                "Chưa tạo chỉ thị pending; Leadership có thể phát hành chỉ thị mới trên giao diện."
            )
        print("Tài khoản Leadership: demo.leadership / mật khẩu mặc định trong seed demo.")
        print(f"Tài khoản Manager cần kiểm thử: {manager['username']}")
    finally:
        client.close()


if __name__ == "__main__":
    asyncio.run(seed(parse_args()))
