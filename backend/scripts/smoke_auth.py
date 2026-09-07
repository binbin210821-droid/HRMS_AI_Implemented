import argparse
import json
import sys
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import Settings
from app.core.security import create_access_token, decode_access_token


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke-test login và endpoint tài khoản hiện tại")
    parser.add_argument("--base-url", default="http://127.0.0.1:8001")
    parser.add_argument("--username", default="demo.manager")
    parser.add_argument("--password", default="DemoPassword123!")
    return parser.parse_args()


def post_login(base_url: str, username: str, password: str) -> dict:
    request = Request(
        f"{base_url}/api/auth/login",
        data=json.dumps({"username": username, "password": password}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=5) as response:
        return json.load(response)


def get_me(base_url: str, token: str) -> dict:
    request = Request(
        f"{base_url}/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urlopen(request, timeout=5) as response:
        return json.load(response)


def assert_unauthorized(base_url: str, token: str) -> None:
    try:
        get_me(base_url, token)
    except HTTPError as error:
        assert error.code == 401
        return
    raise AssertionError("Token không hợp lệ nhưng endpoint vẫn cho phép truy cập")


if __name__ == "__main__":
    args = parse_args()
    token_response = post_login(args.base_url, args.username, args.password)
    claims = decode_access_token(token_response["access_token"], Settings())
    current_user = get_me(args.base_url, token_response["access_token"])
    assert claims["role"] == "manager"
    assert claims["department_id"]
    assert current_user["role"] == "manager"
    assert current_user["department_id"] == claims["department_id"]
    settings = Settings()
    expired_token = create_access_token(
        claims["sub"],
        settings,
        expires_minutes=-1,
        role=claims["role"],
        department_id=claims["department_id"],
    )
    assert_unauthorized(args.base_url, expired_token)
    wrong_signature = create_access_token(
        claims["sub"],
        Settings(jwt_secret="wrong-secret"),
        role=claims["role"],
        department_id=claims["department_id"],
    )
    assert_unauthorized(args.base_url, wrong_signature)
    print("Live auth smoke test passed: login, JWT claims và /api/auth/me.")
