from collections.abc import Callable

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.core.config import get_settings
from app.core.database import get_mongo_database
from app.core.security import decode_access_token
from app.models.user import CurrentUser, UserRole
from app.repositories.user_repository import UserRepository

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def get_user_repository() -> UserRepository:
    return UserRepository(get_mongo_database().get_database())


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    repository: UserRepository = Depends(get_user_repository),
) -> CurrentUser:
    return await resolve_current_user(token, repository)


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
