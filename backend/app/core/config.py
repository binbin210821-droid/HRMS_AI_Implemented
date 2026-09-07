from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "WorkMind"
    environment: str = "development"
    mongo_uri: str = "mongodb://localhost:27017/hrms?replicaSet=rs0"
    database_name: str = "hrms"
    jwt_secret: str = "change-this-development-secret"
    algorithm: str = "HS256"
    jwt_expire_minutes: int = 60
    ai_api_key: str = ""
    ai_provider: str = "groq"
    ai_fallback_provider: str = "openrouter"
    ai_model: str = "llama-3.1-8b-instant"
    ai_timeout_seconds: float = 30.0
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

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[3] / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
