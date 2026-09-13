from collections.abc import AsyncIterator
from typing import Protocol

JSON_OBJECT_MODE_MARKER = "[[WORKMIND_JSON_OBJECT_MODE]]"
AI_SUMMARY_MODE_MARKER = "[[WORKMIND_AI_SUMMARY_MODE]]"


class IAiProvider(Protocol):
    """Small provider contract so adapters are interchangeable."""

    name: str
    configured: bool

    def generate_insight_stream(self, prompt: str) -> AsyncIterator[str]: ...
