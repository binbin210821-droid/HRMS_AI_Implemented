from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any, ClassVar

import httpx

from app.ai.base import AI_SUMMARY_MODE_MARKER, JSON_OBJECT_MODE_MARKER

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _ParsedSseChunk:
    text: str = ""
    reasoning: str = ""
    finish_reason: str | None = None


class AiProviderError(RuntimeError):
    """A provider failed without exposing credentials or provider internals."""

    def __init__(
        self,
        message: str,
        *,
        retryable: bool = False,
        status_code: int | None = None,
        error_type: str = "provider_error",
    ) -> None:
        super().__init__(message)
        self.retryable = retryable
        self.status_code = status_code
        self.error_type = error_type


class _HttpProvider:
    RETRYABLE_STATUS_CODES: ClassVar[set[int]] = {408, 429, 500, 502, 503, 504}
    MIN_VISIBLE_CONTENT_AFTER_LENGTH: ClassVar[int] = 32

    def __init__(
        self,
        api_key: str,
        model: str,
        timeout_seconds: float,
        name: str,
        max_completion_tokens: int | None = None,
        summary_max_completion_tokens: int | None = None,
        connect_timeout_seconds: float | None = None,
        first_token_timeout_seconds: float | None = None,
        idle_timeout_seconds: float | None = None,
        enable_thinking: bool = True,
        debug_stream: bool = False,
    ) -> None:
        self.api_key = api_key.strip()
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.name = name
        self.max_completion_tokens = max_completion_tokens
        self.summary_max_completion_tokens = summary_max_completion_tokens
        self.connect_timeout_seconds = max(
            0.1, connect_timeout_seconds or timeout_seconds
        )
        self.first_token_timeout_seconds = max(
            0.1, first_token_timeout_seconds or timeout_seconds
        )
        self.idle_timeout_seconds = max(0.1, idle_timeout_seconds or timeout_seconds)
        self.enable_thinking = enable_thinking
        self.debug_stream = debug_stream

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    @staticmethod
    def _text_from_payload(payload: dict[str, Any]) -> _ParsedSseChunk:
        choices = payload.get("choices") or []
        if choices:
            choice = choices[0] or {}
            delta = choice.get("delta") or {}
            content = str(delta.get("content") or choice.get("text") or "")
            reasoning = str(
                delta.get("reasoning_content")
                or delta.get("reasoning")
                or choice.get("reasoning_content")
                or ""
            )
            return _ParsedSseChunk(
                text=content,
                reasoning=reasoning,
                finish_reason=choice.get("finish_reason"),
            )
        candidates = payload.get("candidates") or []
        if candidates:
            parts = ((candidates[0] or {}).get("content") or {}).get("parts") or []
            return _ParsedSseChunk(
                text="".join(str(part.get("text") or "") for part in parts),
                finish_reason=(candidates[0] or {}).get("finishReason"),
            )
        return _ParsedSseChunk()

    @classmethod
    def _parse_sse_payload(cls, line: str) -> _ParsedSseChunk:
        if not line.startswith("data:"):
            return _ParsedSseChunk()
        raw_data = line[5:].strip()
        if not raw_data or raw_data == "[DONE]":
            return _ParsedSseChunk()
        try:
            payload = json.loads(raw_data)
        except json.JSONDecodeError as error:
            raise AiProviderError(
                "Phản hồi từ trợ lý AI không hợp lệ", error_type="malformed_sse"
            ) from error
        return cls._text_from_payload(payload)

    async def _stream_openai_compatible(
        self, url: str, headers: dict[str, str], prompt: str
    ) -> AsyncIterator[str]:
        summary_output = prompt.startswith(AI_SUMMARY_MODE_MARKER)
        request_prompt = (
            prompt[len(AI_SUMMARY_MODE_MARKER) :].lstrip()
            if summary_output
            else prompt
        )
        structured_output = request_prompt.startswith(JSON_OBJECT_MODE_MARKER)
        if structured_output:
            request_prompt = request_prompt[len(JSON_OBJECT_MODE_MARKER) :].lstrip()
        body = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "Bạn là trợ lý phân tích hiệu suất, chỉ trả lời bằng tiếng Việt dễ hiểu.",
                },
                {"role": "user", "content": request_prompt},
            ],
            "stream": True,
            "temperature": 0.2,
        }
        max_completion_tokens = (
            self.summary_max_completion_tokens
            if summary_output and self.summary_max_completion_tokens is not None
            else self.max_completion_tokens
        )
        if max_completion_tokens is not None:
            body["max_completion_tokens"] = max_completion_tokens
        if structured_output:
            body["response_format"] = {"type": "json_object"}
        if self.name == "cloudflare" and (
            not self.enable_thinking or structured_output or summary_output
        ):
            body["chat_template_kwargs"] = {"enable_thinking": False}
        timeout = httpx.Timeout(
            self.timeout_seconds,
            connect=self.connect_timeout_seconds,
        )
        started_at = time.perf_counter()
        first_chunk_at: float | None = None
        chunk_count = 0
        output_chars = 0
        reasoning_chars = 0
        finish_reason: str | None = None
        stream_error_type: str | None = None
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream("POST", url, headers=headers, json=body) as response:
                    if response.status_code >= 400:
                        raise AiProviderError(
                            f"Nhà cung cấp AI trả về HTTP {response.status_code}",
                            retryable=response.status_code in self.RETRYABLE_STATUS_CODES,
                            status_code=response.status_code,
                            error_type="http_error",
                        )
                    line_iterator = response.aiter_lines().__aiter__()
                    while True:
                        wait_timeout = (
                            self.first_token_timeout_seconds
                            if first_chunk_at is None
                            else self.idle_timeout_seconds
                        )
                        try:
                            line = await asyncio.wait_for(
                                line_iterator.__anext__(), timeout=wait_timeout
                            )
                        except StopAsyncIteration:
                            break
                        if self.debug_stream and line.startswith("data:"):
                            logger.debug(
                                "ai_provider_stream_chunk provider=%s raw=%s",
                                self.name,
                                line[5:].strip(),
                            )
                        parsed = self._parse_sse_payload(line)
                        if parsed.reasoning:
                            reasoning_chars += len(parsed.reasoning)
                        if parsed.finish_reason:
                            finish_reason = parsed.finish_reason
                        if parsed.text:
                            chunk_count += 1
                            output_chars += len(parsed.text)
                            if first_chunk_at is None:
                                first_chunk_at = time.perf_counter()
                            yield parsed.text
            if (
                finish_reason == "length"
                and output_chars <= self.MIN_VISIBLE_CONTENT_AFTER_LENGTH
            ):
                raise AiProviderError(
                    "Nhà cung cấp AI bị cắt khi đang suy luận trước khi tạo đủ câu trả lời",
                    retryable=True,
                    error_type="reasoning_truncated",
                )
            if output_chars == 0:
                raise AiProviderError(
                    "Nhà cung cấp AI trả về stream rỗng",
                    retryable=True,
                    error_type="empty_output",
                )
        except AiProviderError as error:
            stream_error_type = error.error_type
            raise
        except (httpx.TimeoutException, TimeoutError) as error:
            stream_error_type = "timeout"
            raise AiProviderError(
                "Không thể kết nối tới trợ lý AI",
                retryable=True,
                error_type="timeout",
            ) from error
        except httpx.HTTPError as error:
            stream_error_type = "transport_error"
            raise AiProviderError(
                "Không thể kết nối tới trợ lý AI",
                retryable=True,
                error_type="transport_error",
            ) from error
        finally:
            log_method = logger.warning if stream_error_type else logger.info
            log_method(
                "ai_provider_stream %s",
                json.dumps(
                    {
                        "provider": self.name,
                        "model": self.model,
                        "duration_ms": round((time.perf_counter() - started_at) * 1000),
                        "first_chunk_ms": (
                            round((first_chunk_at - started_at) * 1000)
                            if first_chunk_at is not None
                            else None
                        ),
                        "chunk_count": chunk_count,
                        "output_chars": output_chars,
                        "reasoning_chars": reasoning_chars,
                        "finish_reason": finish_reason,
                        "error_type": stream_error_type,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                ),
            )


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
                        raise AiProviderError(
                            f"Nhà cung cấp AI trả về HTTP {response.status_code}",
                            retryable=response.status_code in _HttpProvider.RETRYABLE_STATUS_CODES,
                            status_code=response.status_code,
                            error_type="http_error",
                        )
                    async for line in response.aiter_lines():
                        parsed = self._parse_sse_payload(line)
                        if parsed.text:
                            yield parsed.text
        except AiProviderError:
            raise
        except (httpx.TimeoutException, TimeoutError) as error:
            raise AiProviderError(
                "Không thể kết nối tới trợ lý AI", retryable=True, error_type="timeout"
            ) from error
        except httpx.HTTPError as error:
            raise AiProviderError(
                "Không thể kết nối tới trợ lý AI",
                retryable=True,
                error_type="transport_error",
            ) from error


class GroqProvider(_HttpProvider):
    def __init__(
        self,
        api_key: str,
        model: str,
        timeout_seconds: float,
        max_completion_tokens: int | None = None,
        summary_max_completion_tokens: int | None = None,
        connect_timeout_seconds: float | None = None,
        first_token_timeout_seconds: float | None = None,
        idle_timeout_seconds: float | None = None,
    ) -> None:
        super().__init__(
            api_key,
            model,
            timeout_seconds,
            "groq",
            max_completion_tokens,
            summary_max_completion_tokens,
            connect_timeout_seconds,
            first_token_timeout_seconds,
            idle_timeout_seconds,
        )

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
    def __init__(
        self,
        api_key: str,
        model: str,
        timeout_seconds: float,
        max_completion_tokens: int | None = None,
        summary_max_completion_tokens: int | None = None,
        connect_timeout_seconds: float | None = None,
        first_token_timeout_seconds: float | None = None,
        idle_timeout_seconds: float | None = None,
    ) -> None:
        super().__init__(
            api_key,
            model,
            timeout_seconds,
            "openrouter",
            max_completion_tokens,
            summary_max_completion_tokens,
            connect_timeout_seconds,
            first_token_timeout_seconds,
            idle_timeout_seconds,
        )

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


class CloudflareProvider(_HttpProvider):
    """Cloudflare Workers AI through its OpenAI-compatible chat endpoint."""

    def __init__(
        self,
        account_id: str,
        api_token: str,
        model: str,
        timeout_seconds: float,
        max_completion_tokens: int | None = None,
        summary_max_completion_tokens: int | None = None,
        connect_timeout_seconds: float | None = None,
        first_token_timeout_seconds: float | None = None,
        idle_timeout_seconds: float | None = None,
        enable_thinking: bool = True,
        debug_stream: bool = False,
    ) -> None:
        super().__init__(
            api_token,
            model,
            timeout_seconds,
            "cloudflare",
            max_completion_tokens,
            summary_max_completion_tokens,
            connect_timeout_seconds,
            first_token_timeout_seconds,
            idle_timeout_seconds,
            enable_thinking,
            debug_stream,
        )
        self.account_id = account_id.strip()

    @property
    def configured(self) -> bool:
        return bool(self.account_id and self.api_key)

    async def generate_insight_stream(self, prompt: str) -> AsyncIterator[str]:
        if not self.configured:
            raise AiProviderError("Cloudflare Workers AI chưa được cấu hình")
        url = (
            "https://api.cloudflare.com/client/v4/accounts/"
            f"{self.account_id}/ai/v1/chat/completions"
        )
        async for text in self._stream_openai_compatible(
            url,
            {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            prompt,
        ):
            yield text
