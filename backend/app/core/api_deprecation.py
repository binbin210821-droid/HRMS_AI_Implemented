import json
import logging
from collections.abc import Callable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.core.config import Settings
from app.core.time import BusinessClock

logger = logging.getLogger(__name__)


def _is_observed_legacy_path(path: str) -> bool:
    if not path.startswith("/api/") or path.startswith("/api/v1/"):
        return False
    return not (
        path == "/api/auth"
        or path.startswith("/api/auth/")
        or path == "/api/health"
        or path.startswith("/api/health/")
    )


def _safe_log_value(value: str | None, max_length: int = 512) -> str | None:
    if value is None:
        return None
    return value.replace("\r", " ").replace("\n", " ")[:max_length]


class LegacyApiUsageMiddleware(BaseHTTPMiddleware):
    """Ghi nhận request API cũ, không query DB/Redis và không chặn request."""

    def __init__(self, app, clock: BusinessClock | None = None) -> None:
        super().__init__(app)
        self.clock = clock or BusinessClock()

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        should_log = _is_observed_legacy_path(request.url.path)
        try:
            return await call_next(request)
        finally:
            if should_log:
                fields = {
                    "event": "legacy_api_call",
                    "path": request.url.path,
                    "method": request.method,
                    "user_id": getattr(request.state, "authenticated_user_id", None),
                    "user_agent": _safe_log_value(request.headers.get("user-agent")),
                    "request_id": getattr(request.state, "request_id", None),
                    "logged_at": self.clock.now().isoformat(),
                }
                logger.info(
                    "legacy_api_call %s",
                    json.dumps(fields, ensure_ascii=False, separators=(",", ":")),
                    extra=fields,
                )


class LegacyApiDeprecationMiddleware(BaseHTTPMiddleware):
    """Giữ `/api` tương thích trong thời gian chuyển sang `/api/v1`."""

    def __init__(self, app, settings: Settings) -> None:
        super().__init__(app)
        self.settings = settings

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        path = request.url.path
        if path.startswith("/api/") and not path.startswith("/api/v1/"):
            successor = f"/api/v1{path.removeprefix('/api')}"
            if request.url.query:
                successor = f"{successor}?{request.url.query}"
            response.headers["Deprecation"] = "true"
            response.headers["Sunset"] = self.settings.legacy_api_sunset
            response.headers["Link"] = f"<{successor}>; rel=\"successor-version\""
        return response
