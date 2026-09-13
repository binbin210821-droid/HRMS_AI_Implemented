from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer
from fastapi.testclient import TestClient

from app.core.api_deprecation import LegacyApiDeprecationMiddleware, LegacyApiUsageMiddleware
from app.core.config import Settings
from app.core.http_contract import RequestIdMiddleware, install_http_contract
from app.infrastructure.idempotency import idempotent


def build_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(RequestIdMiddleware)
    install_http_contract(app)

    @app.get("/items")
    @app.get("/api/v1/items")
    async def list_items(limit: Annotated[int, Query(ge=1)]) -> dict:
        return {"limit": limit}

    @app.get("/forbidden")
    async def forbidden() -> None:
        raise HTTPException(status_code=403, detail="Không có quyền")

    @app.get("/api/legacy-forbidden")
    async def legacy_forbidden() -> None:
        raise HTTPException(status_code=403, detail="Không có quyền cũ")

    @app.get("/api/v1/forbidden")
    async def v1_forbidden() -> None:
        raise HTTPException(status_code=403, detail="Không có quyền mới")

    @app.post("/items", dependencies=[Depends(HTTPBearer(auto_error=False))])
    async def create_item() -> dict[str, bool]:
        return {"ok": True}

    @app.post("/api/v1/idempotent-items", dependencies=[Depends(idempotent("test"))])
    async def create_idempotent_item() -> dict[str, bool]:
        return {"ok": True}

    @app.get("/api/legacy-items")
    async def legacy_items() -> dict[str, bool]:
        return {"ok": True}

    return app


def test_error_contract_preserves_valid_request_id() -> None:
    client = TestClient(build_app())

    response = client.get("/forbidden", headers={"X-Request-ID": "trace-123"})

    assert response.status_code == 403
    assert response.headers["X-Request-ID"] == "trace-123"
    assert response.json() == {
        "code": "forbidden",
        "message": "Không có quyền",
        "details": None,
        "request_id": "trace-123",
    }


def test_request_id_is_present_on_cors_preflight_response() -> None:
    app = FastAPI()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestIdMiddleware)

    response = TestClient(app).options(
        "/items",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["X-Request-ID"]


def test_validation_and_not_found_use_the_same_error_shape() -> None:
    client = TestClient(build_app())

    invalid = client.get("/items", params={"limit": "bad"})
    missing = client.get("/missing")

    assert invalid.status_code == 422
    assert invalid.json()["code"] == "validation_error"
    assert invalid.json()["request_id"]
    assert missing.status_code == 404
    assert missing.json()["code"] == "not_found"
    assert missing.json()["request_id"]


def test_v1_handler_uses_object_details_and_legacy_handler_is_unchanged() -> None:
    client = TestClient(build_app())

    v1_response = client.get("/api/v1/forbidden", headers={"X-Request-ID": "v1-trace"})
    legacy_response = client.get("/api/legacy-forbidden", headers={"X-Request-ID": "old-trace"})

    assert v1_response.json() == {
        "code": "forbidden",
        "message": "Không có quyền mới",
        "details": None,
        "request_id": "v1-trace",
    }
    assert legacy_response.json() == {
        "code": "forbidden",
        "message": "Không có quyền cũ",
        "details": None,
        "request_id": "old-trace",
    }


def test_v1_validation_details_are_an_object() -> None:
    client = TestClient(build_app())

    response = client.get("/api/v1/items", params={"limit": "bad"})

    assert response.status_code == 422
    assert isinstance(response.json()["details"], dict)
    assert "errors" in response.json()["details"]


def test_openapi_documents_api_error_for_routes() -> None:
    schema = build_app().openapi()

    assert "ApiError" in schema["components"]["schemas"]
    assert "V1ApiError" in schema["components"]["schemas"]
    responses = schema["paths"]["/forbidden"]["get"]["responses"]
    assert responses["401"]["content"]["application/json"]["schema"]["$ref"] == (
        "#/components/schemas/ApiError"
    )
    assert schema["components"]["securitySchemes"]["CookieAuth"]["in"] == "cookie"
    operation = schema["paths"]["/items"]["post"]
    assert operation["security"] == [{"CookieAuth": []}, {"BearerAuth": []}]
    assert any(
        parameter["name"] == "Idempotency-Key"
        for parameter in operation["parameters"]
    )
    required_operation = schema["paths"]["/api/v1/idempotent-items"]["post"]
    idempotency_parameter = next(
        parameter
        for parameter in required_operation["parameters"]
        if parameter["name"] == "Idempotency-Key"
    )
    assert idempotency_parameter["required"] is False
    assert operation["responses"]["429"]["content"]["application/json"]["schema"]["$ref"] == (
        "#/components/schemas/ApiError"
    )
    assert schema["paths"]["/api/legacy-items"]["get"]["deprecated"] is True
    assert (
        schema["paths"]["/api/v1/forbidden"]["get"]["responses"]["403"]["content"][
            "application/json"
        ]["schema"]["$ref"]
        == "#/components/schemas/V1ApiError"
    )
    assert (
        schema["paths"]["/api/legacy-forbidden"]["get"]["responses"]["403"]["content"][
            "application/json"
        ]["schema"]["$ref"]
        == "#/components/schemas/ApiError"
    )


def test_legacy_api_response_points_to_v1_successor() -> None:
    app = FastAPI()
    app.add_middleware(LegacyApiDeprecationMiddleware, settings=Settings())

    @app.get("/api/items")
    async def items() -> dict[str, bool]:
        return {"ok": True}

    response = TestClient(app).get("/api/items?limit=2")

    assert response.status_code == 200
    assert response.headers["Deprecation"] == "true"
    assert response.headers["Sunset"] == "2027-03-01T00:00:00Z"
    assert response.headers["Link"] == '</api/v1/items?limit=2>; rel="successor-version"'


def test_legacy_api_usage_logs_only_observed_legacy_paths(caplog) -> None:
    app = FastAPI()
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(LegacyApiUsageMiddleware)

    @app.get("/api/items")
    async def legacy_items() -> dict[str, bool]:
        return {"ok": True}

    @app.get("/api/v1/items")
    async def v1_items() -> dict[str, bool]:
        return {"ok": True}

    @app.get("/api/auth/me")
    async def auth_me() -> dict[str, bool]:
        return {"ok": True}

    @app.get("/api/health")
    async def health() -> dict[str, bool]:
        return {"ok": True}

    caplog.set_level("INFO", logger="app.core.api_deprecation")
    client = TestClient(app)
    assert client.get("/api/items", headers={"User-Agent": "phase16-test"}).status_code == 200
    assert client.get("/api/v1/items").status_code == 200
    assert client.get("/api/auth/me").status_code == 200
    assert client.get("/api/health").status_code == 200

    events = [record for record in caplog.records if record.event == "legacy_api_call"]
    assert len(events) == 1
    assert events[0].path == "/api/items"
    assert events[0].method == "GET"
    assert events[0].user_agent == "phase16-test"
