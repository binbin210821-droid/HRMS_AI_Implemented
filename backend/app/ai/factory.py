from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import AsyncIterator
from typing import cast

from app.ai.base import IAiProvider
from app.ai.providers import (
    AiProviderError,
    CloudflareProvider,
    GeminiProvider,
    GroqProvider,
    OpenRouterProvider,
)
from app.core.config import Settings

logger = logging.getLogger(__name__)

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
            "cloudflare": cast(
                IAiProvider,
                CloudflareProvider(
                    settings.cloudflare_account_id,
                    settings.cloudflare_api_token,
                    settings.ai_model,
                    settings.ai_timeout_seconds,
                    settings.ai_max_completion_tokens,
                    settings.ai_summary_max_completion_tokens,
                    settings.ai_connect_timeout_seconds,
                    settings.ai_first_token_timeout_seconds,
                    settings.ai_idle_timeout_seconds,
                    settings.ai_enable_thinking,
                    settings.ai_debug_stream,
                ),
            ),
            "gemini": cast(
                IAiProvider,
                GeminiProvider(api_key, settings.ai_model, settings.ai_timeout_seconds),
            ),
            "groq": cast(
                IAiProvider,
                GroqProvider(
                    api_key,
                    settings.ai_model,
                    settings.ai_timeout_seconds,
                    settings.ai_max_completion_tokens,
                    settings.ai_summary_max_completion_tokens,
                    settings.ai_connect_timeout_seconds,
                    settings.ai_first_token_timeout_seconds,
                    settings.ai_idle_timeout_seconds,
                ),
            ),
            "openrouter": cast(
                IAiProvider,
                OpenRouterProvider(
                    api_key,
                    settings.ai_fallback_model or settings.ai_model,
                    settings.ai_timeout_seconds,
                    settings.ai_max_completion_tokens,
                    settings.ai_summary_max_completion_tokens,
                    settings.ai_connect_timeout_seconds,
                    settings.ai_first_token_timeout_seconds,
                    settings.ai_idle_timeout_seconds,
                ),
            ),
        }
        self.primary_name = settings.ai_provider.lower()
        self.fallback_name = settings.ai_fallback_provider.lower()
        self.retry_attempts = max(0, settings.ai_retry_attempts)
        self.retry_backoff_seconds = max(0.0, settings.ai_retry_backoff_seconds)
        self.breakers = {
            name: CircuitBreaker(
                settings.ai_circuit_failure_threshold, settings.ai_circuit_recovery_seconds
            )
            for name in self.providers
        }

    def _provider_order(self) -> list[str]:
        return list(
            dict.fromkeys(
                [self.primary_name, self.fallback_name, "cloudflare", "gemini", "groq", "openrouter"]
            )
        )

    async def generate_insight_stream(
        self, prompt: str, request_id: str | None = None
    ) -> AsyncIterator[str]:
        for provider_name in self._provider_order():
            provider = self.providers.get(provider_name)
            breaker = self.breakers.get(provider_name)
            if provider is None or breaker is None or not provider.configured:
                continue
            if not breaker.allow_request():
                logger.info(
                    "ai_provider_skipped %s",
                    json.dumps(
                        {
                            "request_id": request_id,
                            "provider": provider_name,
                            "reason": "circuit_open",
                        },
                        sort_keys=True,
                    ),
                )
                continue
            attempt_started = time.perf_counter()
            first_chunk_at: float | None = None
            chunk_count = 0
            output_chars = 0
            for attempt in range(self.retry_attempts + 1):
                try:
                    provider_chunks: list[str] = []
                    async for chunk in provider.generate_insight_stream(prompt):
                        provider_chunks.append(chunk)
                        if first_chunk_at is None:
                            first_chunk_at = time.perf_counter()
                        chunk_count += 1
                        output_chars += len(chunk)
                    if not "".join(provider_chunks).strip():
                        raise AiProviderError(
                            "Nhà cung cấp AI trả về stream rỗng",
                            retryable=True,
                            error_type="empty_output",
                        )
                    breaker.record_success()
                    logger.info(
                        "ai_provider_success %s",
                        json.dumps(
                            {
                                "request_id": request_id,
                                "provider": provider_name,
                                "attempt": attempt + 1,
                                "duration_ms": round(
                                    (time.perf_counter() - attempt_started) * 1000
                                ),
                                "first_chunk_ms": (
                                    round((first_chunk_at - attempt_started) * 1000)
                                    if first_chunk_at is not None
                                    else None
                                ),
                                "chunk_count": chunk_count,
                                "output_chars": output_chars,
                            },
                            sort_keys=True,
                        ),
                    )
                    for chunk in provider_chunks:
                        yield chunk
                    return
                except AiProviderError as error:
                    should_retry = error.retryable and attempt < self.retry_attempts
                    error_type = error.error_type
                    status_code = error.status_code
                except TimeoutError:
                    should_retry = attempt < self.retry_attempts
                    error_type = "timeout"
                    status_code = None
                except Exception:  # Provider boundary: isolate SDK failures from the API.
                    should_retry = False
                    error_type = "provider_error"
                    status_code = None

                logger.warning(
                    "ai_provider_failure %s",
                    json.dumps(
                        {
                            "request_id": request_id,
                            "provider": provider_name,
                            "attempt": attempt + 1,
                            "duration_ms": round(
                                (time.perf_counter() - attempt_started) * 1000
                            ),
                            "error_type": error_type,
                            "status_code": status_code,
                            "retryable": should_retry,
                        },
                        sort_keys=True,
                    ),
                )

                if should_retry:
                    await asyncio.sleep(self.retry_backoff_seconds * (2**attempt))
                    continue
                breaker.record_failure()
                break

        # Keep one stable user-facing message for missing keys, open circuits and
        # exhausted fallback providers; provider details must not reach the UI.
        yield SAFE_AI_FALLBACK_MESSAGE
