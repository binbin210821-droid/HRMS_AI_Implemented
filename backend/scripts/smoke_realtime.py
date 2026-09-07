import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

from bson import ObjectId
from pymongo import MongoClient
from websockets import connect
from websockets.exceptions import ConnectionClosedError, InvalidStatus

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import Settings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke-test WebSocket realtime và Change Streams")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--websocket-url", default="ws://127.0.0.1:8000/ws/realtime")
    parser.add_argument("--password", default="DemoPassword123!")
    return parser.parse_args()


def login(base_url: str, username: str, password: str) -> str:
    request = Request(
        f"{base_url}/api/auth/login",
        data=json.dumps({"username": username, "password": password}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=5) as response:
        return json.load(response)["access_token"]


async def run_smoke(args: argparse.Namespace) -> None:
    settings = Settings()
    database_client = MongoClient(settings.mongo_uri, serverSelectionTimeoutMS=5000)
    database = database_client[settings.database_name]
    kd = database.departments.find_one({"code": "KD"}, {"_id": 1})
    kt = database.departments.find_one({"code": "KT"}, {"_id": 1})
    kd_employee = database.employees.find_one({"employee_code": "KD-NV-001"}, {"_id": 1})
    assert kd and kt and kd_employee, "Thiếu dữ liệu seed KD/KT"

    kd_token = login(args.base_url, "demo.manager", args.password)
    kt_token = login(args.base_url, "demo.manager.tech", args.password)
    leadership_token = login(args.base_url, "demo.leadership", args.password)
    kd_url = f"{args.websocket_url}?token={quote(kd_token)}"
    kt_url = f"{args.websocket_url}?token={quote(kt_token)}"
    leadership_url = f"{args.websocket_url}?token={quote(leadership_token)}"
    alert_id = ObjectId()
    metric_id = ObjectId()
    task_id = ObjectId()
    alert = {
        "_id": alert_id,
        "department_id": kd["_id"],
        "employee_id": ObjectId(),
        "message": "Phase 4 realtime smoke",
        "created_at": datetime.now(timezone.utc),
    }
    metric = {
        "_id": metric_id,
        "employee_id": kd_employee["_id"],
        "date": datetime(2099, 12, 30, tzinfo=timezone.utc),
        "tasks_completed": 4,
        "quality_score": 80.0,
        "reviewed_by": ObjectId(),
        "performance_score": 86.0,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    task = {
        "_id": task_id,
        "title": "Phase 4 realtime task smoke",
        "description": "Kiểm tra cập nhật công việc tức thời",
        "subtasks": [],
        "employee_id": kd_employee["_id"],
        "department_id": kd["_id"],
        "priority": "high",
        "status": "in_progress",
        "due_date": datetime.now(timezone.utc),
        "completed_at": None,
        "created_by": ObjectId(),
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }

    try:
        async with (
            connect(kd_url) as kd_socket,
            connect(kt_url) as kt_socket,
            connect(leadership_url) as leadership_socket,
        ):
            database.alerts.insert_one(alert)
            kd_event = json.loads(await asyncio.wait_for(kd_socket.recv(), timeout=5))
            leadership_event = json.loads(
                await asyncio.wait_for(leadership_socket.recv(), timeout=5)
            )
            assert kd_event["topic"] == "alerts"
            assert kd_event["operation"] == "insert"
            assert kd_event["data"]["_id"] == str(alert_id)
            assert leadership_event["data"]["_id"] == str(alert_id)

            try:
                await asyncio.wait_for(kt_socket.recv(), timeout=1.5)
            except TimeoutError:
                pass
            else:
                raise AssertionError("Manager phòng KT nhận alert ngoài scope KD")

            database.performance_metrics.insert_one(metric)
            kd_metric_event = json.loads(await asyncio.wait_for(kd_socket.recv(), timeout=5))
            leadership_metric_event = json.loads(
                await asyncio.wait_for(leadership_socket.recv(), timeout=5)
            )
            assert kd_metric_event["topic"] == "performance_metrics"
            assert kd_metric_event["data"]["_id"] == str(metric_id)
            assert leadership_metric_event["data"]["_id"] == str(metric_id)
            try:
                await asyncio.wait_for(kt_socket.recv(), timeout=1.5)
            except TimeoutError:
                pass
            else:
                raise AssertionError("Manager phòng KT nhận metric ngoài scope KD")

            database.tasks.insert_one(task)
            kd_task_event = json.loads(await asyncio.wait_for(kd_socket.recv(), timeout=5))
            leadership_task_event = json.loads(
                await asyncio.wait_for(leadership_socket.recv(), timeout=5)
            )
            assert kd_task_event["topic"] == "tasks"
            assert kd_task_event["data"]["_id"] == str(task_id)
            assert leadership_task_event["data"]["_id"] == str(task_id)
            try:
                await asyncio.wait_for(kt_socket.recv(), timeout=1.5)
            except TimeoutError:
                pass
            else:
                raise AssertionError("Manager phòng KT nhận task ngoài scope KD")

            database.tasks.update_one(
                {"_id": task_id}, {"$set": {"title": "Phase 4 realtime task updated"}}
            )
            kd_task_update = json.loads(await asyncio.wait_for(kd_socket.recv(), timeout=5))
            leadership_task_update = json.loads(
                await asyncio.wait_for(leadership_socket.recv(), timeout=5)
            )
            assert kd_task_update["topic"] == "tasks"
            assert kd_task_update["operation"] == "update"
            assert kd_task_update["data"]["title"] == "Phase 4 realtime task updated"
            assert leadership_task_update["data"]["title"] == "Phase 4 realtime task updated"

            database.tasks.delete_one({"_id": task_id})
            kd_task_delete = json.loads(await asyncio.wait_for(kd_socket.recv(), timeout=5))
            leadership_task_delete = json.loads(
                await asyncio.wait_for(leadership_socket.recv(), timeout=5)
            )
            assert kd_task_delete["topic"] == "tasks"
            assert kd_task_delete["operation"] == "delete"
            assert kd_task_delete["data"]["_id"] == str(task_id)
            assert leadership_task_delete["data"]["_id"] == str(task_id)
    finally:
        database.alerts.delete_one({"_id": alert_id})
        database.performance_metrics.delete_one({"_id": metric_id})
        database.tasks.delete_one({"_id": task_id})
        database_client.close()

    try:
        async with connect(f"{args.websocket_url}?token=invalid-token"):
            raise AssertionError("WebSocket chấp nhận token không hợp lệ")
    except ConnectionClosedError as error:
        assert error.code == 1008
    except InvalidStatus as error:
        assert error.response.status_code == 403

    print("Realtime smoke test passed: Change Stream, WebSocket và manager scope.")


if __name__ == "__main__":
    asyncio.run(run_smoke(parse_args()))
