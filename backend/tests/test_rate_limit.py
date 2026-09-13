import asyncio
import logging
from types import SimpleNamespace

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import Settings
from app.core.http_contract import RequestIdMiddleware, install_http_contract
from app.core.security import create_access_token
from app.infrastructure.idempotency import (
    IdempotencyContext,
    IdempotencyMiddleware,
    IdempotencyReplay,
    InMemoryIdempotencyStore,
    RedisIdempotencyStore,
    StoredResponse,
    _idempotency_key,
    complete_idempotency,
    handle_idempotency_replay,
    idempotent,
)
from app.infrastructure.rate_limit import (
    InMemoryRateLimiter,
    RateLimitKeyBuilder,
    RateLimitMiddleware,
    RateLimitPolicy,
    RateLimitRule,
    RedisRateLimiter,
    UnavailableRateLimiter,
    rate_limit_group,
)
from app.infrastructure.rate_limit import middleware as rate_limit_middleware
from app.realtime.websocket import realtime_websocket

TEST_ITEM_IDEMPOTENCY = Depends(idempotent("test_item"))
FAILING_ITEM_IDEMPOTENCY = Depends(idempotent("failing_item"))


def make_settings(**overrides) -> Settings:
    values = {
        "rate_limit_enabled": True,
        "rate_limit_backend": "memory",
        "rate_limit_shadow_mode": False,
        "rate_limit_enforced_groups": "",
        "idempotency_enabled": False,
        "rate_limit_default": 2,
        "rate_limit_login": 1,
        "rate_limit_fail_mode": "open",
    }
    values.update(overrides)
    return Settings(**values)


def build_app(settings: Settings, limiter) -> FastAPI:
    app = FastAPI()
    app.state.settings = settings
    app.state.rate_limiter = limiter
    app.state.rate_limit_policy = RateLimitPolicy(settings)
    app.state.rate_limit_key_builder = RateLimitKeyBuilder(settings)
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(RateLimitMiddleware, limiter=limiter, settings=settings)
    install_http_contract(app)

    @app.get("/api/v1/items", dependencies=[Depends(rate_limit_group("read_light"))])
    async def items() -> dict[str, bool]:
        return {"ok": True}

    @app.get("/api/items", dependencies=[Depends(rate_limit_group("read_light"))])
    async def legacy_items() -> dict[str, bool]:
        return {"ok": True}

    @app.get(
        "/api/v1/operational-alerts",
        dependencies=[Depends(rate_limit_group("read_operational"))],
    )
    async def operational_alerts() -> dict[str, bool]:
        return {"ok": True}

    @app.get(
        "/api/v1/operational-tasks",
        dependencies=[Depends(rate_limit_group("read_operational"))],
    )
    async def operational_tasks() -> dict[str, bool]:
        return {"ok": True}

    @app.get(
        "/api/v1/heavy-items",
        dependencies=[Depends(rate_limit_group("read_heavy"))],
    )
    async def heavy_items() -> dict[str, bool]:
        return {"ok": True}

    @app.post("/api/v1/auth/login", dependencies=[Depends(rate_limit_group("login"))])
    async def login() -> dict[str, bool]:
        return {"ok": True}

    @app.post("/api/v1/mutations", dependencies=[Depends(rate_limit_group("mutation"))])
    async def mutation() -> dict[str, bool]:
        return {"ok": True}

    return app


def test_in_memory_limiter_denies_after_limit() -> None:
    limiter = InMemoryRateLimiter()

    import asyncio

    first = asyncio.run(limiter.check("test", 1, 60))
    second = asyncio.run(limiter.check("test", 1, 60))

    assert first.allowed is True
    assert first.remaining == 0
    assert second.allowed is False
    assert second.retry_after_seconds >= 1


def test_rate_limit_denial_uses_api_error_contract_and_headers() -> None:
    client = TestClient(build_app(make_settings(), InMemoryRateLimiter()))

    assert client.get("/api/v1/items", headers={"X-Request-ID": "trace-rate"}).status_code == 200
    response = client.get("/api/v1/items", headers={"X-Request-ID": "trace-rate"})

    assert response.status_code == 200
    assert response.headers["X-RateLimit-Limit"] == "2"
    response = client.get("/api/v1/items", headers={"X-Request-ID": "trace-rate"})
    assert response.status_code == 429
    assert response.json()["code"] == "rate_limit_exceeded"
    assert response.json()["request_id"] == "trace-rate"
    assert response.headers["Retry-After"]


def test_shadow_mode_allows_request_and_marks_response() -> None:
    settings = make_settings(rate_limit_shadow_mode=True, rate_limit_default=1)
    client = TestClient(build_app(settings, InMemoryRateLimiter()))

    assert client.get("/api/items").status_code == 200
    response = client.get("/api/v1/items")

    assert response.status_code == 200
    assert response.headers["X-RateLimit-Shadow"] == "true"


def test_shadow_mode_records_allowed_and_shadow_denied_observations(caplog) -> None:
    settings = make_settings(rate_limit_shadow_mode=True, rate_limit_default=1)
    client = TestClient(build_app(settings, InMemoryRateLimiter()))
    caplog.set_level(logging.INFO, logger="app.infrastructure.rate_limit.middleware")

    assert client.get("/api/v1/items").status_code == 200
    response = client.get("/api/v1/items")

    assert response.status_code == 200
    observations = [
        record
        for record in caplog.records
        if getattr(record, "event", None) == "rate_limit_shadow"
    ]
    assert [record.decision for record in observations] == ["allowed", "shadow_denied"]
    assert all(record.group == "read_light" for record in observations)
    assert all(record.method == "GET" for record in observations)
    assert all(record.path == "/api/v1/items" for record in observations)
    assert all(record.key != "testclient" for record in observations)
    assert "raw-secret-token" not in caplog.text


def test_enforced_group_overrides_global_shadow_mode() -> None:
    settings = make_settings(
        rate_limit_shadow_mode=True,
        rate_limit_login=1,
        rate_limit_enforced_groups="login",
    )
    client = TestClient(build_app(settings, InMemoryRateLimiter()))

    assert client.post("/api/v1/auth/login").status_code == 200
    response = client.post("/api/v1/auth/login")

    assert response.status_code == 429
    assert response.headers["Retry-After"]
    assert response.headers["X-RateLimit-Limit"] == "1"


def test_group_not_in_enforced_rollout_remains_shadow() -> None:
    settings = make_settings(
        rate_limit_shadow_mode=True,
        rate_limit_default=1,
        rate_limit_enforced_groups="login",
    )
    client = TestClient(build_app(settings, InMemoryRateLimiter()))

    assert client.get("/api/v1/items").status_code == 200
    response = client.get("/api/v1/items")

    assert response.status_code == 200
    assert response.headers["X-RateLimit-Shadow"] == "true"


def test_enforcement_warning_is_emitted_once_per_group_and_key(caplog) -> None:
    settings = make_settings(
        rate_limit_shadow_mode=True,
        rate_limit_login=1,
        rate_limit_enforced_groups="login",
    )
    rate_limit_middleware._last_enforcement_logs.clear()
    client = TestClient(build_app(settings, InMemoryRateLimiter()))
    caplog.set_level(logging.WARNING, logger="app.infrastructure.rate_limit.middleware")

    assert client.post("/api/v1/auth/login").status_code == 200
    assert client.post("/api/v1/auth/login").status_code == 429
    assert client.post("/api/v1/auth/login").status_code == 429

    records = [
        record
        for record in caplog.records
        if record.name == "app.infrastructure.rate_limit.middleware"
        and getattr(record, "event", None) == "rate_limit_enforced"
    ]
    assert len(records) == 1
    assert records[0].group == "login"
    assert records[0].decision == "enforced_denied"
    assert len(records[0].key) == 16


def test_enforced_ai_chat_rejects_before_sse_handler_starts() -> None:
    settings = make_settings(
        rate_limit_shadow_mode=True,
        rate_limit_ai_chat=1,
        rate_limit_enforced_groups="ai_chat",
    )
    app = FastAPI()
    app.state.settings = settings
    app.state.rate_limiter = InMemoryRateLimiter()
    app.state.rate_limit_policy = RateLimitPolicy(settings)
    app.state.rate_limit_key_builder = RateLimitKeyBuilder(settings)
    calls = {"count": 0}

    @app.post("/api/v1/ai/chat/stream", dependencies=[Depends(rate_limit_group("ai_chat"))])
    async def stream() -> Response:
        calls["count"] += 1
        return Response(content="data: ok\\n\\n", media_type="text/event-stream")

    client = TestClient(app)
    assert client.post("/api/v1/ai/chat/stream").status_code == 200
    response = client.post("/api/v1/ai/chat/stream")

    assert response.status_code == 429
    assert calls["count"] == 1


def test_mutation_rollout_blocks_request_31_and_partitions_users() -> None:
    settings = make_settings(
        rate_limit_shadow_mode=True,
        rate_limit_mutation=30,
        rate_limit_enforced_groups="mutation",
    )
    client = TestClient(build_app(settings, InMemoryRateLimiter()))
    user_one = create_access_token("mutation-user-1", settings, role="manager")
    user_two = create_access_token("mutation-user-2", settings, role="manager")

    for _ in range(30):
        assert client.post(
            "/api/v1/mutations", headers={"Authorization": f"Bearer {user_one}"}
        ).status_code == 200
    assert (
        client.post(
            "/api/v1/mutations", headers={"Authorization": f"Bearer {user_one}"}
        ).status_code
        == 429
    )
    assert (
        client.post(
            "/api/v1/mutations", headers={"Authorization": f"Bearer {user_two}"}
        ).status_code
        == 200
    )


def test_operational_lists_have_one_shared_operational_quota() -> None:
    settings = make_settings(
        rate_limit_default=4,
        rate_limit_operational=4,
        rate_limit_shadow_mode=False,
        rate_limit_enforced_groups="read_operational",
    )
    client = TestClient(build_app(settings, InMemoryRateLimiter()))

    assert client.get("/api/v1/operational-alerts").status_code == 200
    assert client.get("/api/v1/operational-tasks").status_code == 200
    assert client.get("/api/v1/operational-alerts").status_code == 200
    assert client.get("/api/v1/operational-tasks").status_code == 200
    assert client.get("/api/v1/operational-alerts").status_code == 429


def test_heavy_read_can_be_enforced_independently() -> None:
    settings = make_settings(
        rate_limit_default=120,
        rate_limit_heavy_read=30,
        rate_limit_shadow_mode=True,
        rate_limit_enforced_groups="read_operational,read_heavy",
    )
    client = TestClient(build_app(settings, InMemoryRateLimiter()))

    for _ in range(30):
        assert client.get("/api/v1/heavy-items").status_code == 200

    assert client.get("/api/v1/heavy-items").status_code == 429


def test_sensitive_backend_failure_fails_closed() -> None:
    settings = make_settings(rate_limit_fail_mode="open")
    client = TestClient(build_app(settings, UnavailableRateLimiter()))

    response = client.post("/api/v1/auth/login")

    assert response.status_code == 503
    assert response.json()["code"] == "rate_limit_unavailable"


def test_non_sensitive_backend_failure_follows_open_mode() -> None:
    settings = make_settings(rate_limit_fail_mode="open")
    client = TestClient(build_app(settings, UnavailableRateLimiter()))

    response = client.get("/api/v1/items")

    assert response.status_code == 200


def test_policy_and_key_builder_do_not_expose_raw_access_token() -> None:
    settings = make_settings()
    policy = RateLimitPolicy(settings)
    key_builder = RateLimitKeyBuilder(settings)
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/v1/items",
            "raw_path": b"/api/v1/items",
            "query_string": b"",
            "headers": [(b"authorization", b"Bearer raw-secret-token")],
            "scheme": "http",
            "server": ("testserver", 80),
            "client": ("testclient", 50000),
        }
    )
    rule = policy.rule_for_group("read_light")

    key = key_builder.build(request, rule)

    assert isinstance(rule, RateLimitRule)
    assert "raw-secret-token" not in key
    assert key == "rl:ip:testclient:anonymous:read_light"


def test_authenticated_key_is_partitioned_by_role_without_exposing_token() -> None:
    settings = make_settings()
    policy = RateLimitPolicy(settings)
    key_builder = RateLimitKeyBuilder(settings)
    token = create_access_token("leadership-1", settings, role="leadership")
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/v1/items",
            "raw_path": b"/api/v1/items",
            "query_string": b"",
            "headers": [(b"authorization", f"Bearer {token}".encode())],
            "scheme": "http",
            "server": ("testserver", 80),
            "client": ("testclient", 50000),
        }
    )

    key = key_builder.build(request, policy.rule_for_group("read_light"))

    assert key == "rl:user:leadership-1:read_light"


def test_authenticated_key_is_stable_across_token_refresh_for_same_user() -> None:
    settings = make_settings()
    policy = RateLimitPolicy(settings)
    key_builder = RateLimitKeyBuilder(settings)
    first_token = create_access_token(
        "manager-1", settings, role="manager", username="manager-old"
    )
    refreshed_token = create_access_token(
        "manager-1", settings, role="manager", username="manager-new"
    )

    def request_for(token: str) -> Request:
        return Request(
            {
                "type": "http",
                "method": "GET",
                "path": "/api/v1/items",
                "raw_path": b"/api/v1/items",
                "query_string": b"",
                "headers": [(b"authorization", f"Bearer {token}".encode())],
                "scheme": "http",
                "server": ("testserver", 80),
                "client": ("testclient", 50000),
            }
        )

    rule = policy.rule_for_group("read_light")
    assert key_builder.build(request_for(first_token), rule) == key_builder.build(
        request_for(refreshed_token), rule
    )


def test_canonical_scan_route_uses_sensitive_scan_bucket() -> None:
    settings = make_settings()
    policy = RateLimitPolicy(settings)
    rule = policy.rule_for_group("scan")

    assert rule.group == "scan"
    assert rule.sensitive is True


def test_idempotency_replays_success_and_rejects_payload_reuse() -> None:
    settings = make_settings(idempotency_enabled=True)
    app = FastAPI()
    app.add_middleware(
        IdempotencyMiddleware,
        store=InMemoryIdempotencyStore(),
        settings=settings,
    )
    calls = {"count": 0}

    @app.post("/api/v1/items")
    async def create_item(payload: dict[str, str]) -> dict[str, object]:
        calls["count"] += 1
        return {"value": payload["value"], "call": calls["count"]}

    client = TestClient(app)
    headers = {"Idempotency-Key": "item-1"}
    first = client.post(
        "/api/v1/items",
        json={"value": "a"},
        headers={**headers, "X-Request-ID": "first-request"},
    )
    replay = client.post(
        "/api/v1/items",
        json={"value": "a"},
        headers={**headers, "X-Request-ID": "replay-request"},
    )
    conflict = client.post("/api/v1/items", json={"value": "b"}, headers=headers)

    assert first.status_code == replay.status_code == 200
    assert first.json() == replay.json() == {"value": "a", "call": 1}
    assert replay.headers["Idempotency-Replayed"] == "true"
    assert replay.headers["X-Request-ID"] == "replay-request"
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "idempotency_key_conflict"
    assert calls["count"] == 1


def test_scoped_idempotency_dependency_optionally_replays_and_caches_location() -> None:
    settings = make_settings(idempotency_enabled=True)
    store = InMemoryIdempotencyStore()
    app = FastAPI()
    app.state.settings = settings
    app.state.idempotency_store = store
    app.add_exception_handler(IdempotencyReplay, handle_idempotency_replay)
    calls = {"count": 0}

    @app.post("/api/v1/items", status_code=201)
    async def create_item(
        payload: dict[str, str],
        request: Request,
        response: Response,
        idempotency: IdempotencyContext = TEST_ITEM_IDEMPOTENCY,
    ) -> dict[str, object]:
        calls["count"] += 1
        result = {"value": payload["value"], "call": calls["count"]}
        response.headers["Location"] = "/api/v1/items/1"
        await complete_idempotency(idempotency, result, response, status_code=201)
        return result

    client = TestClient(app)
    missing = client.post("/api/v1/items", json={"value": "a"})
    first = client.post(
        "/api/v1/items", json={"value": "a"}, headers={"Idempotency-Key": "item-1"}
    )
    replay = client.post(
        "/api/v1/items", json={"value": "a"}, headers={"Idempotency-Key": "item-1"}
    )
    conflict = client.post(
        "/api/v1/items", json={"value": "b"}, headers={"Idempotency-Key": "item-1"}
    )

    assert missing.status_code == 201
    assert first.status_code == replay.status_code == 201
    assert first.json() == replay.json() == {"value": "a", "call": 2}
    assert replay.headers["Idempotency-Replayed"] == "true"
    assert replay.headers["Location"] == "/api/v1/items/1"
    assert conflict.status_code == 409
    assert calls["count"] == 2
    assert app.state.idempotency_counters["test_item"]["POST /api/v1/items"] == {
        "with_key": 3,
        "without_key": 1,
    }


def test_idempotency_disabled_is_a_true_killswitch_without_redis_or_header() -> None:
    settings = make_settings(idempotency_enabled=False)
    app = FastAPI()
    app.state.settings = settings
    calls = {"count": 0}

    @app.post("/api/v1/items", status_code=201)
    async def create_item(
        idempotency: IdempotencyContext | None = TEST_ITEM_IDEMPOTENCY,
    ) -> dict[str, bool]:
        assert idempotency is None
        calls["count"] += 1
        return {"ok": True}

    response = TestClient(app).post("/api/v1/items", json={"value": "a"})

    assert response.status_code == 201
    assert response.json() == {"ok": True}
    assert calls["count"] == 1


def test_scoped_idempotency_dependency_releases_claim_after_route_error() -> None:
    settings = make_settings(idempotency_enabled=True)
    store = InMemoryIdempotencyStore()
    app = FastAPI()
    app.state.settings = settings
    app.state.idempotency_store = store
    app.add_exception_handler(IdempotencyReplay, handle_idempotency_replay)
    calls = {"count": 0}

    @app.post("/api/v1/items", status_code=201)
    async def create_item(
        request: Request,
        idempotency: IdempotencyContext = FAILING_ITEM_IDEMPOTENCY,
    ) -> Response:
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("expected test failure")
        result = {"ok": True}
        await complete_idempotency(idempotency, result, status_code=201)
        return Response(status_code=201, content=b'{"ok":true}', media_type="application/json")

    client = TestClient(app, raise_server_exceptions=False)
    headers = {"Idempotency-Key": "retryable-item"}
    first = client.post("/api/v1/items", headers=headers)
    second = client.post("/api/v1/items", headers=headers)

    assert first.status_code == 500
    assert second.status_code == 201
    assert calls["count"] == 2


def test_idempotency_identity_is_stable_across_token_refresh() -> None:
    settings = make_settings()
    first_token = create_access_token(
        "manager-1", settings, role="manager", username="manager-old"
    )
    refreshed_token = create_access_token(
        "manager-1", settings, role="manager", username="manager-new"
    )

    def request_for(token: str) -> Request:
        return Request(
            {
                "type": "http",
                "method": "POST",
                "path": "/api/v1/items",
                "raw_path": b"/api/v1/items",
                "query_string": b"",
                "headers": [(b"authorization", f"Bearer {token}".encode())],
                "scheme": "http",
                "server": ("testserver", 80),
                "client": ("testclient", 50000),
            }
        )

    first_key = _idempotency_key(request_for(first_token), "same-key", b"{}", settings)
    refreshed_key = _idempotency_key(
        request_for(refreshed_token), "same-key", b"{}", settings
    )

    assert first_key == refreshed_key


def test_anonymous_idempotency_identity_is_partitioned_by_ip() -> None:
    settings = make_settings(rate_limit_trusted_proxy_ips="testclient")

    def request_for(ip: str) -> Request:
        return Request(
            {
                "type": "http",
                "method": "POST",
                "path": "/api/v1/items",
                "raw_path": b"/api/v1/items",
                "query_string": b"",
                "headers": [(b"x-forwarded-for", ip.encode())],
                "scheme": "http",
                "server": ("testserver", 80),
                "client": ("testclient", 50000),
            }
        )

    first_key = _idempotency_key(request_for("10.0.0.1"), "same-key", b"{}", settings)
    second_key = _idempotency_key(request_for("10.0.0.2"), "same-key", b"{}", settings)

    assert first_key != second_key


def test_idempotency_scope_includes_query_string() -> None:
    settings = make_settings()

    def request_for(query: str) -> Request:
        return Request(
            {
                "type": "http",
                "method": "POST",
                "path": "/api/v1/items",
                "raw_path": b"/api/v1/items",
                "query_string": query.encode(),
                "headers": [],
                "scheme": "http",
                "server": ("testserver", 80),
                "client": ("testclient", 50000),
            }
        )

    first_key = _idempotency_key(request_for("mode=a"), "same-key", b"{}", settings)
    second_key = _idempotency_key(request_for("mode=b"), "same-key", b"{}", settings)

    assert first_key != second_key


def test_idempotency_releases_claim_after_server_error() -> None:
    settings = make_settings(idempotency_enabled=True)
    app = FastAPI()
    app.add_middleware(
        IdempotencyMiddleware,
        store=InMemoryIdempotencyStore(),
        settings=settings,
    )
    calls = {"count": 0}

    @app.post("/api/v1/items")
    async def create_item() -> Response:
        calls["count"] += 1
        if calls["count"] == 1:
            return Response(status_code=500)
        return Response(status_code=201, content=b"created")

    client = TestClient(app)
    headers = {"Idempotency-Key": "retry-after-error"}

    first = client.post("/api/v1/items", headers=headers)
    second = client.post("/api/v1/items", headers=headers)

    assert first.status_code == 500
    assert second.status_code == 201
    assert calls["count"] == 2


def test_two_middleware_instances_share_rate_limit_state() -> None:
    settings = make_settings(rate_limit_default=1)
    limiter = InMemoryRateLimiter()
    first_client = TestClient(build_app(settings, limiter))
    second_client = TestClient(build_app(settings, limiter))

    assert first_client.get("/api/v1/items").status_code == 200
    response = second_client.get("/api/v1/items")

    assert response.status_code == 429
    assert response.json()["code"] == "rate_limit_exceeded"


def test_two_middleware_instances_share_idempotency_state() -> None:
    settings = make_settings(idempotency_enabled=True)
    store = InMemoryIdempotencyStore()
    calls = {"count": 0}

    def build_idempotent_app() -> FastAPI:
        app = FastAPI()
        app.add_middleware(IdempotencyMiddleware, store=store, settings=settings)

        @app.post("/api/v1/items")
        async def create_item(payload: dict[str, str]) -> dict[str, object]:
            calls["count"] += 1
            return {"value": payload["value"], "call": calls["count"]}

        return app

    first_client = TestClient(build_idempotent_app())
    second_client = TestClient(build_idempotent_app())
    headers = {"Idempotency-Key": "shared-item-1"}

    first = first_client.post("/api/v1/items", json={"value": "a"}, headers=headers)
    replay = second_client.post("/api/v1/items", json={"value": "a"}, headers=headers)

    assert first.status_code == replay.status_code == 200
    assert replay.headers["Idempotency-Replayed"] == "true"
    assert replay.json() == {"value": "a", "call": 1}
    assert calls["count"] == 1


def test_redis_rate_limiter_adapter_uses_atomic_eval_script() -> None:
    calls: list[tuple] = []

    class FakeRedis:
        async def eval(self, script, *args):
            calls.append((script, *args))
            return [1, 9, args[2] + args[3], 0]

    limiter = RedisRateLimiter.__new__(RedisRateLimiter)
    limiter.client = FakeRedis()

    import asyncio

    decision = asyncio.run(limiter.check("rl:read:manager:fp", 10, 60))

    assert decision.allowed is True
    assert decision.remaining == 9
    assert calls and "HGET" in calls[0][0]
    assert decision.reset_at.tzinfo is not None


def test_contract_policy_uses_explicit_groups_and_health_bypass() -> None:
    settings = make_settings(
        rate_limit_default=120,
        rate_limit_read_heavy=None,
        rate_limit_heavy_read=None,
        rate_limit_directive=None,
        rate_limit_upload_session=None,
        rate_limit_upload_completion=None,
        rate_limit_ai_chat=None,
        rate_limit_ws_handshake=None,
    )
    policy = RateLimitPolicy(settings)

    assert policy.rule_for_group("read_light").limit == 120
    assert policy.rule_for_group("read_operational").limit == 120
    # A group without an explicit quota falls back to the shared default.
    assert policy.rule_for_group("read_heavy").limit == settings.rate_limit_default
    assert policy.rule_for_group("directive_action").limit == 120
    assert policy.is_bypassed("health") is True
    assert policy.rule_for_group("health").limit == 0


def test_operational_policy_uses_its_explicit_quota_before_default() -> None:
    settings = make_settings(rate_limit_default=120, rate_limit_operational=90)
    policy = RateLimitPolicy(settings)

    assert policy.rule_for_group("read_operational").limit == 90


def test_contract_key_builder_uses_three_canonical_key_shapes() -> None:
    settings = make_settings(trusted_proxy_ips="testclient")
    builder = RateLimitKeyBuilder(settings)
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/v1/items",
            "raw_path": b"/api/v1/items",
            "query_string": b"",
            "headers": [(b"x-forwarded-for", b"10.0.0.7, 10.0.0.8")],
            "scheme": "http",
            "server": ("testserver", 80),
            "client": ("testclient", 50000),
        }
    )

    assert builder.build_user_key("user-1", "mutation") == "rl:user:user-1:mutation"
    assert builder.build_anonymous_key("10.0.0.7", "read_light") == (
        "rl:ip:10.0.0.7:anonymous:read_light"
    )
    assert builder.build_login_keys("10.0.0.7", "demo.manager") == (
        "rl:ip:10.0.0.7:login:demo.manager",
        "rl:ip:10.0.0.7:login",
    )
    assert builder.build_for_group(request, "read_light") == (
        "rl:ip:10.0.0.7:anonymous:read_light"
    )


def test_explicit_rate_limit_dependency_enforces_declared_group() -> None:
    settings = make_settings(rate_limit_default=1)
    app = FastAPI()
    app.state.settings = settings
    app.state.rate_limiter = InMemoryRateLimiter()
    app.state.rate_limit_policy = RateLimitPolicy(settings)
    app.state.rate_limit_key_builder = RateLimitKeyBuilder(settings)

    @app.get("/items", dependencies=[Depends(rate_limit_group("read_light"))])
    async def items() -> dict[str, bool]:
        return {"ok": True}

    client = TestClient(app)
    assert client.get("/items").status_code == 200
    assert client.get("/items").status_code == 429


def test_websocket_handshake_closes_eleven_attempt_with_1013() -> None:
    settings = make_settings(rate_limit_enabled=True, rate_limit_ws_handshake=10)
    app = FastAPI()
    app.state.settings = settings
    app.state.rate_limiter = InMemoryRateLimiter()
    app.state.rate_limit_policy = RateLimitPolicy(settings)
    app.state.rate_limit_key_builder = RateLimitKeyBuilder(settings)

    class FakeWebSocket:
        def __init__(self) -> None:
            self.app = app
            self.client = SimpleNamespace(host="198.51.100.10")
            self.headers = {}
            self.cookies = {}
            self.query_params = {}
            self.closed: list[tuple[int, str]] = []

        async def close(self, code: int, reason: str) -> None:
            self.closed.append((code, reason))

    async def exercise() -> list[tuple[int, str]]:
        closed: list[tuple[int, str]] = []
        for _ in range(11):
            websocket = FakeWebSocket()
            await realtime_websocket(websocket, object())  # type: ignore[arg-type]
            closed.extend(websocket.closed)
        return closed

    closed = asyncio.run(exercise())
    assert [code for code, _ in closed[:10]] == [1008] * 10
    assert closed[10][0] == 1013


def test_redis_idempotency_adapter_uses_atomic_claim_complete_release_scripts() -> None:
    calls: list[tuple] = []

    class FakeRedis:
        async def eval(self, script, *args):
            calls.append((script, *args))
            if "local current" in script:
                return [1, args[2]]
            return 1

    store = RedisIdempotencyStore.__new__(RedisIdempotencyStore)
    store.client = FakeRedis()

    import asyncio

    claim = asyncio.run(store.claim("idempotency:test", "hash", 60))
    assert claim.state == "claimed"
    assert claim.owner is not None
    response = StoredResponse(201, {"content-type": "application/json"}, b"{}")
    asyncio.run(store.complete("idempotency:test", claim.owner, "hash", response, 60))
    asyncio.run(store.release("idempotency:test", claim.owner, "hash"))

    assert any("local current" in call[0] for call in calls)
    assert any("redis.call('SET'" in call[0] for call in calls)
    assert any("redis.call('DEL'" in call[0] for call in calls)
