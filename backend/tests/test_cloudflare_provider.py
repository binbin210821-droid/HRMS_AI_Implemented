import logging
from collections.abc import AsyncIterator
from typing import ClassVar

import httpx
import pytest

from app.ai.base import AI_SUMMARY_MODE_MARKER, JSON_OBJECT_MODE_MARKER
from app.ai.providers import AiProviderError, CloudflareProvider


class FakeResponse:
    def __init__(self, status_code: int, lines: list[str]) -> None:
        self.status_code = status_code
        self.lines = lines

    async def __aenter__(self) -> "FakeResponse":
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None

    async def aiter_lines(self) -> AsyncIterator[str]:
        for line in self.lines:
            yield line


class FakeClient:
    response: FakeResponse
    requests: ClassVar[list[dict[str, object]]] = []

    def __init__(self, **_kwargs: object) -> None:
        self.__class__.requests = []

    async def __aenter__(self) -> "FakeClient":
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None

    def stream(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        json: dict[str, object],
    ) -> FakeResponse:
        self.__class__.requests.append(
            {"method": method, "url": url, "headers": headers, "json": json}
        )
        return self.__class__.response


def make_provider(
    max_completion_tokens: int | None = None,
    summary_max_completion_tokens: int | None = None,
    *,
    enable_thinking: bool = True,
    debug_stream: bool = False,
) -> CloudflareProvider:
    return CloudflareProvider(
        account_id="account-1",
        api_token="token-1",
        model="@cf/google/gemma-4-26b-a4b-it",
        timeout_seconds=3,
        max_completion_tokens=max_completion_tokens,
        summary_max_completion_tokens=summary_max_completion_tokens,
        enable_thinking=enable_thinking,
        debug_stream=debug_stream,
    )


async def collect(stream: AsyncIterator[str]) -> list[str]:
    return [chunk async for chunk in stream]


@pytest.mark.asyncio
async def test_cloudflare_provider_streams_openai_compatible_response(monkeypatch) -> None:
    FakeClient.response = FakeResponse(
        200,
        [
            'data: {"choices":[{"delta":{"content":"Xin "}}]}',
            'data: {"choices":[{"delta":{"content":"chào"}}]}',
            "data: [DONE]",
        ],
    )
    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)

    result = await collect(make_provider().generate_insight_stream("Xin chào"))

    assert result == ["Xin ", "chào"]
    request = FakeClient.requests[0]
    assert request["method"] == "POST"
    assert request["url"] == (
        "https://api.cloudflare.com/client/v4/accounts/account-1/ai/v1/chat/completions"
    )
    assert request["headers"] == {
        "Authorization": "Bearer token-1",
        "Content-Type": "application/json",
    }
    assert request["json"] == {
        "model": "@cf/google/gemma-4-26b-a4b-it",
        "messages": [
            {
                "role": "system",
                "content": "Bạn là trợ lý phân tích hiệu suất, chỉ trả lời bằng tiếng Việt dễ hiểu.",
            },
            {"role": "user", "content": "Xin chào"},
        ],
        "stream": True,
        "temperature": 0.2,
    }


def test_cloudflare_provider_parses_reasoning_and_content_separately() -> None:
    parsed = CloudflareProvider._parse_sse_payload(
        'data: {"choices":[{"delta":{"reasoning_content":"Suy luận",'
        '"content":"Câu trả lời"},"finish_reason":"stop"}]}'
    )

    assert parsed.reasoning == "Suy luận"
    assert parsed.text == "Câu trả lời"
    assert parsed.finish_reason == "stop"


@pytest.mark.asyncio
async def test_cloudflare_provider_sends_max_completion_tokens(monkeypatch) -> None:
    FakeClient.response = FakeResponse(200, ['data: {"choices":[{"delta":{"content":"ok"}}]}'])
    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)

    await collect(make_provider(max_completion_tokens=128).generate_insight_stream("Xin chào"))

    assert FakeClient.requests[0]["json"]["max_completion_tokens"] == 128


@pytest.mark.asyncio
async def test_cloudflare_provider_uses_json_object_mode_marker(monkeypatch) -> None:
    FakeClient.response = FakeResponse(200, ['data: {"choices":[{"delta":{"content":"{}"}}]}'])
    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)

    await collect(
        make_provider().generate_insight_stream(
            f"{JSON_OBJECT_MODE_MARKER}\nChỉ trả JSON"
        )
    )

    request = FakeClient.requests[0]["json"]
    assert request["response_format"] == {"type": "json_object"}
    assert request["chat_template_kwargs"] == {"enable_thinking": False}
    assert request["messages"][1]["content"] == "Chỉ trả JSON"


@pytest.mark.asyncio
async def test_cloudflare_provider_can_disable_thinking_for_normal_chat(monkeypatch) -> None:
    FakeClient.response = FakeResponse(200, ['data: {"choices":[{"delta":{"content":"ok"}}]}'])
    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)

    await collect(
        make_provider(enable_thinking=False).generate_insight_stream("Xin chào")
    )

    assert FakeClient.requests[0]["json"]["chat_template_kwargs"] == {
        "enable_thinking": False
    }


@pytest.mark.asyncio
async def test_cloudflare_provider_ignores_reasoning_but_keeps_answer_content(monkeypatch) -> None:
    FakeClient.response = FakeResponse(
        200,
        [
            'data: {"choices":[{"delta":{"reasoning_content":"Suy luận nội bộ"}}]}',
            'data: {"choices":[{"delta":{"content":"Kết luận an toàn"},"finish_reason":"stop"}]}',
        ],
    )
    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)

    result = await collect(
        make_provider(summary_max_completion_tokens=320).generate_insight_stream(
            f"{AI_SUMMARY_MODE_MARKER}\nTóm tắt"
        )
    )

    assert result == ["Kết luận an toàn"]
    assert FakeClient.requests[0]["json"]["max_completion_tokens"] == 320
    assert FakeClient.requests[0]["json"]["chat_template_kwargs"] == {
        "enable_thinking": False
    }


@pytest.mark.asyncio
async def test_cloudflare_provider_rejects_reasoning_only_as_empty_output(monkeypatch) -> None:
    FakeClient.response = FakeResponse(
        200,
        ['data: {"choices":[{"delta":{"reasoning_content":"Chỉ suy luận"}}]}'],
    )
    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)

    with pytest.raises(AiProviderError, match="stream rỗng") as error:
        await collect(make_provider().generate_insight_stream("Tóm tắt"))

    assert error.value.error_type == "empty_output"


@pytest.mark.asyncio
async def test_cloudflare_provider_reports_reasoning_truncated_on_length(monkeypatch) -> None:
    FakeClient.response = FakeResponse(
        200,
        [
            'data: {"choices":[{"delta":{"reasoning_content":"Suy luận dài"}}]}',
            'data: {"choices":[{"delta":{},"finish_reason":"length"}]}',
        ],
    )
    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)

    with pytest.raises(AiProviderError, match="bị cắt khi đang suy luận") as error:
        await collect(make_provider(max_completion_tokens=50).generate_insight_stream("Tóm tắt"))

    assert error.value.error_type == "reasoning_truncated"
    assert error.value.retryable is True


@pytest.mark.asyncio
async def test_cloudflare_provider_logs_raw_sse_when_debug_enabled(monkeypatch, caplog) -> None:
    FakeClient.response = FakeResponse(
        200,
        [
            'data: {"choices":[{"delta":{"reasoning_content":"Suy luận",'
            '"content":"Câu trả lời"}}]}',
        ],
    )
    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)
    caplog.set_level(logging.DEBUG, logger="app.ai.providers")

    await collect(make_provider(debug_stream=True).generate_insight_stream("Xin chào"))

    assert '"reasoning_content":"Suy luận"' in caplog.text
    assert '"content":"Câu trả lời"' in caplog.text


@pytest.mark.asyncio
async def test_cloudflare_provider_rejects_empty_stream(monkeypatch) -> None:
    FakeClient.response = FakeResponse(200, ["data: [DONE]"])
    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)

    with pytest.raises(AiProviderError) as error:
        await collect(make_provider().generate_insight_stream("Tóm tắt"))

    assert error.value.error_type == "empty_output"


@pytest.mark.parametrize("status_code", [401, 403, 429])
@pytest.mark.asyncio
async def test_cloudflare_provider_translates_http_errors(status_code: int, monkeypatch) -> None:
    FakeClient.response = FakeResponse(status_code, [])
    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)

    with pytest.raises(AiProviderError, match=f"HTTP {status_code}"):
        await collect(make_provider().generate_insight_stream("Xin chào"))


@pytest.mark.asyncio
async def test_cloudflare_provider_translates_timeout(monkeypatch) -> None:
    class TimeoutClient(FakeClient):
        def stream(self, *_args: object, **_kwargs: object) -> FakeResponse:
            raise httpx.ReadTimeout("provider timeout")

    monkeypatch.setattr(httpx, "AsyncClient", TimeoutClient)

    with pytest.raises(AiProviderError, match="Không thể kết nối"):
        await collect(make_provider().generate_insight_stream("Xin chào"))


@pytest.mark.asyncio
async def test_cloudflare_provider_requires_account_and_token(monkeypatch) -> None:
    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)
    provider = CloudflareProvider("", "", "@cf/google/gemma-4-26b-a4b-it", 3)

    assert provider.configured is False
    with pytest.raises(AiProviderError, match="chưa được cấu hình"):
        await collect(provider.generate_insight_stream("Xin chào"))
