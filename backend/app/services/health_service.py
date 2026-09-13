from datetime import datetime, timezone

from fastapi import HTTPException, status

from app.models.health import HealthResponse
from app.repositories.health_repository import HealthRepository

PROCESS_STARTED_AT = datetime.now(timezone.utc)


class HealthService:
    def __init__(self, repository: HealthRepository, settings=None) -> None:
        self.repository = repository
        self.settings = settings

    async def check(self) -> HealthResponse:
        if not await self.repository.is_database_available():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Cơ sở dữ liệu chưa sẵn sàng",
            )
        settings = self.settings
        provider = str(getattr(settings, "ai_provider", "")) or None
        fallback_provider = str(getattr(settings, "ai_fallback_provider", "")) or None
        return HealthResponse(
            status="healthy",
            timestamp=datetime.now(timezone.utc),
            process_started_at=PROCESS_STARTED_AT,
            ai_provider=provider,
            ai_model=str(getattr(settings, "ai_model", "")) or None,
            ai_provider_configured=_provider_configured(settings, provider),
            ai_fallback_provider=fallback_provider,
            ai_fallback_configured=_provider_configured(settings, fallback_provider),
        )


def _provider_configured(settings, provider: str | None) -> bool | None:
    if settings is None or provider is None:
        return None
    normalized = provider.lower()
    if normalized == "cloudflare":
        return bool(
            str(getattr(settings, "cloudflare_account_id", "")).strip()
            and str(getattr(settings, "cloudflare_api_token", "")).strip()
        )
    if normalized in {"gemini", "groq", "openrouter"}:
        return bool(str(getattr(settings, "ai_api_key", "")).strip())
    return False
