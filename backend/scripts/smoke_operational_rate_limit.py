"""Live-smoke enforcement cho nhóm read_operational."""

import argparse
import json
import sys
from http.cookiejar import CookieJar
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import HTTPCookieProcessor, Request, build_opener

from redis import Redis

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def request_json(opener, url: str, method: str, payload: dict | None = None):
    data = json.dumps(payload).encode() if payload is not None else None
    headers = {"Content-Type": "application/json"} if data is not None else {}
    request = Request(url, data=data, headers=headers, method=method)
    try:
        with opener.open(request, timeout=10) as response:
            return response.status, dict(response.headers), response.read()
    except HTTPError as error:
        return error.code, dict(error.headers), error.read()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8001")
    parser.add_argument("--redis-url", default="redis://localhost:6379/0")
    parser.add_argument("--username", default="demo.manager")
    parser.add_argument("--password", default="DemoPassword123!")
    parser.add_argument("--requests", type=int, default=121)
    args = parser.parse_args()

    jar = CookieJar()
    opener = build_opener(HTTPCookieProcessor(jar))
    login_status, _, _ = request_json(
        opener,
        f"{args.base_url}/api/v1/auth/login",
        "POST",
        {"username": args.username, "password": args.password},
    )
    if login_status != 200:
        raise SystemExit(f"Login thất bại: {login_status}")

    me_status, _, me_body = request_json(opener, f"{args.base_url}/api/v1/auth/me", "GET")
    if me_status != 200:
        raise SystemExit(f"/me thất bại: {me_status}")
    user_id = json.loads(me_body)["user_id"]

    redis = Redis.from_url(args.redis_url)
    redis_key = f"rl:user:{user_id}:read_operational"
    redis.delete(redis_key)

    results = []
    try:
        for index in range(args.requests):
            path = "/api/v1/alerts?page_size=100" if index % 2 == 0 else "/api/v1/tasks?page_size=100"
            status, headers, _ = request_json(opener, f"{args.base_url}{path}", "GET")
            normalized_headers = {key.lower(): value for key, value in headers.items()}
            results.append(
                {
                    "index": index + 1,
                    "path": path.split("?", 1)[0],
                    "status": status,
                    "limit": normalized_headers.get("x-ratelimit-limit"),
                    "remaining": normalized_headers.get("x-ratelimit-remaining"),
                    "retry_after": normalized_headers.get("retry-after"),
                }
            )
    finally:
        redis.delete(redis_key)
        redis.close()

    csrf = next(cookie.value for cookie in jar if cookie.name == "hrms_csrf_token")
    logout_request = Request(
        f"{args.base_url}/api/v1/auth/logout",
        headers={"X-CSRF-Token": csrf},
        method="POST",
    )
    with opener.open(logout_request, timeout=10) as response:
        logout_status = response.status

    first_denied = next((item for item in results if item["status"] == 429), None)
    summary = {
        "login": login_status,
        "requests": len(results),
        "successes": sum(item["status"] == 200 for item in results),
        "denied": sum(item["status"] == 429 for item in results),
        "first_denied": first_denied,
        "logout": logout_status,
    }
    print(json.dumps(summary, ensure_ascii=False))

    if len(results) >= 121:
        if any(item["status"] != 200 for item in results[:120]):
            raise SystemExit("Có request trong quota bị chặn ngoài dự kiến")
        if results[120]["status"] != 429:
            raise SystemExit("Request thứ 121 không bị chặn; enforcement chưa hoạt động")


if __name__ == "__main__":
    main()
