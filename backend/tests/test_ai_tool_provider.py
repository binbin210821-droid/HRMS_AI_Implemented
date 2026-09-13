from typing import ClassVar

import httpx
import pytest

from app.ai.tool_provider import CloudflareToolProvider


class FakeResponse:
    status_code = 200

    def json(self) -> dict[str, object]:
        return {
            "choices": [
                {
                    "message": {
                        "tool_calls": [
                            {
                                "function": {
                                    "name": "get_rebalance_candidates",
                                    "arguments": '{"alert_id":"alert-1"}',
                                }
                            }
                        ]
                    }
                }
            ]
        }


class FakeClient:
    requests: ClassVar[list[dict[str, object]]] = []

    def __init__(self, **_kwargs: object) -> None:
        self.__class__.requests = []

    async def __aenter__(self) -> "FakeClient":
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None

    async def post(self, url: str, headers: dict[str, str], json: dict[str, object]) -> FakeResponse:
        self.__class__.requests.append({"url": url, "headers": headers, "json": json})
        return FakeResponse()


@pytest.mark.asyncio
async def test_cloudflare_tool_provider_parses_tool_call(monkeypatch) -> None:
    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)
    provider = CloudflareToolProvider("account-1", "token-1", "gemma", 3, 128)

    result = await provider.generate_tool_call(
        "Tìm ứng viên cho cảnh báo alert-1",
        [
            {
                "type": "function",
                "function": {
                    "name": "get_rebalance_candidates",
                    "description": "Đọc ứng viên",
                    "parameters": {"type": "object"},
                },
            }
        ],
    )

    assert result is not None
    assert result.name == "get_rebalance_candidates"
    assert result.arguments == {"alert_id": "alert-1"}
    body = FakeClient.requests[0]["json"]
    assert body["stream"] is False
    assert body["tool_choice"] == "auto"
    assert body["chat_template_kwargs"] == {"enable_thinking": False}
    assert body["max_completion_tokens"] == 128
    system_prompt = body["messages"][0]["content"]
    assert "Không được bịa ngày tháng" in system_prompt
    assert "phòng tôi" in system_prompt
