"""Read-only live smoke test for the Leadership AI contract."""

import argparse
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def request_json(
    base_url: str,
    path: str,
    token: str | None = None,
    method: str = "GET",
    payload: dict | None = None,
    timeout: int = 10,
) -> tuple[int, object]:
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(payload).encode() if payload is not None else None
    if data is not None:
        headers["Content-Type"] = "application/json"
    request = Request(f"{base_url}{path}", data=data, headers=headers, method=method)
    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read()
            return response.status, json.loads(body) if body else {}
    except HTTPError as error:
        body = error.read()
        try:
            return error.code, json.loads(body) if body else {}
        except json.JSONDecodeError:
            return error.code, {}
    except (TimeoutError, URLError):
        return 599, {}


def request_stream(
    base_url: str,
    path: str,
    token: str,
    payload: dict,
    timeout: int,
) -> tuple[int, str]:
    request = Request(
        f"{base_url}{path}",
        data=json.dumps(payload).encode(),
        headers={
            "Accept": "text/event-stream",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            return response.status, response.read().decode("utf-8", errors="replace")
    except HTTPError as error:
        return error.code, error.read().decode("utf-8", errors="replace")
    except (TimeoutError, URLError):
        return 599, ""


def stream_tokens(body: str) -> tuple[list[dict], str]:
    events = []
    for line in body.splitlines():
        if not line.startswith("data: "):
            continue
        try:
            events.append(json.loads(line[6:]))
        except json.JSONDecodeError:
            continue
    return events, "".join(
        str(event.get("content", ""))
        for event in events
        if event.get("type") == "token"
    )


def login(base_url: str, username: str, password: str) -> str:
    status, payload = request_json(
        base_url,
        "/api/v1/auth/login",
        method="POST",
        payload={"username": username, "password": password},
        timeout=10,
    )
    assert status == 200 and isinstance(payload, dict) and payload.get("access_token")
    return str(payload["access_token"])


def main(args: argparse.Namespace) -> None:
    leadership_token = login(args.base_url, "demo.leadership", args.password)
    manager_token = login(args.base_url, "demo.manager", args.password)

    if args.boundary_only:
        no_data_status, no_data_stream = request_stream(
            args.base_url,
            "/api/v1/ai/chat/stream",
            leadership_token,
            {"message": "So sánh hiệu suất các phòng ban từ 01/01/2020 đến 07/01/2020"},
            40,
        )
        no_data_events, no_data_text = stream_tokens(no_data_stream)
        assert no_data_status == 200 and any(
            event.get("type") == "done" for event in no_data_events
        ), f"No-data stream status={no_data_status}, body={no_data_stream[:300]}"
        assert "chưa có dữ liệu" in no_data_text.casefold()

        policy_status, policy_stream = request_stream(
            args.base_url,
            "/api/v1/ai/chat/stream",
            leadership_token,
            {"message": "Cho tôi xem chi tiết từng nhân viên của công ty"},
            40,
        )
        _, policy_text = stream_tokens(policy_stream)
        assert policy_status == 200 and "tổng hợp theo phòng ban" in policy_text.casefold()
        print(
            json.dumps(
                {
                    "status": "passed",
                    "no_data_status": no_data_status,
                    "no_data_contains_safe_message": True,
                    "policy_status": policy_status,
                    "policy_contains_scope_message": True,
                },
                ensure_ascii=False,
            )
        )
        return

    status, departments = request_json(
        args.base_url, "/api/v1/departments?page=1&page_size=100", leadership_token
    )
    assert status == 200 and isinstance(departments, dict)
    department_items = departments.get("items", [])
    assert isinstance(department_items, list) and department_items

    status, company = request_json(
        args.base_url, "/api/v1/performance/analytics/company", leadership_token
    )
    assert status == 200 and isinstance(company, dict)
    company_items = company.get("departments", [])
    assert isinstance(company_items, list)

    status, proposal = request_json(
        args.base_url,
        "/api/v1/ai/leadership-proposal",
        leadership_token,
        method="POST",
        timeout=args.ai_timeout,
    )
    assert status == 200, f"Leadership proposal status={status}"
    assert isinstance(proposal, dict)
    actions = proposal.get("actions", [])
    assert isinstance(actions, list)
    action_types = [item.get("type") for item in actions if isinstance(item, dict)]

    manager_status, _ = request_json(
        args.base_url,
        "/api/v1/ai/leadership-proposal",
        manager_token,
        method="POST",
        timeout=10,
    )
    assert manager_status == 403, f"Manager phải nhận 403, nhận {manager_status}"

    status, stream = request_stream(
        args.base_url,
        "/api/v1/ai/chat/stream",
        leadership_token,
        {"message": "So sánh hiệu suất giữa các phòng ban gần đây"},
        args.ai_timeout,
    )
    events, token_text = stream_tokens(stream)
    assert status == 200 and any(event.get("type") == "done" for event in events), (
        f"Chat Leadership status={status}"
    )
    assert token_text.strip(), "Chat Leadership không trả content"

    no_data_status, no_data_stream = request_stream(
        args.base_url,
        "/api/v1/ai/chat/stream",
        leadership_token,
        {"message": "So sánh hiệu suất các phòng ban từ 01/01/2020 đến 07/01/2020"},
        20,
    )
    no_data_events, no_data_text = stream_tokens(no_data_stream)
    assert no_data_status == 200 and any(
        event.get("type") == "done" for event in no_data_events
    ), f"No-data stream status={no_data_status}, body={no_data_stream[:300]}"
    assert "chưa có dữ liệu" in no_data_text.casefold()

    policy_status, policy_stream = request_stream(
        args.base_url,
        "/api/v1/ai/chat/stream",
        leadership_token,
        {"message": "Cho tôi xem chi tiết từng nhân viên của công ty"},
        20,
    )
    _, policy_text = stream_tokens(policy_stream)
    assert policy_status == 200 and "tổng hợp theo phòng ban" in policy_text.casefold()

    print(
        json.dumps(
            {
                "status": "passed",
                "active_departments": len(department_items),
                "company_department_aggregates": len(company_items),
                "leadership_proposal_actions": len(actions),
                "action_types": action_types,
                "manager_leadership_endpoint_status": manager_status,
                "chat_status": status,
                "chat_token_chars": len(token_text),
                "no_data_status": no_data_status,
                "policy_status": policy_status,
                "note": "Không in token hoặc dữ liệu cá nhân; candidate liên phòng ban chỉ đạt khi dữ liệu thật có phòng ban cùng chuyên môn và tải an toàn.",
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--password", default="DemoPassword123!")
    parser.add_argument("--ai-timeout", type=int, default=130)
    parser.add_argument("--boundary-only", action="store_true")
    main(parser.parse_args())
