import argparse
import json
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke-test overload APIs")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--password", default="DemoPassword123!")
    return parser.parse_args()


def request_json(base_url: str, path: str, token: str, method: str = "GET", body=None):
    headers = {"Accept": "application/json", "Authorization": f"Bearer {token}"}
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode()
    request = Request(f"{base_url}{path}", headers=headers, method=method, data=data)
    try:
        with urlopen(request, timeout=10) as response:
            content = response.read()
            return response.status, json.loads(content) if content else None
    except HTTPError as error:
        content = error.read()
        return error.code, json.loads(content) if content else None


def login(base_url: str, username: str, password: str) -> str:
    request = Request(
        f"{base_url}/api/v1/auth/login",
        data=json.dumps({"username": username, "password": password}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=10) as response:
        return json.load(response)["access_token"]


def main(args: argparse.Namespace) -> None:
    leadership_token = login(args.base_url, "demo.leadership", args.password)
    manager_token = login(args.base_url, "demo.manager", args.password)

    status, scan = request_json(args.base_url, "/api/v1/overload/scans", leadership_token, "POST")
    assert status == 200, scan
    # Scan is idempotent: the first run creates logs, later runs may return zero.
    assert scan["created_count"] >= 0, scan

    status, leadership_logs = request_json(args.base_url, "/api/v1/overload", leadership_token)
    assert status == 200, leadership_logs
    leadership_logs = leadership_logs["items"]
    log_a = next(log for log in leadership_logs if log["employee_code"] == "KD-NV-001")
    log_b = next(log for log in leadership_logs if log["employee_code"] == "KD-NV-002")
    assert "Khối lượng công việc cao" in log_a["trigger_reason_labels"], log_a
    assert "Chất lượng công việc giảm mạnh" in log_b["trigger_reason_labels"], log_b
    assert all(
        candidate["tasks_completed"] <= 2 and candidate["quality_score"] >= 80
        for candidate in log_a["suggested_candidates"]
    )
    status, employees = request_json(
        args.base_url, "/api/v1/employees?page=1&page_size=100", leadership_token
    )
    assert status == 200, employees
    department_employee_codes = {
        employee["employee_code"]
        for employee in employees["items"]
        if employee["department_id"] == log_a["department_id"]
    }
    assert all(
        candidate["employee_code"] in department_employee_codes
        for candidate in log_a["suggested_candidates"]
    )

    status, alerts = request_json(args.base_url, "/api/v1/alerts?alert_type=all", leadership_token)
    assert status == 200, alerts
    alerts = alerts["items"]
    high_alerts = [alert for alert in alerts if alert["alert_type"] == "overload"]
    assert any(
        alert["employee_code"] == "KD-NV-001" and alert["severity"] == "high"
        for alert in high_alerts
    )
    assert any(
        alert["employee_code"] == "KD-NV-002" and alert["severity"] == "high"
        for alert in high_alerts
    )

    status, manager_logs = request_json(args.base_url, "/api/v1/overload", manager_token)
    assert status == 200, manager_logs
    manager_logs = manager_logs["items"]
    assert manager_logs and all(
        log["department_id"] == log_a["department_id"] for log in manager_logs
    )

    print("Overload smoke test passed: điều kiện A/B, rebalancer, Alert high và RBAC scope.")


if __name__ == "__main__":
    main(parse_args())
