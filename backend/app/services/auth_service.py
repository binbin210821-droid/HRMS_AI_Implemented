from fastapi import HTTPException, status

from app.core.config import Settings
from app.core.security import create_access_token, verify_password
from app.models.user import LoginRequest, TokenResponse
from app.repositories.user_repository import UserRepository


class AuthenticationService:
    def __init__(self, repository: UserRepository, settings: Settings) -> None:
        self.repository = repository
        self.settings = settings

    async def login(self, request: LoginRequest) -> TokenResponse:
        user = await self.repository.find_by_username(request.username.strip())
        if (
            user is None
            or not user.is_active
            or not verify_password(request.password, user.password_hash)
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Tên đăng nhập hoặc mật khẩu không đúng",
                headers={"WWW-Authenticate": "Bearer"},
            )

        token = create_access_token(
            subject=str(user.id),
            settings=self.settings,
            role=user.role.value,
            department_id=str(user.department_id) if user.department_id else None,
            username=user.username,
            full_name=user.full_name,
            expires_minutes=self.settings.jwt_expire_minutes,
        )
        return TokenResponse(access_token=token)
