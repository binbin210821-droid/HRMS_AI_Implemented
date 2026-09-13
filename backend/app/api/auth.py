from fastapi import APIRouter, Depends, Request, Response, status

from app.api.dependencies import get_current_user
from app.core.config import get_settings
from app.core.database import get_mongo_database
from app.core.security import clear_auth_cookies, ensure_csrf_cookie, set_auth_cookies
from app.infrastructure.rate_limit import rate_limit_group
from app.models.user import CurrentUser, LoginRequest, TokenResponse
from app.repositories.user_repository import UserRepository
from app.services.auth_service import AuthenticationService

router = APIRouter(prefix="/auth", tags=["Auth"])


def get_auth_service() -> AuthenticationService:
    return AuthenticationService(
        repository=UserRepository(get_mongo_database().get_database()),
        settings=get_settings(),
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Đăng nhập",
    dependencies=[Depends(rate_limit_group("login"))],
)
async def login(
    response: Response,
    request: LoginRequest,
    service: AuthenticationService = Depends(get_auth_service),
) -> TokenResponse:
    token_response = await service.login(request)
    set_auth_cookies(response, token_response.access_token, get_settings())
    return token_response


@router.get(
    "/me",
    response_model=CurrentUser,
    summary="Lấy tài khoản hiện tại",
    dependencies=[Depends(rate_limit_group("read_light"))],
)
async def get_me(
    request: Request,
    response: Response,
    current_user: CurrentUser = Depends(get_current_user),
) -> CurrentUser:
    settings = get_settings()
    if not request.cookies.get(settings.auth_csrf_cookie_name):
        ensure_csrf_cookie(response, settings, None)
    return current_user


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Đăng xuất",
    dependencies=[Depends(rate_limit_group("mutation"))],
)
async def logout(response: Response) -> None:
    clear_auth_cookies(response, get_settings())
