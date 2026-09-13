from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from pydantic import AliasChoices, Field, PrivateAttr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEVELOPMENT_JWT_SECRET = "change-this-development-secret"
DEVELOPMENT_STORAGE_CREDENTIAL = "minioadmin"


class Settings(BaseSettings):
    app_name: str = "WorkMind"
    environment: str = "development"
    mongo_uri: str = "mongodb://localhost:27017/hrms?replicaSet=rs0"
    database_name: str = "hrms"
    jwt_secret: str = DEVELOPMENT_JWT_SECRET
    algorithm: str = "HS256"
    jwt_expire_minutes: int = 60
    auth_access_cookie_name: str = "hrms_access_token"
    auth_csrf_cookie_name: str = "hrms_csrf_token"
    auth_cookie_secure: bool = False
    auth_cookie_samesite: str = "lax"
    auth_cookie_domain: str = ""
    auth_cookie_max_age: int = 3600
    csrf_enabled: bool = True
    legacy_bearer_enabled: bool = True
    legacy_ws_query_token_enabled: bool = True
    legacy_api_sunset: str = "2027-03-01T00:00:00Z"
    redis_url: str = "redis://localhost:6379/0"
    rate_limit_backend: Literal["redis", "memory"] = "redis"
    rate_limit_enabled: bool = True
    rate_limit_shadow_mode: bool = True
    rate_limit_enforced_groups: str = ""
    rate_limit_fail_mode: Literal["open", "closed"] = "open"
    rate_limit_default: int = 120
    rate_limit_operational: int | None = None
    rate_limit_heavy_read: int | None = None
    rate_limit_mutation: int = 30
    rate_limit_login: int = 10
    rate_limit_ai: int | None = None
    rate_limit_upload: int | None = None
    rate_limit_upload_mutation: int | None = None
    rate_limit_scan: int = 5
    rate_limit_trusted_proxy_ips: str = ""
    # Tên canonical theo contract rate-limit mới. Các field legacy phía trên
    # vẫn được giữ để client/config hiện tại chuyển đổi dần.
    rate_limit_read_heavy: int | None = Field(
        default=None,
        validation_alias=AliasChoices("RATE_LIMIT_READ_HEAVY", "RATE_LIMIT_HEAVY_READ"),
    )
    rate_limit_directive: int | None = None
    rate_limit_upload_session: int | None = Field(
        default=None,
        validation_alias=AliasChoices("RATE_LIMIT_UPLOAD_SESSION", "RATE_LIMIT_UPLOAD"),
    )
    rate_limit_upload_completion: int | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "RATE_LIMIT_UPLOAD_COMPLETION", "RATE_LIMIT_UPLOAD_MUTATION"
        ),
    )
    rate_limit_ai_chat: int | None = Field(
        default=None,
        validation_alias=AliasChoices("RATE_LIMIT_AI_CHAT", "RATE_LIMIT_AI"),
    )
    rate_limit_ws_handshake: int | None = None
    trusted_proxy_ips: str = Field(
        default="",
        validation_alias=AliasChoices("TRUSTED_PROXY_IPS", "RATE_LIMIT_TRUSTED_PROXY_IPS"),
    )
    idempotency_enabled: bool = True
    idempotency_ttl_seconds: int = 86400
    ai_api_key: str = ""
    ai_provider: str = "groq"
    ai_fallback_provider: str = "openrouter"
    ai_model: str = "llama-3.1-8b-instant"
    ai_fallback_model: str = ""
    cloudflare_account_id: str = ""
    cloudflare_api_token: str = ""
    ai_timeout_seconds: float = 30.0
    ai_connect_timeout_seconds: float = 5.0
    ai_first_token_timeout_seconds: float = 15.0
    ai_idle_timeout_seconds: float = 15.0
    ai_total_timeout_seconds: float = 60.0
    ai_max_completion_tokens: int | None = 4096
    ai_tool_max_completion_tokens: int | None = 256
    ai_summary_max_completion_tokens: int = 320
    ai_enable_thinking: bool = True
    ai_debug_stream: bool = False
    ai_summary_context_max_chars: int = 24000
    ai_summary_cache_ttl_seconds: int = 300
    ai_summary_cache_max_entries: int = 256
    ai_retry_attempts: int = 1
    ai_retry_backoff_seconds: float = 0.5
    ai_proposal_cache_ttl_seconds: int = 300
    ai_proposal_cache_max_entries: int = 256
    ai_rag_enabled: bool = False
    ai_embedding_model: str = "@cf/qwen/qwen3-embedding-0.6b"
    ai_vector_index_name: str = "ai_knowledge_embedding"
    ai_rag_top_k: int = 4
    ai_rag_local_fallback_enabled: bool = False
    ai_circuit_failure_threshold: int = 2
    ai_circuit_recovery_seconds: float = 60.0
    cors_origins: str = "http://localhost:5173"
    # Development mặc định dùng MinIO trong docker-compose; production ghi đè
    # toàn bộ nhóm biến STORAGE_* bằng S3/R2 tương ứng.
    storage_endpoint_url: str = "http://localhost:9000"
    storage_internal_endpoint_url: str = ""
    storage_public_endpoint_url: str = ""
    storage_bucket: str = "hrms-evidence"
    storage_region: str = "us-east-1"
    storage_access_key: str = "minioadmin"
    storage_secret_key: str = "minioadmin"
    storage_signed_url_ttl: int = 900
    storage_direct_upload_enabled: bool = False
    storage_upload_url_ttl: int = 600
    storage_upload_session_ttl: int = 900
    storage_public_cors_origins: str = "http://localhost:5173"
    storage_max_file_size: int = 10 * 1024 * 1024
    storage_max_files_per_evaluation: int = 5
    malware_scanner_enabled: bool = False
    malware_scanner_host: str = "localhost"
    malware_scanner_port: int = 3310
    malware_scanner_timeout_seconds: float = 10.0
    storage_allowed_content_types: set[str] = {
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-powerpoint",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "image/png",
        "image/jpeg",
        "text/plain",
    }
    business_timezone: str = "Asia/Ho_Chi_Minh"
    weekly_evaluation_cutoff_hour: int = 17

    _rate_limit_enforced_groups_cache: set[str] | None = PrivateAttr(default=None)

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[3] / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        populate_by_name=True,
        extra="ignore",
    )

    @field_validator("cors_origins")
    @classmethod
    def reject_wildcard_origins_with_credentials(cls, value: str) -> str:
        origins = {origin.strip() for origin in value.split(",") if origin.strip()}
        if "*" in origins:
            raise ValueError("CORS_ORIGINS không được chứa '*' khi bật credentials.")
        return value

    @field_validator(
        "rate_limit_default",
        "rate_limit_operational",
        "rate_limit_heavy_read",
        "rate_limit_mutation",
        "rate_limit_login",
        "rate_limit_ai",
        "rate_limit_upload",
        "rate_limit_upload_mutation",
        "rate_limit_scan",
        "rate_limit_read_heavy",
        "rate_limit_directive",
        "rate_limit_upload_session",
        "rate_limit_upload_completion",
        "rate_limit_ai_chat",
        "rate_limit_ws_handshake",
        "idempotency_ttl_seconds",
    )
    @classmethod
    def require_positive_request_limits(cls, value: int | None) -> int | None:
        if value is not None and value <= 0:
            raise ValueError("Các quota rate limit và TTL idempotency phải lớn hơn 0.")
        return value

    @model_validator(mode="after")
    def require_secure_auth_cookie_in_production(self):
        is_production = self.environment.lower() == "production"
        if is_production and not self.auth_cookie_secure:
            raise ValueError("AUTH_COOKIE_SECURE phải là true trong production.")
        if (
            is_production
            and self.rate_limit_enabled
            and self.rate_limit_backend != "redis"
        ):
            raise ValueError("Production phải dùng Redis cho rate limiting phân tán.")
        if is_production:
            if self.jwt_secret.strip() == DEVELOPMENT_JWT_SECRET or len(self.jwt_secret) < 32:
                raise ValueError(
                    "JWT_SECRET production phải là secret riêng và có ít nhất 32 ký tự."
                )
            if (
                self.storage_access_key.strip() == DEVELOPMENT_STORAGE_CREDENTIAL
                or self.storage_secret_key.strip() == DEVELOPMENT_STORAGE_CREDENTIAL
            ):
                raise ValueError("Production không được dùng credential MinIO mặc định.")
            if self.rate_limit_enabled and (
                not self.rate_limit_enforced_groups_set
                and self.rate_limit_shadow_mode
            ):
                raise ValueError(
                    "Production không được chạy rate limiting chỉ ở chế độ shadow."
                )
            if self.storage_bucket.strip():
                endpoint = self.storage_public_endpoint_url or self.storage_endpoint_url
                parsed_endpoint = urlparse(endpoint)
                if parsed_endpoint.scheme != "https" or parsed_endpoint.hostname in {
                    "localhost",
                    "127.0.0.1",
                    "::1",
                }:
                    raise ValueError(
                        "Storage production phải dùng endpoint public HTTPS, không dùng localhost."
                    )
                if not self.malware_scanner_enabled:
                    raise ValueError(
                        "Production phải bật malware scanner khi dùng evidence storage."
                    )
        if self.idempotency_enabled and not self.redis_url.strip():
            raise ValueError("IDEMPOTENCY_ENABLED yêu cầu REDIS_URL hợp lệ.")
        return self

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def rate_limit_enforced_groups_set(self) -> set[str]:
        """Parse rollout overrides once per settings instance."""
        if self._rate_limit_enforced_groups_cache is None:
            self._rate_limit_enforced_groups_cache = {
                group.strip()
                for group in self.rate_limit_enforced_groups.split(",")
                if group.strip()
            }
        return self._rate_limit_enforced_groups_cache


@lru_cache
def get_settings() -> Settings:
    return Settings()
