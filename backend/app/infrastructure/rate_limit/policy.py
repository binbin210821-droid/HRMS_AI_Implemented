from dataclasses import dataclass

from app.core.config import Settings

RATE_LIMIT_GROUPS = {
    "read_light",
    "read_operational",
    "read_heavy",
    "mutation",
    "directive_action",
    "login",
    "upload_session",
    "upload_completion",
    "ai_chat",
    "scan",
    "websocket_handshake",
    "health",
}
HEALTH_BYPASS_GROUPS = frozenset({"health"})


@dataclass(frozen=True)
class RateLimitRule:
    group: str
    limit: int
    window_seconds: int = 60
    sensitive: bool = False


class RateLimitPolicy:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def is_bypassed(self, group: str) -> bool:
        return group in HEALTH_BYPASS_GROUPS

    def rule_for_group(self, group: str) -> RateLimitRule:
        """Trả policy theo group do route khai báo, không suy luận từ URL."""
        if group not in RATE_LIMIT_GROUPS:
            raise ValueError(f"Nhóm rate limit không hợp lệ: {group}")
        if self.is_bypassed(group):
            return RateLimitRule(group, 0)

        limits = {
            "read_light": self.settings.rate_limit_default,
            "read_operational": self.settings.rate_limit_operational
            or self.settings.rate_limit_default,
            "read_heavy": self.settings.rate_limit_read_heavy
            or self.settings.rate_limit_heavy_read
            or self.settings.rate_limit_default,
            "mutation": self.settings.rate_limit_mutation,
            "directive_action": self.settings.rate_limit_directive
            or self.settings.rate_limit_default,
            "login": self.settings.rate_limit_login,
            "upload_session": self.settings.rate_limit_upload_session
            or self.settings.rate_limit_upload
            or self.settings.rate_limit_default,
            "upload_completion": self.settings.rate_limit_upload_completion
            or self.settings.rate_limit_upload_mutation
            or self.settings.rate_limit_default,
            "ai_chat": self.settings.rate_limit_ai_chat
            or self.settings.rate_limit_ai
            or self.settings.rate_limit_default,
            "scan": self.settings.rate_limit_scan,
            "websocket_handshake": self.settings.rate_limit_ws_handshake
            or self.settings.rate_limit_default,
        }
        sensitive = group in {
            "login",
            "directive_action",
            "upload_session",
            "upload_completion",
            "ai_chat",
            "scan",
            "websocket_handshake",
        }
        return RateLimitRule(group, limits[group], sensitive=sensitive)
