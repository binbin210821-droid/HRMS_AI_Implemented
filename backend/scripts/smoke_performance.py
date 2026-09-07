import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from bson import ObjectId
from pymongo import MongoClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke-test Performance API và RBAC scope")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--password", default="DemoPassword123!")
    return parser.parse_args()


def request_json(
    base_url: str,
    path: str,
    token: str | None = None,
    method: str = "GET",
    body: dict | None = None,
) -> tuple[int, object]:
    headers = {"Accept": "application/json"}
    data = None
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode()
    request = Request(f"{base_url}{path}", headers=headers, method=method, data=data)
    try:
        with urlopen(request, timeout=5) as response:
            payload = response.read()
            return response.status, json.loads(payload) if payload else None
    except HTTPError as error:
        payload = error.read()
        return error.code, json.loads(payload) if payload else None


def login(base_url: str, username: str, password: str) -> str:
    status, response = request_json(
        base_url,
        "/api/auth/login",
        method="POST",
        body={"username": username, "password": password},
    )
    assert status == 200, response
    return response["access_token"]


def main(args: argparse.Namespace) -> None:
    leadership_token = login(args.base_url, "demo.leadership", args.password)
    manager_token = login(args.base_url, "demo.manager", args.password)

    status, all_metrics = request_json(args.base_url, "/api/performance", leadership_token)
    assert status == 200 and len(all_metrics) == 900, len(all_metrics)
    status, manager_metrics = request_json(args.base_url, "/api/performance", manager_token)
    assert status == 200 and len(manager_metrics) == 300, len(manager_metrics)

    status, employees = request_json(args.base_url, "/api/employees", leadership_token)
    assert status == 200, employees
    kd_employee = next(
        employee for employee in employees if employee["employee_code"] == "KD-NV-001"
    )
    kt_employee = next(
        employee for employee in employees if employee["employee_code"] == "KT-NV-001"
    )

    test_date = "2099-12-31"
    test_payload = {
        "employee_id": kd_employee["id"],
        "date": test_date,
        "tasks_completed": 4,
        "quality_score": 80,
        "note": "Smoke Performance",
    }
    settings = get_settings()
    client = MongoClient(settings.mongo_uri, serverSelectionTimeoutMS=5000)
    try:
        status, created = request_json(
            args.base_url, "/api/performance/daily", manager_token, method="POST", body=test_payload
        )
        assert status == 201, created
        assert created["performance_score"] == 86.0, created

        forbidden_payload = {**test_payload, "employee_id": kt_employee["id"]}
        status, forbidden = request_json(
            args.base_url,
            "/api/performance/daily",
            manager_token,
            method="POST",
            body=forbidden_payload,
        )
        assert status == 403, forbidden

        status, leadership_forbidden = request_json(
            args.base_url,
            "/api/performance/daily",
            leadership_token,
            method="POST",
            body=test_payload,
        )
        assert status == 403, leadership_forbidden
    finally:
        client[settings.database_name]["performance_metrics"].delete_one(
            {
                "employee_id": ObjectId(kd_employee["id"]),
                "date": datetime(2099, 12, 31, tzinfo=timezone.utc),
            }
        )
        client.close()

    print("Performance smoke test passed: 60 ngày, công thức 86.0 và RBAC scope.")


if __name__ == "__main__":
    main(parse_args())
