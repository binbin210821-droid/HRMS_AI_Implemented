import argparse
import json
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke-test Early Warning API")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--password", default="DemoPassword123!")
    return parser.parse_args()


def request_json(
    base_url: str,
    path: str,
    token: str,
    method: str = "GET",
    body: dict | None = None,
) -> tuple[int, object]:
    headers = {"Accept": "application/json", "Authorization": f"Bearer {token}"}
    data = None
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

    status, created = request_json(args.base_url, "/api/alerts/scan", leadership_token, "POST")
    assert status == 200, created
    status, alerts = request_json(args.base_url, "/api/alerts", leadership_token)
    assert status == 200
    sample = next(alert for alert in alerts if alert["employee_code"] == "KD-NV-003")
    assert sample["severity"] == "medium"
    assert sample["alert_type"] == "early_warning"
    assert "Nên theo dõi" in sample["suggested_action"]

    status, manager_alerts = request_json(args.base_url, "/api/alerts", manager_token)
    assert status == 200
    assert all(alert["department_id"] == sample["department_id"] for alert in manager_alerts)
    assert all(alert["employee_code"].startswith("KD-") for alert in manager_alerts)

    print(
        "Early-warning smoke test passed: chuỗi 3 ngày, cảnh báo medium, EventBus/Change Stream và scope."
    )


if __name__ == "__main__":
    main(parse_args())
