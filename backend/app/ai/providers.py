from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx


class AiProviderError(RuntimeError):
    """A provider failed without exposing credentials or provider internals."""


class _HttpProvider:
    def __init__(self, api_key: str, model: str, timeout_seconds: float, name: str) -> None:
        self.api_key = api_key.strip()
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.name = name

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    @staticmethod
    def _text_from_payload(payload: dict[str, Any]) -> str:
        choices = payload.get("choices") or []
        if choices:
            choice = choices[0] or {}
            delta = choice.get("delta") or {}
            return str(delta.get("content") or choice.get("text") or "")
        candidates = payload.get("candidates") or []
        if candidates:
            parts = ((candidates[0] or {}).get("content") or {}).get("parts") or []
            return "".join(str(part.get("text") or "") for part in parts)
        return ""

    @classmethod
    def _parse_sse_payload(cls, line: str) -> str:
        if not line.startswith("data:"):
            return ""
        raw_data = line[5:].strip()
        if not raw_data or raw_data == "[DONE]":
            return ""
        try:
            payload = json.loads(raw_data)
        except json.JSONDecodeError as error:
            raise AiProviderError("Phản hồi từ trợ lý AI không hợp lệ") from error
        return cls._text_from_payload(payload)

    async def _stream_openai_compatible(
        self, url: str, headers: dict[str, str], prompt: str
    ) -> AsyncIterator[str]:
        body = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "Bạn là trợ lý phân tích hiệu suất, chỉ trả lời bằng tiếng Việt dễ hiểu.",
                },
                {"role": "user", "content": prompt},
            ],
            "stream": True,
            "temperature": 0.2,
        }
        timeout = httpx.Timeout(self.timeout_seconds)
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream("POST", url, headers=headers, json=body) as response:
                    if response.status_code >= 400:
                        raise AiProviderError(f"Nhà cung cấp AI trả về HTTP {response.status_code}")
                    async for line in response.aiter_lines():
                        text = self._parse_sse_payload(line)
                        if text:
                            yield text
        except AiProviderError:
            raise
        except (httpx.HTTPError, TimeoutError) as error:
            raise AiProviderError("Không thể kết nối tới trợ lý AI") from error


class GeminiProvider(_HttpProvider):
    def __init__(self, api_key: str, model: str, timeout_seconds: float) -> None:
        super().__init__(api_key, model, timeout_seconds, "gemini")

    async def generate_insight_stream(self, prompt: str) -> AsyncIterator[str]:
        if not self.configured:
            raise AiProviderError("Gemini chưa được cấu hình")
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:streamGenerateContent?alt=sse&key={self.api_key}"
        )
        body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.2},
        }
        timeout = httpx.Timeout(self.timeout_seconds)
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream("POST", url, json=body) as response:
                    if response.status_code >= 400:
                        raise AiProviderError(f"Nhà cung cấp AI trả về HTTP {response.status_code}")
                    async for line in response.aiter_lines():
                        text = self._parse_sse_payload(line)
                        if text:
                            yield text
        except AiProviderError:
            raise
        except (httpx.HTTPError, TimeoutError) as error:
            raise AiProviderError("Không thể kết nối tới trợ lý AI") from error


class GroqProvider(_HttpProvider):
    def __init__(self, api_key: str, model: str, timeout_seconds: float) -> None:
        super().__init__(api_key, model, timeout_seconds, "groq")

    async def generate_insight_stream(self, prompt: str) -> AsyncIterator[str]:
        if not self.configured:
            raise AiProviderError("Groq chưa được cấu hình")
        async for text in self._stream_openai_compatible(
            "https://api.groq.com/openai/v1/chat/completions",
            {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            prompt,
        ):
            yield text


class OpenRouterProvider(_HttpProvider):
    def __init__(self, api_key: str, model: str, timeout_seconds: float) -> None:
        super().__init__(api_key, model, timeout_seconds, "openrouter")

    async def generate_insight_stream(self, prompt: str) -> AsyncIterator[str]:
        if not self.configured:
            raise AiProviderError("OpenRouter chưa được cấu hình")
        async for text in self._stream_openai_compatible(
            "https://openrouter.ai/api/v1/chat/completions",
            {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "http://localhost:5173",
                "X-Title": "WorkMind",
            },
            prompt,
        ):
            yield text
