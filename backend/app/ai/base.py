from collections.abc import AsyncIterator
from typing import Protocol


class IAiProvider(Protocol):
    """Small provider contract so adapters are interchangeable."""

    name: str
    configured: bool

    def generate_insight_stream(self, prompt: str) -> AsyncIterator[str]: ...
