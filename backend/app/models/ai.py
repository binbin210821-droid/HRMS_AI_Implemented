from typing import Literal

from pydantic import BaseModel, Field


class AIChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    mode: Literal["chat", "summary"] = "chat"
    refresh: bool = False
    conversation_id: str | None = Field(default=None, min_length=1, max_length=64)
