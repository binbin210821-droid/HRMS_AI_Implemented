from datetime import datetime, timezone

import pytest
from bson import ObjectId
from fastapi import HTTPException, Response
from fastapi.security import HTTPAuthorizationCredentials
from httpx import ASGITransport, AsyncClient
from starlette.requests import Request
from starlette.responses import PlainTextResponse

from app.api.dependencies import (
    extract_request_token,
    get_current_user,
    get_department_scope,
    require_role,
)
from app.core.config import Settings
from app.core.csrf import CSRFMiddleware
from app.core.security import (
    create_access_token,
    decode_access_token,
    ensure_csrf_cookie,
    hash_password,
    set_auth_cookies,
)
from app.models.user import CurrentUser, LoginRequest, UserDocument, UserRole
from app.services.auth_service import AuthenticationService


def make_user(
    *,
    role: UserRole = UserRole.MANAGER,
    department_id: ObjectId | None = None,
    is_active: bool = True,
) -> UserDocument:
    return UserDocument(
        _id=ObjectId(),
        username="demo.user",
        password_hash=hash_password("mat-khau-dung"),
        full_name="Người dùng thử nghiệm",
        role=role,
        department_id=department_id,
        is_active=is_active,
        created_at=datetime.now(timezone.utc),
    )


class FakeUserRepository:
    def __init__(self, user: UserDocument | None) -> None:
        self.user = user

    async def find_by_username(self, _: str) -> UserDocument | None:
        return self.user

    async def find_by_id(self, _: str) -> UserDocument | None:
        return self.user


def make_request(*, cookie: str | None = None, authorization: str | None = None) -> Request:
    headers = []
    if cookie:
        headers.append((b"cookie", cookie.encode()))
    if authorization:
        headers.append((b"authorization", authorization.encode()))
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/auth/me",
            "raw_path": b"/api/auth/me",
            "query_string": b"",
            "headers": headers,
            "scheme": "http",
            "server": ("testserver", 80),
            "client": ("testclient", 50000),
        }
    )


@pytest.mark.asyncio
async def test_login_token_contains_role_and_department_scope() -> None:
    department_id = ObjectId()
    user = make_user(department_id=department_id)
    settings = Settings(jwt_secret="test-secret")

    response = await AuthenticationService(FakeUserRepository(user), settings).login(
        LoginRequest(username=" demo.user ", password="mat-khau-dung")
    )

    claims = decode_access_token(response.access_token, settings)
    assert claims["sub"] == str(user.id)
    assert claims["role"] == "manager"
    assert claims["department_id"] == str(department_id)


@pytest.mark.asyncio
async def test_invalid_credentials_and_inactive_user_return_401() -> None:
    settings = Settings(jwt_secret="test-secret")
    service = AuthenticationService(FakeUserRepository(make_user()), settings)

    with pytest.raises(HTTPException) as invalid_password:
        await service.login(LoginRequest(username="demo.user", password="sai"))
    assert invalid_password.value.status_code == 401

    inactive_service = AuthenticationService(
        FakeUserRepository(make_user(is_active=False)), settings
    )
    with pytest.raises(HTTPException) as inactive:
        await inactive_service.login(LoginRequest(username="demo.user", password="mat-khau-dung"))
    assert inactive.value.status_code == 401


@pytest.mark.asyncio
async def test_current_user_rejects_expired_wrong_signature_and_mismatched_claims() -> None:
    user = make_user(department_id=ObjectId())
    settings = Settings(jwt_secret="test-secret")
    repository = FakeUserRepository(user)

    expired = create_access_token(
        str(user.id),
        settings,
        expires_minutes=-1,
        role=user.role.value,
        department_id=str(user.department_id),
    )
    with pytest.raises(HTTPException) as expired_error:
        await get_current_user(expired, repository)
    assert expired_error.value.status_code == 401

    wrong_signature = create_access_token(
        str(user.id),
        Settings(jwt_secret="other-secret"),
        role=user.role.value,
        department_id=str(user.department_id),
    )
    with pytest.raises(HTTPException) as signature_error:
        await get_current_user(wrong_signature, repository)
    assert signature_error.value.status_code == 401

    mismatched_claims = create_access_token(
        str(user.id), settings, role=UserRole.LEADERSHIP.value, department_id=None
    )
    with pytest.raises(HTTPException) as claim_error:
        await get_current_user(mismatched_claims, repository)
    assert claim_error.value.status_code == 401


@pytest.mark.asyncio
async def test_role_guard_and_department_scope() -> None:
    department_id = ObjectId()
    manager = CurrentUser(
        user_id=str(ObjectId()),
        username="manager",
        full_name="Quản lý",
        role=UserRole.MANAGER,
        department_id=str(department_id),
    )
    leadership = manager.model_copy(update={"role": UserRole.LEADERSHIP, "department_id": None})

    assert await get_department_scope(manager) == department_id
    assert await get_department_scope(leadership) is None

    leadership_guard = require_role(UserRole.LEADERSHIP)
    with pytest.raises(HTTPException) as forbidden:
        await leadership_guard(manager)
    assert forbidden.value.status_code == 403


def test_cookie_is_the_primary_auth_source_and_bearer_remains_compatible() -> None:
    settings = Settings(jwt_secret="test-secret")
    request = make_request(
        cookie=f"{settings.auth_access_cookie_name}=cookie-token",
        authorization="Bearer cookie-token",
    )
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="cookie-token")

    assert extract_request_token(request, credentials) == "cookie-token"
    assert request.state.auth_source == "cookie"

    bearer_request = make_request(authorization="Bearer legacy-token")
    bearer_credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="legacy-token")
    assert extract_request_token(bearer_request, bearer_credentials) == "legacy-token"
    assert bearer_request.state.auth_source == "bearer"


def test_mismatched_cookie_and_bearer_are_rejected() -> None:
    settings = Settings(jwt_secret="test-secret")
    request = make_request(
        cookie=f"{settings.auth_access_cookie_name}=cookie-token",
        authorization="Bearer other-token",
    )
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="other-token")

    with pytest.raises(HTTPException) as error:
        extract_request_token(request, credentials)
    assert error.value.status_code == 401


def test_auth_cookies_include_httponly_access_and_readable_csrf_cookie() -> None:
    settings = Settings(jwt_secret="test-secret")
    response = Response()

    set_auth_cookies(response, "signed-token", settings, csrf_token="csrf-token")
    cookies = response.headers.getlist("set-cookie")

    access_cookie = next(cookie for cookie in cookies if settings.auth_access_cookie_name in cookie)
    csrf_cookie = next(cookie for cookie in cookies if settings.auth_csrf_cookie_name in cookie)
    assert "HttpOnly" in access_cookie
    assert "HttpOnly" not in csrf_cookie
    assert "signed-token" in access_cookie
    assert "csrf-token" in csrf_cookie


def test_ensure_csrf_cookie_does_not_replace_access_cookie() -> None:
    settings = Settings(jwt_secret="test-secret")
    response = Response()

    ensure_csrf_cookie(response, settings, None)
    cookies = response.headers.getlist("set-cookie")

    assert len(cookies) == 1
    assert settings.auth_csrf_cookie_name in cookies[0]


@pytest.mark.asyncio
async def test_csrf_middleware_requires_matching_token_for_cookie_mutations() -> None:
    async def app(scope, receive, send):
        await PlainTextResponse("ok")(scope, receive, send)

    protected_app = CSRFMiddleware(app)
    transport = ASGITransport(app=protected_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        missing = await client.post(
            "/api/tasks",
            headers={"Cookie": "hrms_access_token=access; hrms_csrf_token=csrf"},
        )
        valid = await client.post(
            "/api/tasks",
            headers={
                "Cookie": "hrms_access_token=access; hrms_csrf_token=csrf",
                "X-CSRF-Token": "csrf",
            },
        )
        safe = await client.get(
            "/api/tasks",
            headers={"Cookie": "hrms_access_token=access; hrms_csrf_token=csrf"},
        )

    assert missing.status_code == 403
    assert valid.status_code == 200
    assert safe.status_code == 200
