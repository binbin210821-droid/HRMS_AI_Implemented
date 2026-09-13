r"""Kiểm thử đa process cho Redis rate limit và idempotency.

Chạy tường minh trên máy đã có MongoDB replica set, Redis và MinIO:

    $env:RUN_MULTI_WORKER_TESTS = "1"
    .\.venv\Scripts\python.exe -m pytest tests/test_multi_worker_integration.py -m integration -q

Các test này dùng một database MongoDB cô lập theo PID, được seed tối thiểu bằng
script dữ liệu nền rồi xóa toàn bộ database sau test. Redis dùng database 15 riêng
để không ảnh hưởng quota của môi trường đang chạy.
"""

from __future__ import annotations

import asyncio
import os
import socket
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import httpx
import pytest
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient
from redis.asyncio import Redis

pytestmark = pytest.mark.integration


BACKEND_ROOT = Path(__file__).resolve().parents[1]
TEST_REDIS_DB = 15
TEST_DATABASE_NAME = f"hrms_phase15_{os.getpid()}"
TEST_USERNAME = os.getenv("MULTI_WORKER_TEST_USERNAME", "demo.manager")
TEST_PASSWORD = os.getenv("MULTI_WORKER_TEST_PASSWORD", "DemoPassword123!")
LEADERSHIP_USERNAME = os.getenv("MULTI_WORKER_LEADERSHIP_USERNAME", "demo.leadership")
LEADERSHIP_PASSWORD = os.getenv("MULTI_WORKER_LEADERSHIP_PASSWORD", TEST_PASSWORD)


def _redis_test_url() -> str:
    configured = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    parsed = urlsplit(configured)
    return urlunsplit((parsed.scheme, parsed.netloc, f"/{TEST_REDIS_DB}", "", ""))


async def _clear_test_redis(redis_url: str) -> None:
    client = Redis.from_url(redis_url, decode_responses=False)
    try:
        keys: list[bytes] = []
        async for key in client.scan_iter(match=b"rl:*"):
            keys.append(key)
        async for key in client.scan_iter(match=b"idem:*"):
            keys.append(key)
        if keys:
            await client.delete(*keys)
    finally:
        await client.aclose()


async def _seed_test_alert(mongo_uri: str) -> None:
    client = AsyncIOMotorClient(mongo_uri)
    try:
        database = client[TEST_DATABASE_NAME]
        department = await database["departments"].find_one({"code": "KD"})
        assert department is not None
        employee = await database["employees"].find_one({"department_id": department["_id"]})
        assert employee is not None
        now = datetime.now(timezone.utc)
        detected_date = datetime.combine(now.date(), datetime.min.time(), tzinfo=timezone.utc)
        await database["alerts"].insert_one(
            {
                "_id": ObjectId(),
                "alert_type": "overload",
                "severity": "high",
                "status": "open",
                "employee_id": employee["_id"],
                "department_id": department["_id"],
                "employee_code": employee["employee_code"],
                "employee_name": employee["full_name"],
                "title": "Giai đoạn 15 - cảnh báo kiểm thử",
                "message": "Dữ liệu kiểm thử cô lập cho idempotency đa worker.",
                "suggested_action": "Không áp dụng vào dữ liệu vận hành.",
                "detected_dates": [detected_date],
                "fingerprint": "phase15-multi-worker-alert",
                "created_at": now,
                "updated_at": now,
            }
        )
        assert (
            await database["alerts"].count_documents(
                {
                    "department_id": department["_id"],
                    "alert_type": "overload",
                    "severity": "high",
                    "status": "open",
                }
            )
            == 1
        )
    finally:
        client.close()


async def _drop_test_database(mongo_uri: str) -> None:
    client = AsyncIOMotorClient(mongo_uri)
    try:
        await client.drop_database(TEST_DATABASE_NAME)
    finally:
        client.close()


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@dataclass
class MultiWorkerServer:
    process: subprocess.Popen[Any]
    base_url: str
    log_path: Path
    log_file: Any

    def log_tail(self) -> str:
        self.log_file.flush()
        try:
            return self.log_path.read_text(encoding="utf-8")[-6000:]
        except OSError:
            return ""

    def stop(self) -> None:
        if os.name == "nt":
            # Uvicorn's Windows spawn supervisor can exit while worker
            # children remain alive; terminate the whole owned tree even when
            # Popen.poll() already reports the supervisor as exited.
            subprocess.run(
                ["taskkill", "/PID", str(self.process.pid), "/T", "/F"],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        elif self.process.poll() is None:
            self.process.terminate()
        if self.process.poll() is None:
            try:
                self.process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=15)
        if not self.log_file.closed:
            self.log_file.close()


@pytest.fixture(scope="module")
def multi_worker_server() -> MultiWorkerServer:
    if os.getenv("RUN_MULTI_WORKER_TESTS") != "1":
        pytest.skip("Đặt RUN_MULTI_WORKER_TESTS=1 để chạy kiểm thử đa worker.")

    port = _free_port()
    environment = os.environ.copy()
    environment.update(
        {
            "MONGO_URI": environment.get(
                "MONGO_URI", "mongodb://localhost:27017/hrms?replicaSet=rs0"
            ),
            "DATABASE_NAME": TEST_DATABASE_NAME,
            "REDIS_URL": _redis_test_url(),
            "RATE_LIMIT_BACKEND": "redis",
            "RATE_LIMIT_ENABLED": "true",
            "RATE_LIMIT_SHADOW_MODE": "true",
            # Chỉ enforcement read_light để test quota chung; các request upload
            # giữ shadow mode và không làm test phụ thuộc quota nghiệp vụ khác.
            "RATE_LIMIT_ENFORCED_GROUPS": "read_light",
            "RATE_LIMIT_DEFAULT": "3",
            "RATE_LIMIT_OPERATIONAL": "3",
            "IDEMPOTENCY_ENABLED": "true",
            "STORAGE_DIRECT_UPLOAD_ENABLED": "true",
        }
    )
    seed = subprocess.run(
        [
            sys.executable,
            "scripts/seed_base_data.py",
            "--employees-per-department",
            "5",
        ],
        cwd=BACKEND_ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    if seed.returncode != 0:
        raise RuntimeError(
            "Không thể seed database cô lập cho test multi-worker: "
            f"{seed.stdout}\n{seed.stderr}"
        )
    asyncio.run(_seed_test_alert(environment["MONGO_URI"]))
    asyncio.run(_clear_test_redis(environment["REDIS_URL"]))

    command = [
        sys.executable,
        "-m",
        "uvicorn",
        "app.main:app",
        "--workers",
        "4",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
    ]
    log_fd, log_name = tempfile.mkstemp(prefix="hrms-phase15-", suffix=".log")
    os.close(log_fd)
    log_path = Path(log_name)
    log_file = log_path.open("w", encoding="utf-8")
    process = subprocess.Popen(
        command,
        cwd=BACKEND_ROOT,
        env=environment,
        stdin=subprocess.DEVNULL,
        stdout=log_file,
        stderr=subprocess.STDOUT,
    )
    server = MultiWorkerServer(process, f"http://127.0.0.1:{port}", log_path, log_file)
    try:
        with httpx.Client(timeout=2.0) as client:
            for _ in range(60):
                if process.poll() is not None:
                    raise RuntimeError("Uvicorn multi-worker dừng trước khi health sẵn sàng.")
                try:
                    if client.get(f"{server.base_url}/api/health").status_code == 200:
                        yield server
                        return
                except httpx.HTTPError:
                    pass
                asyncio.run(asyncio.sleep(0.25))
        raise RuntimeError("Không thể khởi động backend 4 worker trong 15 giây.")
    except BaseException:
        server.stop()
        raise
    finally:
        server.stop()
        asyncio.run(_clear_test_redis(environment["REDIS_URL"]))
        asyncio.run(_drop_test_database(environment["MONGO_URI"]))
        try:
            log_path.unlink()
        except FileNotFoundError:
            pass


@pytest.fixture(scope="module")
def test_redis_url(multi_worker_server: MultiWorkerServer) -> str:
    del multi_worker_server
    return _redis_test_url()


async def _login(
    client: httpx.AsyncClient,
    username: str = TEST_USERNAME,
    password: str = TEST_PASSWORD,
) -> None:
    response = await client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200, response.text
    assert client.cookies.get("hrms_csrf_token")


def _csrf_headers(client: httpx.AsyncClient, **extra: str) -> dict[str, str]:
    csrf = client.cookies.get("hrms_csrf_token")
    assert csrf
    return {"X-CSRF-Token": csrf, **extra}


@pytest.mark.asyncio
async def test_rate_limit_is_shared_by_four_workers(
    multi_worker_server: MultiWorkerServer,
    test_redis_url: str,
) -> None:
    await _clear_test_redis(test_redis_url)
    async with httpx.AsyncClient(base_url=multi_worker_server.base_url, timeout=20.0) as client:
        await _login(client)
        responses = await asyncio.gather(
            *(client.get("/api/v1/departments?page_size=20") for _ in range(40))
        )

    statuses = [response.status_code for response in responses]
    assert statuses.count(200) == 3
    assert statuses.count(429) == 37
    assert all(response.headers.get("X-RateLimit-Limit") == "3" for response in responses)


@pytest.mark.asyncio
async def test_idempotency_is_shared_by_four_workers(
    multi_worker_server: MultiWorkerServer,
    test_redis_url: str,
) -> None:
    await _clear_test_redis(test_redis_url)
    created_ids: set[str] = set()
    mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/hrms?replicaSet=rs0")
    database_name = TEST_DATABASE_NAME
    mongo = AsyncIOMotorClient(mongo_uri)

    try:
        async with httpx.AsyncClient(
            base_url=multi_worker_server.base_url, timeout=30.0
        ) as client:
            try:
                await _login(client, LEADERSHIP_USERNAME, LEADERSHIP_PASSWORD)
                departments = await client.get("/api/v1/departments?page_size=20")
                assert departments.status_code == 200, departments.text
                department_items = departments.json()["items"]
                if not department_items:
                    pytest.skip("Database test chưa có phòng ban cho demo.manager.")
                department = next(
                    (item for item in department_items if item.get("code") == "KD"),
                    department_items[0],
                )
                department_id = department["id"]
                open_alerts = await client.get(
                    f"/api/v1/alerts?status=open&department_id={department_id}&page_size=20"
                )
                assert open_alerts.status_code == 200, open_alerts.text
                assert open_alerts.json()["items"], {
                    "department_id": department_id,
                    "alerts": open_alerts.json(),
                    "server_log_tail": multi_worker_server.log_tail(),
                }

                payload = {
                    "alert_type": "all",
                    "severity": "all",
                    "note": "Kiểm thử idempotency đa worker Giai đoạn 15",
                }
                headers = _csrf_headers(
                    client,
                    **{
                        "Idempotency-Key": "phase15-multi-worker-alert-directive",
                    },
                )

                responses = await asyncio.gather(
                    *(
                        client.post(
                            f"/api/v1/coordination/department-directives/{department_id}",
                            json=payload,
                            headers=headers,
                        )
                        for _ in range(2)
                    )
                )
                successful = [response for response in responses if response.status_code == 201]
                assert len(successful) >= 1, {
                    "responses": [
                        {"status": response.status_code, "body": response.text}
                        for response in responses
                    ],
                    "server_log_tail": multi_worker_server.log_tail(),
                }
                assert all(response.status_code in {201, 409} for response in responses)
                for response in successful:
                    created_ids.add(response.json()["id"])
                assert len(created_ids) == 1, (
                    "Một Idempotency-Key đã tạo nhiều alert directive khác nhau."
                )

                replay = await client.post(
                    f"/api/v1/coordination/department-directives/{department_id}",
                    json=payload,
                    headers=headers,
                )
                assert replay.status_code == 201, replay.text
                assert replay.headers.get("Idempotency-Replayed") == "true"
                assert replay.json() == successful[0].json()

                stored_count = await mongo[database_name]["department_alert_directives"].count_documents(
                    {"_id": {"$in": [ObjectId(item) for item in created_ids]}}
                )
                assert stored_count == 1
            finally:
                await mongo[database_name]["department_alert_directives"].delete_many(
                    {"_id": {"$in": [ObjectId(item) for item in created_ids]}}
                )
                csrf = client.cookies.get("hrms_csrf_token")
                if csrf:
                    await client.post(
                        "/api/auth/logout", headers={"X-CSRF-Token": csrf}
                    )
                await _clear_test_redis(test_redis_url)
    finally:
        mongo.close()
