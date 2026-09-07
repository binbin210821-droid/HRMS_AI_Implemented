from __future__ import annotations

import time
from collections.abc import AsyncIterator
from typing import cast

from app.ai.base import IAiProvider
from app.ai.providers import (
    AiProviderError,
    GeminiProvider,
    GroqProvider,
    OpenRouterProvider,
)
from app.core.config import Settings

SAFE_AI_FALLBACK_MESSAGE = (
    "Trợ lý AI hiện chưa sẵn sàng. Vui lòng thử lại sau ít phút hoặc liên hệ quản trị viên."
)


class CircuitBreaker:
    def __init__(self, failure_threshold: int, recovery_seconds: float) -> None:
        self.failure_threshold = max(1, failure_threshold)
        self.recovery_seconds = max(0.0, recovery_seconds)
        self.failure_count = 0
        self.opened_at: float | None = None

    def allow_request(self) -> bool:
        if self.opened_at is None:
            return True
        if time.monotonic() - self.opened_at >= self.recovery_seconds:
            self.opened_at = None
            self.failure_count = 0
            return True
        return False

    def record_success(self) -> None:
        self.failure_count = 0
        self.opened_at = None

    def record_failure(self) -> None:
        self.failure_count += 1
        if self.failure_count >= self.failure_threshold:
            self.opened_at = time.monotonic()


class AiProviderFactory:
    """Select a provider and fail over safely when a free-tier provider is unavailable."""

    def __init__(self, settings: Settings) -> None:
        api_key = settings.ai_api_key
        self.providers: dict[str, IAiProvider] = {
            "gemini": cast(
                IAiProvider,
                GeminiProvider(api_key, settings.ai_model, settings.ai_timeout_seconds),
            ),
            "groq": cast(
                IAiProvider,
                GroqProvider(api_key, settings.ai_model, settings.ai_timeout_seconds),
            ),
            "openrouter": cast(
                IAiProvider,
                OpenRouterProvider(api_key, settings.ai_model, settings.ai_timeout_seconds),
            ),
        }
        self.primary_name = settings.ai_provider.lower()
        self.fallback_name = settings.ai_fallback_provider.lower()
        self.breakers = {
            name: CircuitBreaker(
                settings.ai_circuit_failure_threshold, settings.ai_circuit_recovery_seconds
            )
            for name in self.providers
        }

    def _provider_order(self) -> list[str]:
        return list(
            dict.fromkeys([self.primary_name, self.fallback_name, "gemini", "groq", "openrouter"])
        )

    async def generate_insight_stream(self, prompt: str) -> AsyncIterator[str]:
        for provider_name in self._provider_order():
            provider = self.providers.get(provider_name)
            breaker = self.breakers.get(provider_name)
            if provider is None or breaker is None or not provider.configured:
                continue
            if not breaker.allow_request():
                continue
            try:
                provider_chunks: list[str] = []
                async for chunk in provider.generate_insight_stream(prompt):
                    provider_chunks.append(chunk)
                breaker.record_success()
                for chunk in provider_chunks:
                    yield chunk
                return
            except (AiProviderError, TimeoutError):
                breaker.record_failure()
                continue
            except Exception:  # Provider boundary: isolate SDK failures from the API.
                breaker.record_failure()
                continue

        # Keep one stable user-facing message for missing keys, open circuits and
        # exhausted fallback providers; provider details must not reach the UI.
        yield SAFE_AI_FALLBACK_MESSAGE
