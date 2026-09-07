from datetime import datetime, timezone

import pytest
from bson import ObjectId
from fastapi import HTTPException

from app.api.dependencies import get_current_user, get_department_scope, require_role
from app.core.config import Settings
from app.core.security import create_access_token, decode_access_token, hash_password
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
