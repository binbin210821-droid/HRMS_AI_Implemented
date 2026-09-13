import hmac

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import get_settings
from app.core.http_contract import ApiError, get_request_id

SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}


def csrf_error(request: Request) -> JSONResponse:
    payload = ApiError(
        code="csrf_failed",
        message="Yêu cầu không có mã bảo vệ hợp lệ",
        request_id=get_request_id(request),
    )
    response = JSONResponse(
        status_code=403,
        content=payload.model_dump(mode="json"),
    )
    response.headers["X-Request-ID"] = payload.request_id
    return response


class CSRFMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        settings = get_settings()
        if (
            not settings.csrf_enabled
            or request.method in SAFE_METHODS
            or request.url.path.endswith("/auth/login")
            or not request.cookies.get(settings.auth_access_cookie_name)
        ):
            return await call_next(request)

        cookie_token = request.cookies.get(settings.auth_csrf_cookie_name)
        header_token = request.headers.get("X-CSRF-Token")
        if not cookie_token or not header_token:
            return csrf_error(request)
        if not hmac.compare_digest(cookie_token, header_token):
            return csrf_error(request)
        return await call_next(request)
