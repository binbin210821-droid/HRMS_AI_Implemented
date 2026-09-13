from collections.abc import AsyncIterator

import pytest

from app.ai.factory import SAFE_AI_FALLBACK_MESSAGE, AiProviderFactory
from app.ai.providers import AiProviderError, CloudflareProvider
from app.core.config import Settings


class FailingProvider:
    name = "failing"
    configured = True

    async def generate_insight_stream(self, _prompt: str) -> AsyncIterator[str]:
        raise RuntimeError("provider unavailable")
        yield ""


class WorkingProvider:
    name = "working"
    configured = True

    async def generate_insight_stream(self, _prompt: str) -> AsyncIterator[str]:
        yield "Câu trả lời an toàn bằng tiếng Việt."


class RetryThenWorkingProvider:
    configured = True

    def __init__(self) -> None:
        self.calls = 0

    async def generate_insight_stream(self, _prompt: str) -> AsyncIterator[str]:
        self.calls += 1
        if self.calls == 1:
            raise AiProviderError("HTTP 429", retryable=True, status_code=429)
        yield "Đã thử lại thành công."


async def collect(stream: AsyncIterator[str]) -> list[str]:
    return [chunk async for chunk in stream]


@pytest.mark.asyncio
async def test_factory_falls_back_after_provider_failure() -> None:
    factory = AiProviderFactory(
        Settings(ai_api_key="demo", ai_provider="groq", ai_fallback_provider="openrouter")
    )
    factory.providers["groq"] = FailingProvider()
    factory.providers["openrouter"] = WorkingProvider()

    result = await collect(factory.generate_insight_stream("Xin chào"))

    assert result == ["Câu trả lời an toàn bằng tiếng Việt."]


@pytest.mark.asyncio
async def test_factory_falls_back_from_cloudflare_to_openrouter() -> None:
    factory = AiProviderFactory(
        Settings(
            ai_api_key="openrouter-token",
            ai_provider="cloudflare",
            ai_fallback_provider="openrouter",
            cloudflare_account_id="account-1",
            cloudflare_api_token="cloudflare-token",
        )
    )
    factory.providers["cloudflare"] = FailingProvider()
    factory.providers["openrouter"] = WorkingProvider()

    result = await collect(factory.generate_insight_stream("Xin chào"))

    assert result == ["Câu trả lời an toàn bằng tiếng Việt."]


@pytest.mark.asyncio
async def test_factory_returns_polite_message_without_api_key() -> None:
    factory = AiProviderFactory(
        Settings(
            ai_api_key="",
            ai_provider="groq",
            ai_fallback_provider="openrouter",
            cloudflare_account_id="",
            cloudflare_api_token="",
        )
    )

    result = await collect(factory.generate_insight_stream("Xin chào"))

    assert result == [SAFE_AI_FALLBACK_MESSAGE]


@pytest.mark.asyncio
async def test_factory_retries_transient_provider_error_once() -> None:
    factory = AiProviderFactory(
        Settings(
            ai_api_key="demo",
            ai_provider="groq",
            ai_fallback_provider="openrouter",
            ai_retry_attempts=1,
            ai_retry_backoff_seconds=0,
        )
    )
    provider = RetryThenWorkingProvider()
    factory.providers["groq"] = provider

    result = await collect(factory.generate_insight_stream("Xin chào"))

    assert result == ["Đã thử lại thành công."]
    assert provider.calls == 2


def test_factory_configures_cloudflare_without_exposing_credentials() -> None:
    factory = AiProviderFactory(
        Settings(
            ai_provider="cloudflare",
            ai_model="@cf/google/gemma-4-26b-a4b-it",
            cloudflare_account_id="account-1",
            cloudflare_api_token="token-1",
        )
    )

    provider = factory.providers["cloudflare"]

    assert isinstance(provider, CloudflareProvider)
    assert provider.configured is True
    assert provider.model == "@cf/google/gemma-4-26b-a4b-it"
    assert provider.max_completion_tokens == 4096
    assert factory._provider_order()[0:2] == ["cloudflare", "openrouter"]
