import hashlib
import logging
import time
from collections.abc import Callable
from typing import Any

from fastapi import HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.core.config import Settings
from app.core.http_contract import get_request_id
from app.infrastructure.rate_limit.interface import RateLimiter
from app.infrastructure.rate_limit.keys import RateLimitKeyBuilder
from app.infrastructure.rate_limit.policy import RateLimitPolicy

logger = logging.getLogger(__name__)
_ENFORCEMENT_LOG_INTERVAL_SECONDS = 60.0
_last_enforcement_logs: dict[tuple[str, str], float] = {}


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        limiter: RateLimiter,
        settings: Settings | None = None,
        policy: RateLimitPolicy | None = None,
        key_builder: RateLimitKeyBuilder | None = None,
    ) -> None:
        super().__init__(app)
        self.limiter = limiter  # Compatibility constructor; enforcement lives in dependencies.
        self.settings = settings or (policy.settings if policy else Settings())
        self.policy = policy or RateLimitPolicy(self.settings)
        self.keys = key_builder or RateLimitKeyBuilder(self.settings)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        decision = getattr(request.state, "rate_limit_decision", None)
        if decision is not None:
            response.headers.update(
                {
                    "X-RateLimit-Limit": str(decision.limit),
                    "X-RateLimit-Remaining": str(decision.remaining),
                    "X-RateLimit-Reset": str(int(decision.reset_at.timestamp())),
                }
            )
            if not decision.allowed:
                response.headers["X-RateLimit-Shadow"] = "true"
            if getattr(request.state, "rate_limit_shadow_denied", False):
                response.headers["X-RateLimit-Shadow"] = "true"
        return response


def _runtime_components_from_app(app: Any) -> tuple[RateLimiter, RateLimitPolicy, RateLimitKeyBuilder]:
    settings = getattr(app.state, "settings", None)
    if settings is None:
        settings = Settings()
    limiter = getattr(app.state, "rate_limiter", None)
    policy = getattr(app.state, "rate_limit_policy", None)
    key_builder = getattr(app.state, "rate_limit_key_builder", None)
    if limiter is None:
        raise RuntimeError("Rate limiter chưa được cấu hình cho ứng dụng")
    return (
        limiter,
        policy or RateLimitPolicy(settings),
        key_builder or RateLimitKeyBuilder(settings),
    )


def _runtime_components(request: Request) -> tuple[RateLimiter, RateLimitPolicy, RateLimitKeyBuilder]:
    return _runtime_components_from_app(request.app)


def _rate_limit_http_exception(
    status_code: int,
    code: str,
    message: str,
    request: Request,
    details: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> HTTPException:
    detail = {
        "code": code,
        "message": message,
        "details": details,
    }
    exception_headers = dict(headers or {})
    exception_headers["X-Request-ID"] = get_request_id(request)
    return HTTPException(status_code=status_code, detail=detail, headers=exception_headers)


def _rate_limit_key_hash(key: str) -> str:
    """Không ghi raw IP/user/token vào log; chỉ ghi fingerprint truy vấn được."""

    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


def _log_rate_limit_observation(
    request: Request,
    group: str,
    key: str,
    decision: str,
) -> None:
    request_id = get_request_id(request)
    fields = {
        "event": "rate_limit_shadow",
        "group": group,
        "key": _rate_limit_key_hash(key),
        "decision": decision,
        "method": request.method,
        "path": request.url.path,
        "request_id": request_id,
    }
    logger.info(
        "event=rate_limit_shadow group=%s key=%s decision=%s method=%s path=%s request_id=%s",
        fields["group"],
        fields["key"],
        fields["decision"],
        fields["method"],
        fields["path"],
        fields["request_id"],
        extra=fields,
    )


def _log_rate_limit_enforcement(request: Request, group: str, key: str) -> None:
    """Warn once per group/key during a short window without logging secrets."""
    cache_key = (group, _rate_limit_key_hash(key))
    now = time.monotonic()
    last_logged = _last_enforcement_logs.get(cache_key)
    if last_logged is not None and now - last_logged < _ENFORCEMENT_LOG_INTERVAL_SECONDS:
        return
    _last_enforcement_logs[cache_key] = now
    fields = {
        "event": "rate_limit_enforced",
        "group": group,
        "key": cache_key[1],
        "decision": "enforced_denied",
        "method": request.method,
        "path": request.url.path,
        "request_id": get_request_id(request),
    }
    logger.warning(
        "event=rate_limit_enforced group=%s key=%s decision=%s method=%s path=%s request_id=%s",
        fields["group"],
        fields["key"],
        fields["decision"],
        fields["method"],
        fields["path"],
        fields["request_id"],
        extra=fields,
    )


def rate_limit_group(group: str) -> Callable:
    """FastAPI dependency để route khai báo group một cách tường minh."""

    async def dependency(request: Request) -> None:
        limiter, policy, keys = _runtime_components(request)
        settings = policy.settings
        if not settings.rate_limit_enabled:
            return
        rule = policy.rule_for_group(group)
        if policy.is_bypassed(group):
            return

        username: str | None = None
        if group == "login":
            try:
                payload = await request.json()
                candidate = payload.get("username") if isinstance(payload, dict) else None
                username = str(candidate).strip() if candidate else None
            except (ValueError, TypeError):
                username = None

        built_keys = keys.build_for_group(request, group, username=username)
        check_keys = built_keys if isinstance(built_keys, tuple) else (built_keys,)
        observation_key = "|".join(check_keys)
        try:
            decisions = [
                await limiter.check(key, rule.limit, rule.window_seconds)
                for key in check_keys
            ]
        except Exception as error:
            _log_rate_limit_observation(request, group, observation_key, "backend_error")
            if rule.sensitive or settings.rate_limit_fail_mode == "closed":
                raise _rate_limit_http_exception(
                    status.HTTP_503_SERVICE_UNAVAILABLE,
                    "rate_limit_unavailable",
                    "Hệ thống giới hạn truy cập chưa sẵn sàng. Vui lòng thử lại sau.",
                    request,
                ) from error
            return

        decision = min(decisions, key=lambda item: item.remaining)
        request.state.rate_limit_decision = decision
        denied = next((decision for decision in decisions if not decision.allowed), None)
        if denied is None:
            _log_rate_limit_observation(request, group, observation_key, "allowed")
            return

        is_shadow = (
            settings.rate_limit_shadow_mode
            and group not in settings.rate_limit_enforced_groups_set
        )
        if is_shadow:
            request.state.rate_limit_decision = denied
            request.state.rate_limit_shadow_denied = True
            _log_rate_limit_observation(request, group, observation_key, "shadow_denied")
            return

        _log_rate_limit_enforcement(request, group, observation_key)
        raise _rate_limit_http_exception(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "rate_limit_exceeded",
            "Bạn thao tác quá nhanh. Vui lòng thử lại sau.",
            request,
            {"retry_after_seconds": denied.retry_after_seconds},
            {
                "Retry-After": str(denied.retry_after_seconds),
                "X-RateLimit-Limit": str(denied.limit),
                "X-RateLimit-Remaining": str(denied.remaining),
                "X-RateLimit-Reset": str(int(denied.reset_at.timestamp())),
            },
        )

    return dependency
