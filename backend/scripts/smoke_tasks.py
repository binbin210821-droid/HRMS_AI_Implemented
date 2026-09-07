"""Kiểm tra API công việc trả đúng dữ liệu seed và cách ly scope phòng ban."""

import argparse
import json
import sys
from pathlib import Path
from urllib.request import Request, urlopen

from pymongo import MongoClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import Settings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke-test API công việc và deadline")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
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


def get_tasks(base_url: str, token: str) -> list[dict]:
    request = Request(
        f"{base_url}/api/tasks",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urlopen(request, timeout=5) as response:
        return json.load(response)


def run_smoke(args: argparse.Namespace) -> None:
    settings = Settings()
    database_client = MongoClient(settings.mongo_uri, serverSelectionTimeoutMS=5000)
    try:
        database = database_client[settings.database_name]
        manager = database.users.find_one({"username": "demo.manager"}, {"department_id": 1})
        assert manager and manager.get("department_id"), "Thiếu tài khoản demo.manager"
        department_id = str(manager["department_id"])

        manager_tasks = get_tasks(
            args.base_url,
            login(args.base_url, "demo.manager", args.password),
        )
        assert manager_tasks, "API chưa trả công việc seed cho Manager"
        assert all(task["department_id"] == department_id for task in manager_tasks)
        assert all(task["employee_name"] and task["due_date"] for task in manager_tasks)

        leadership_tasks = get_tasks(
            args.base_url,
            login(args.base_url, "demo.leadership", args.password),
        )
        assert len(leadership_tasks) >= len(manager_tasks)
        print(
            "Tasks smoke test passed: "
            f"Manager={len(manager_tasks)}, Leadership={len(leadership_tasks)}, "
            "dữ liệu có tên nhân viên và deadline."
        )
    finally:
        database_client.close()


if __name__ == "__main__":
    run_smoke(parse_args())
