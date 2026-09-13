from app.ai.tool_provider import CloudflareToolProvider
from app.core.config import Settings


class AiToolProviderFactory:
    """Optional function-calling capability, separate from streaming chat."""

    def __init__(self, settings: Settings) -> None:
        self.provider = CloudflareToolProvider(
            settings.cloudflare_account_id,
            settings.cloudflare_api_token,
            settings.ai_model,
            settings.ai_timeout_seconds,
            settings.ai_tool_max_completion_tokens,
        )

    async def generate_tool_call(self, prompt: str, tools: list[dict[str, object]]):
        if not self.provider.configured:
            return None
        return await self.provider.generate_tool_call(prompt, tools)


__all__ = ["AiToolProviderFactory"]
