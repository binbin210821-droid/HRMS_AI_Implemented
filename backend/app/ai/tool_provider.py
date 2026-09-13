from __future__ import annotations

import json
from typing import Any, Protocol

import httpx

from app.ai.providers import AiProviderError, _HttpProvider
from app.ai.tooling import ToolCall


class IAiToolProvider(Protocol):
    name: str
    configured: bool

    async def generate_tool_call(
        self, prompt: str, tools: list[dict[str, Any]]
    ) -> ToolCall | None: ...


class CloudflareToolProvider:
    """Non-streaming optional capability; it does not change IAiProvider."""

    name = "cloudflare"

    def __init__(
        self,
        account_id: str,
        api_token: str,
        model: str,
        timeout_seconds: float,
        max_completion_tokens: int | None = None,
    ) -> None:
        self.account_id = account_id.strip()
        self.api_token = api_token.strip()
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.max_completion_tokens = max_completion_tokens

    @property
    def configured(self) -> bool:
        return bool(self.account_id and self.api_token)

    async def generate_tool_call(
        self, prompt: str, tools: list[dict[str, Any]]
    ) -> ToolCall | None:
        if not self.configured:
            raise AiProviderError("Cloudflare Workers AI chưa được cấu hình")
        body: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Bạn là bộ định tuyến công cụ an toàn của WorkMind. "
                        "Chỉ gọi đúng một công cụ trong danh sách nếu cần; không tự thực hiện thay đổi. "
                        "Không được bịa ngày tháng, tên phòng ban, tên nhân viên hoặc mã định danh. "
                        "Nếu người dùng không nêu khoảng thời gian thì để date_from và date_to là null. "
                        "Nếu người dùng nói phòng tôi hoặc phòng mình thì không điền department_name."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "tools": tools,
            "tool_choice": "auto",
            "stream": False,
            "temperature": 0.0,
            "chat_template_kwargs": {"enable_thinking": False},
        }
        if self.max_completion_tokens is not None:
            body["max_completion_tokens"] = self.max_completion_tokens
        url = (
            "https://api.cloudflare.com/client/v4/accounts/"
            f"{self.account_id}/ai/v1/chat/completions"
        )
        timeout = httpx.Timeout(self.timeout_seconds)
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    url,
                    headers={
                        "Authorization": f"Bearer {self.api_token}",
                        "Content-Type": "application/json",
                    },
                    json=body,
                )
            if response.status_code >= 400:
                raise AiProviderError(
                    f"Nhà cung cấp AI trả về HTTP {response.status_code}",
                    retryable=response.status_code in _HttpProvider.RETRYABLE_STATUS_CODES,
                    status_code=response.status_code,
                )
            payload = response.json()
        except AiProviderError:
            raise
        except (httpx.HTTPError, TimeoutError, json.JSONDecodeError) as error:
            raise AiProviderError("Không thể kết nối tới trợ lý AI", retryable=True) from error

        choices = payload.get("choices") or []
        message = (choices[0] or {}).get("message") if choices else None
        tool_calls = (message or {}).get("tool_calls") or []
        if not tool_calls:
            return None
        function = (tool_calls[0] or {}).get("function") or {}
        name = function.get("name")
        raw_arguments = function.get("arguments") or "{}"
        if not isinstance(name, str):
            return None
        try:
            arguments = json.loads(raw_arguments) if isinstance(raw_arguments, str) else raw_arguments
        except json.JSONDecodeError as error:
            raise AiProviderError("Phản hồi gọi công cụ từ trợ lý AI không hợp lệ") from error
        if not isinstance(arguments, dict):
            raise AiProviderError("Tham số gọi công cụ từ trợ lý AI không hợp lệ")
        return ToolCall(name=name, arguments=arguments)


__all__ = ["CloudflareToolProvider", "IAiToolProvider"]
