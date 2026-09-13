import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.core.time import UTC, BusinessClock


@dataclass(frozen=True)
class RateLimitResult:
    """Kết quả chuẩn của một lần kiểm tra rate limit.

    ``limit`` và ``retry_after_seconds`` được giữ để tương thích với header HTTP
    hiện tại; contract mới chỉ yêu cầu ba trường cốt lõi còn lại.
    """

    allowed: bool
    remaining: int
    reset_at: datetime
    limit: int = 0
    retry_after_seconds: int = 0


# Tên cũ được giữ cho các adapter/client hiện tại trong giai đoạn chuyển đổi.
RateLimitDecision = RateLimitResult


class RateLimiter(Protocol):
    async def check(self, key: str, limit: int, window_seconds: int) -> RateLimitResult:
        ...


class InMemoryRateLimiter:
    """Fallback dùng cho test/local một worker; production phải dùng Redis."""

    def __init__(self, clock: BusinessClock | None = None) -> None:
        self._events: dict[str, list[float]] = {}
        self._lock = asyncio.Lock()
        self.clock = clock or BusinessClock()

    async def check(self, key: str, limit: int, window_seconds: int) -> RateLimitResult:
        async with self._lock:
            now = self.clock.now()
            now_timestamp = now.timestamp()
            window_start = now_timestamp - window_seconds
            events = [
                timestamp
                for timestamp in self._events.get(key, [])
                if timestamp > window_start
            ]
            allowed = len(events) < limit
            if allowed:
                events.append(now_timestamp)
            self._events[key] = events
            retry_after = 0 if allowed else max(1, int(events[0] + window_seconds - now_timestamp))
            reset_timestamp = now_timestamp + (retry_after or window_seconds)
            return RateLimitResult(
                allowed=allowed,
                limit=limit,
                remaining=max(0, limit - len(events)),
                retry_after_seconds=retry_after,
                reset_at=datetime.fromtimestamp(reset_timestamp, UTC),
            )


class UnavailableRateLimiter:
    async def check(self, key: str, limit: int, window_seconds: int) -> RateLimitResult:
        del key, limit, window_seconds
        raise RuntimeError("Rate limiter backend chưa sẵn sàng")
