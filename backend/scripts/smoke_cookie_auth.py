import argparse
import http.cookiejar
import json
import sys
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import HTTPCookieProcessor, Request, build_opener

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke-test cookie session và CSRF auth")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--username", default="demo.manager")
    parser.add_argument("--password", default="DemoPassword123!")
    return parser.parse_args()


def cookie_value(jar: http.cookiejar.CookieJar, name: str) -> str:
    for cookie in jar:
        if cookie.name == name:
            return cookie.value
    raise AssertionError(f"Không nhận được cookie {name}")


def request(opener, url: str, *, method: str = "GET", body: dict | None = None, csrf: str = ""):
    headers = {"Accept": "application/json"}
    payload = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        payload = json.dumps(body).encode()
    if csrf:
        headers["X-CSRF-Token"] = csrf
    return opener.open(Request(url, data=payload, headers=headers, method=method), timeout=5)


if __name__ == "__main__":
    args = parse_args()
    settings = get_settings()
    jar = http.cookiejar.CookieJar()
    opener = build_opener(HTTPCookieProcessor(jar))
    login_response = request(
        opener,
        f"{args.base_url}/api/v1/auth/login",
        method="POST",
        body={"username": args.username, "password": args.password},
    )
    assert login_response.status == 200
    login_payload = json.load(login_response)
    assert login_payload.get("access_token"), "Compatibility token không có trong login response"
    assert cookie_value(jar, settings.auth_access_cookie_name)
    csrf = cookie_value(jar, settings.auth_csrf_cookie_name)

    with request(opener, f"{args.base_url}/api/v1/auth/me") as me_response:
        current_user = json.load(me_response)
    assert current_user["username"] == args.username

    with request(opener, f"{args.base_url}/api/v1/auth/logout", method="POST", csrf=csrf) as logout:
        assert logout.status == 204
    try:
        request(opener, f"{args.base_url}/api/v1/auth/me")
    except HTTPError as error:
        assert error.code == 401
    else:
        raise AssertionError("Session vẫn được chấp nhận sau logout")
    print("Cookie auth smoke test passed: login, /me, CSRF logout và session clear.")
