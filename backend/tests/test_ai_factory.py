from collections.abc import AsyncIterator

import pytest

from app.ai.factory import SAFE_AI_FALLBACK_MESSAGE, AiProviderFactory
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


async def collect(stream: AsyncIterator[str]) -> list[str]:
    return [chunk async for chunk in stream]


@pytest.mark.asyncio
async def test_factory_falls_back_after_provider_failure() -> None:
    factory = AiProviderFactory(Settings(ai_api_key="demo"))
    factory.providers["groq"] = FailingProvider()
    factory.providers["openrouter"] = WorkingProvider()

    result = await collect(factory.generate_insight_stream("Xin chào"))

    assert result == ["Câu trả lời an toàn bằng tiếng Việt."]


@pytest.mark.asyncio
async def test_factory_returns_polite_message_without_api_key() -> None:
    factory = AiProviderFactory(Settings(ai_api_key=""))

    result = await collect(factory.generate_insight_stream("Xin chào"))

    assert result == [SAFE_AI_FALLBACK_MESSAGE]
