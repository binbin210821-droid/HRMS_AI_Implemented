from collections.abc import Callable
from typing import cast

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import get_settings
from app.core.database import get_mongo_database
from app.core.security import decode_access_token
from app.models.user import CurrentUser, UserRole
from app.repositories.user_repository import UserRepository

bearer_scheme = HTTPBearer(auto_error=False)
oauth2_scheme = bearer_scheme


def get_user_repository() -> UserRepository:
    return UserRepository(get_mongo_database().get_database())


def extract_request_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None,
) -> str:
    settings = get_settings()
    cookie_token = request.cookies.get(settings.auth_access_cookie_name)
    bearer_token = credentials.credentials if credentials else None
    authorization = request.headers.get("authorization")

    if authorization and not credentials and authorization.lower().startswith("bearer"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer token không hợp lệ",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if cookie_token and bearer_token and cookie_token != bearer_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Các thông tin xác thực không khớp",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if bearer_token and not settings.legacy_bearer_enabled:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer token tương thích đã được tắt",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = cookie_token or bearer_token
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bạn cần đăng nhập để tiếp tục",
            headers={"WWW-Authenticate": "Bearer"},
        )
    request.state.auth_source = "cookie" if cookie_token else "bearer"
    return token


async def get_auth_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> str:
    return extract_request_token(request, credentials)


async def get_current_user(
    token: str = Depends(get_auth_token),
    repository: UserRepository = Depends(get_user_repository),
    request: Request = cast(Request, None),
) -> CurrentUser:
    current_user = await resolve_current_user(token, repository)
    if request is not None:
        request.state.authenticated_user_id = current_user.user_id
    return current_user


async def resolve_current_user(token: str, repository: UserRepository) -> CurrentUser:
    payload = decode_access_token(token, get_settings())
    user = await repository.find_by_id(str(payload["sub"]))
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tài khoản không tồn tại hoặc đã bị khóa",
            headers={"WWW-Authenticate": "Bearer"},
        )

    expected_department_id = str(user.department_id) if user.department_id else None
    if (
        payload.get("role") != user.role.value
        or payload.get("department_id") != expected_department_id
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token không còn phù hợp với tài khoản",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return CurrentUser(
        user_id=str(user.id),
        username=user.username,
        full_name=user.full_name,
        role=user.role,
        department_id=str(user.department_id) if user.department_id else None,
    )


def require_role(*allowed_roles: UserRole | str) -> Callable:
    roles = {UserRole(role) for role in allowed_roles}

    async def role_dependency(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bạn không có quyền thực hiện chức năng này",
            )
        return current_user

    return role_dependency


async def get_department_scope(
    current_user: CurrentUser = Depends(get_current_user),
) -> ObjectId | None:
    """ObjectId phòng ban cho Manager; None nghĩa là Leadership xem toàn công ty."""
    if current_user.role == UserRole.LEADERSHIP:
        return None
    if current_user.department_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tài khoản quản lý chưa được gán phòng ban",
        )
    try:
        return ObjectId(current_user.department_id)
    except (InvalidId, TypeError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tài khoản quản lý có mã phòng ban không hợp lệ",
        ) from None
