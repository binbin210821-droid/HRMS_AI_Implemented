import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from bson import ObjectId
from pymongo import MongoClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings
from app.core.time import business_clock


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
        "/api/v1/auth/login",
        method="POST",
        body={"username": username, "password": password},
    )
    assert status == 200, response
    return response["access_token"]


def request_all(base_url: str, path: str, token: str) -> list[dict]:
    """Read every page from a list endpoint, supporting legacy and page-based contracts."""
    if path == "/api/v1/employees":
        items: list[dict] = []
        page = 1
        while True:
            status, payload = request_json(
                base_url, f"{path}?page={page}&page_size=100", token
            )
            assert status == 200 and isinstance(payload, dict), payload
            items.extend(payload["items"])
            if not payload["has_next"]:
                return items
            page += 1

    page_size = 100
    offset = 0
    items: list[dict] = []
    while True:
        separator = "&" if "?" in path else "?"
        status, page = request_json(
            base_url,
            f"{path}{separator}offset={offset}&limit={page_size}",
            token,
        )
        assert status == 200 and isinstance(page, list), page
        items.extend(page)
        if len(page) < page_size:
            return items
        offset += page_size


def main(args: argparse.Namespace) -> None:
    leadership_token = login(args.base_url, "demo.leadership", args.password)
    manager_token = login(args.base_url, "demo.manager", args.password)

    employees = request_all(args.base_url, "/api/v1/employees", leadership_token)
    manager_employees = request_all(args.base_url, "/api/v1/employees", manager_token)
    today = business_clock.today()
    start_date = today - timedelta(days=59)
    metrics_path = (
        f"/api/v1/performance?start_date={start_date.isoformat()}"
        f"&end_date={today.isoformat()}"
    )
    all_metrics = request_all(args.base_url, metrics_path, leadership_token)
    manager_metrics = request_all(args.base_url, metrics_path, manager_token)
    expected_all = len(employees) * 60
    expected_manager = len(manager_employees) * 60
    assert len(all_metrics) == expected_all, (len(all_metrics), expected_all)
    assert len(manager_metrics) == expected_manager, (len(manager_metrics), expected_manager)

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
