import pytest
from pydantic import ValidationError

from app.core.config import Settings


def production_settings(**overrides) -> Settings:
    values = {
        "_env_file": None,
        "environment": "production",
        "auth_cookie_secure": True,
        "jwt_secret": "production-secret-" + "x" * 48,
        "storage_endpoint_url": "https://storage.internal.example.com",
        "storage_public_endpoint_url": "https://storage.example.com",
        "storage_access_key": "production-access",
        "storage_secret_key": "production-secret",
        "malware_scanner_enabled": True,
        "rate_limit_shadow_mode": False,
        "rate_limit_enforced_groups": "login,mutation,ai_chat",
    }
    values.update(overrides)
    return Settings(**values)


def test_credentials_cors_rejects_wildcard_origin() -> None:
    with pytest.raises(ValidationError):
        Settings(cors_origins="*")


def test_rate_limit_defaults_to_enabled_shadow_mode() -> None:
    settings = Settings()

    assert settings.rate_limit_enabled is True
    assert settings.rate_limit_shadow_mode is True


def test_ai_defaults_leave_room_for_reasoning_and_debug_off() -> None:
    settings = Settings()

    assert settings.ai_max_completion_tokens == 4096
    assert settings.ai_tool_max_completion_tokens == 256
    assert settings.ai_enable_thinking is True
    assert settings.ai_debug_stream is False


def test_production_requires_secure_auth_cookie() -> None:
    with pytest.raises(ValidationError):
        Settings(environment="production", auth_cookie_secure=False)


def test_production_accepts_secure_auth_cookie() -> None:
    settings = production_settings()

    assert settings.auth_cookie_secure is True


def test_production_rejects_default_jwt_secret() -> None:
    with pytest.raises(ValidationError, match="JWT_SECRET"):
        production_settings(jwt_secret="change-this-development-secret")


def test_production_rejects_default_storage_credentials() -> None:
    with pytest.raises(ValidationError, match="credential MinIO"):
        production_settings(storage_secret_key="minioadmin")


def test_production_rejects_shadow_only_rate_limit() -> None:
    with pytest.raises(ValidationError, match="shadow"):
        production_settings(rate_limit_shadow_mode=True, rate_limit_enforced_groups="")


def test_production_rejects_upload_without_malware_scanner() -> None:
    with pytest.raises(ValidationError, match="malware scanner"):
        production_settings(malware_scanner_enabled=False)


def test_production_rejects_non_https_storage_endpoint() -> None:
    with pytest.raises(ValidationError, match="HTTPS"):
        production_settings(storage_public_endpoint_url="http://storage.example.com")


def test_production_rate_limit_rejects_memory_backend() -> None:
    with pytest.raises(ValidationError):
        Settings(
            environment="production",
            auth_cookie_secure=True,
            rate_limit_enabled=True,
            rate_limit_backend="memory",
        )


def test_idempotency_requires_redis_url() -> None:
    with pytest.raises(ValidationError):
        Settings(
            idempotency_enabled=True,
            redis_url="",
        )


def test_request_limits_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        Settings(rate_limit_scan=0)

    with pytest.raises(ValidationError):
        Settings(idempotency_ttl_seconds=0)
