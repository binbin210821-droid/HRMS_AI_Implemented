import argparse
import json
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke-test Performance analytics API")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--password", default="DemoPassword123!")
    return parser.parse_args()


def request_json(
    base_url: str,
    path: str,
    token: str | None = None,
    method: str = "GET",
) -> tuple[int, object]:
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(f"{base_url}{path}", headers=headers, method=method)
    try:
        with urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read())
    except HTTPError as error:
        return error.code, json.loads(error.read())


def login(base_url: str, username: str, password: str) -> str:
    request = Request(
        f"{base_url}/api/auth/login",
        data=json.dumps({"username": username, "password": password}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=5) as response:
        return json.load(response)["access_token"]


def main(args: argparse.Namespace) -> None:
    leadership_token = login(args.base_url, "demo.leadership", args.password)
    manager_token = login(args.base_url, "demo.manager", args.password)
    status, employees = request_json(args.base_url, "/api/employees", leadership_token)
    assert status == 200
    status, departments = request_json(args.base_url, "/api/departments", leadership_token)
    assert status == 200
    kd_employee = next(item for item in employees if item["employee_code"] == "KD-NV-001")
    kd_department = next(item for item in departments if item["code"] == "KD")
    kt_department = next(item for item in departments if item["code"] == "KT")

    status, trend = request_json(
        args.base_url,
        f"/api/performance/analytics/employee/{kd_employee['id']}",
        manager_token,
    )
    assert status == 200 and len(trend["metrics"]) == 60
    status, forbidden_employee = request_json(
        args.base_url,
        f"/api/performance/analytics/employee/{next(item for item in employees if item['employee_code'] == 'KT-NV-001')['id']}",
        manager_token,
    )
    assert status == 403, forbidden_employee

    status, department = request_json(
        args.base_url,
        f"/api/performance/analytics/department/{kd_department['id']}",
        manager_token,
    )
    assert status == 200 and len(department["employees"]) == 5
    status, forbidden_department = request_json(
        args.base_url,
        f"/api/performance/analytics/department/{kt_department['id']}",
        manager_token,
    )
    assert status == 403, forbidden_department

    status, company = request_json(
        args.base_url, "/api/performance/analytics/company", leadership_token
    )
    assert status == 200 and len(company["departments"]) == 3
    status, manager_company = request_json(
        args.base_url, "/api/performance/analytics/company", manager_token
    )
    assert status == 403, manager_company

    print("Performance analytics smoke test passed: Mongo aggregation, 60-day trend and RBAC.")


if __name__ == "__main__":
    main(parse_args())
