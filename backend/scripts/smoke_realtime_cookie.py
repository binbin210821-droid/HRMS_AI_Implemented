import argparse
import asyncio
import http.cookiejar
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import HTTPCookieProcessor, Request, build_opener

from bson import ObjectId
from pymongo import MongoClient
from websockets import connect
from websockets.exceptions import ConnectionClosedError, InvalidStatus

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import Settings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Smoke-test WebSocket realtime bằng cookie session mới"
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--websocket-url", default="ws://127.0.0.1:8000/ws/realtime")
    parser.add_argument("--password", default="DemoPassword123!")
    return parser.parse_args()


def login(base_url: str, username: str, password: str) -> http.cookiejar.CookieJar:
    jar = http.cookiejar.CookieJar()
    opener = build_opener(HTTPCookieProcessor(jar))
    request = Request(
        f"{base_url}/api/v1/auth/login",
        data=json.dumps({"username": username, "password": password}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with opener.open(request, timeout=5) as response:
        assert response.status == 200
        json.load(response)
    return jar


def cookie_header(jar: http.cookiejar.CookieJar) -> str:
    return "; ".join(f"{cookie.name}={cookie.value}" for cookie in jar)


async def run_smoke(args: argparse.Namespace) -> None:
    settings = Settings()
    database_client = MongoClient(settings.mongo_uri, serverSelectionTimeoutMS=5000)
    database = database_client[settings.database_name]
    kd = database.departments.find_one({"code": "KD"}, {"_id": 1})
    kt = database.departments.find_one({"code": "KT"}, {"_id": 1})
    assert kd and kt, "Thiếu dữ liệu seed KD/KT"

    kd_cookie = cookie_header(login(args.base_url, "demo.manager", args.password))
    kt_cookie = cookie_header(login(args.base_url, "demo.manager.tech", args.password))
    leadership_cookie = cookie_header(
        login(args.base_url, "demo.leadership", args.password)
    )
    alert_id = ObjectId()
    alert = {
        "_id": alert_id,
        "department_id": kd["_id"],
        "employee_id": ObjectId(),
        "message": "Cookie realtime smoke",
        "created_at": datetime.now(timezone.utc),
    }
    try:
        async with (
            connect(args.websocket_url, additional_headers={"Cookie": kd_cookie}) as kd_socket,
            connect(args.websocket_url, additional_headers={"Cookie": kt_cookie}) as kt_socket,
            connect(
                args.websocket_url, additional_headers={"Cookie": leadership_cookie}
            ) as leadership_socket,
        ):
            database.alerts.insert_one(alert)
            kd_event = json.loads(await asyncio.wait_for(kd_socket.recv(), timeout=5))
            leadership_event = json.loads(
                await asyncio.wait_for(leadership_socket.recv(), timeout=5)
            )
            assert kd_event["data"]["_id"] == str(alert_id)
            assert leadership_event["data"]["_id"] == str(alert_id)
            try:
                await asyncio.wait_for(kt_socket.recv(), timeout=1.5)
            except TimeoutError:
                pass
            else:
                raise AssertionError("Manager KT nhận alert ngoài scope KD")
    finally:
        database.alerts.delete_one({"_id": alert_id})
        database_client.close()

    try:
        async with connect(args.websocket_url):
            raise AssertionError("WebSocket chấp nhận kết nối không có cookie")
    except ConnectionClosedError as error:
        assert error.code == 1008
    except InvalidStatus as error:
        assert error.response.status_code == 403
    except HTTPError as error:
        assert error.code == 403

    print("Cookie realtime smoke test passed: cookie session và RBAC WebSocket scope.")


if __name__ == "__main__":
    asyncio.run(run_smoke(parse_args()))
