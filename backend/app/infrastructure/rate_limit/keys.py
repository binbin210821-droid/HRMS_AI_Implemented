import hashlib

from jose import jwt
from jose.exceptions import JWTError
from starlette.requests import HTTPConnection

from app.core.config import Settings
from app.infrastructure.rate_limit.policy import RateLimitRule


class RateLimitKeyBuilder:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def build_user_key(self, user_id: str, group: str) -> str:
        return f"rl:user:{user_id}:{group}"

    def build_anonymous_key(self, ip: str, group: str) -> str:
        return f"rl:ip:{ip}:anonymous:{group}"

    def build_login_keys(self, ip: str, username: str) -> tuple[str, str]:
        return (
            f"rl:ip:{ip}:login:{username}",
            f"rl:ip:{ip}:login",
        )

    def build_for_group(
        self,
        request: HTTPConnection,
        group: str,
        *,
        user_id: str | None = None,
        username: str | None = None,
    ) -> str | tuple[str, str]:
        """Build key theo contract mới; ``build`` bên dưới là compatibility API."""
        ip = self._client_ip(request)
        if group == "login":
            return self.build_login_keys(ip, username or "unknown")
        if user_id is None:
            token = request.cookies.get(self.settings.auth_access_cookie_name)
            if not token:
                authorization = request.headers.get("authorization", "")
                if authorization.lower().startswith("bearer "):
                    token = authorization[7:].strip()
            verified_identity = self._verified_identity(token) if token else None
            user_id = verified_identity[1] if verified_identity else None
        if user_id:
            return self.build_user_key(user_id, group)
        return self.build_anonymous_key(ip, group)

    def build(self, request: HTTPConnection, rule: RateLimitRule) -> str:
        built = self.build_for_group(request, rule.group)
        if isinstance(built, tuple):
            return built[0]
        return built

    def _identity(self, token: str | None, request: HTTPConnection) -> str:
        if not token:
            return f"anonymous:{self._client_ip(request)}"
        verified_identity = self._verified_identity(token)
        if verified_identity is not None:
            role, subject = verified_identity
            return f"{role}:user:{self._fingerprint(subject)}"
        return f"invalid-token:{self._fingerprint(token)}"

    def _client_ip(self, request: HTTPConnection) -> str:
        client_host = request.client.host if request.client else "unknown"
        trusted_proxy_value = self.settings.trusted_proxy_ips or self.settings.rate_limit_trusted_proxy_ips
        trusted_proxies = {
            value.strip()
            for value in trusted_proxy_value.split(",")
            if value.strip()
        }
        if client_host in trusted_proxies:
            forwarded = request.headers.get("X-Forwarded-For", "").split(",", 1)[0].strip()
            if forwarded:
                return forwarded
        return client_host

    @staticmethod
    def _fingerprint(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()[:32]

    def _verified_identity(self, token: str) -> tuple[str, str] | None:
        try:
            claims = jwt.decode(
                token,
                self.settings.jwt_secret,
                algorithms=[self.settings.algorithm],
            )
        except (
            JWTError,
            ValueError,
            TypeError,
        ):
            return None
        role = claims.get("role")
        subject = claims.get("sub")
        if role not in {"manager", "leadership"} or not subject:
            return None
        return str(role), str(subject)
