from fastapi import APIRouter, Depends

from app.api.dependencies import get_current_user
from app.core.config import get_settings
from app.core.database import get_mongo_database
from app.models.user import CurrentUser, LoginRequest, TokenResponse
from app.repositories.user_repository import UserRepository
from app.services.auth_service import AuthenticationService

router = APIRouter(prefix="/api/auth", tags=["Auth"])


def get_auth_service() -> AuthenticationService:
    return AuthenticationService(
        repository=UserRepository(get_mongo_database().get_database()),
        settings=get_settings(),
    )


@router.post("/login", response_model=TokenResponse, summary="Đăng nhập")
async def login(
    request: LoginRequest,
    service: AuthenticationService = Depends(get_auth_service),
) -> TokenResponse:
    return await service.login(request)


@router.get("/me", response_model=CurrentUser, summary="Lấy tài khoản hiện tại")
async def get_me(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    return current_user
