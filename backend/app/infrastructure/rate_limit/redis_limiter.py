from datetime import datetime
from typing import Any

from app.core.time import UTC, BusinessClock
from app.infrastructure.rate_limit.interface import RateLimitResult

SLIDING_WINDOW_SCRIPT = """
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
local bucket = math.floor(now / window)
local elapsed = now - (bucket * window)
local current_field = tostring(bucket)
local previous_field = tostring(bucket - 1)
local current = tonumber(redis.call('HGET', KEYS[1], current_field) or '0')
local previous = tonumber(redis.call('HGET', KEYS[1], previous_field) or '0')
local previous_weight = (window - elapsed) / window
local weighted_count = current + (previous * previous_weight)
local allowed = 0
if weighted_count < limit then
  current = current + 1
  redis.call('HSET', KEYS[1], current_field, current)
  allowed = 1
end
redis.call('HDEL', KEYS[1], tostring(bucket - 2))
redis.call('PEXPIRE', KEYS[1], window * 2)
local remaining = math.max(0, math.floor(limit - weighted_count - (allowed * 1)))
local reset_at = (bucket + 1) * window
local retry = 0
if allowed == 0 then
  retry = math.max(1, math.ceil((reset_at - now) / 1000))
end
return {allowed, remaining, reset_at, retry}
"""


class RedisRateLimiter:
    def __init__(
        self,
        redis_url: str,
        clock: BusinessClock | None = None,
        client: Any | None = None,
    ) -> None:
        self._owns_client = client is None
        if client is None:
            try:
                from redis.asyncio import Redis
            except ImportError as error:
                raise RuntimeError("Redis client chưa được cài đặt") from error
            client = Redis.from_url(redis_url, decode_responses=False)
        self.client = client
        self.clock = clock or BusinessClock()

    async def check(self, key: str, limit: int, window_seconds: int) -> RateLimitResult:
        now = getattr(self, "clock", None)
        if now is None:
            now = BusinessClock()
        current_time = now.now()
        now_ms = int(current_time.timestamp() * 1000)
        window_ms = window_seconds * 1000
        result = await self.client.eval(
            SLIDING_WINDOW_SCRIPT,
            1,
            key,
            now_ms,
            window_ms,
            limit,
        )
        if len(result) == 3:  # compatibility với adapter fake cũ trong giai đoạn chuyển đổi
            allowed, used, retry_after = result
            remaining = max(0, limit - int(used))
            reset_at_ms = now_ms + (int(retry_after) * 1000)
        else:
            allowed, remaining, reset_at_ms, retry_after = result
        allowed_bool = bool(int(allowed))
        retry = max(0, int(retry_after))
        reset_at = datetime.fromtimestamp(int(reset_at_ms) / 1000, UTC)
        return RateLimitResult(
            allowed=allowed_bool,
            limit=limit,
            remaining=max(0, int(remaining)),
            retry_after_seconds=0 if allowed_bool else max(1, retry),
            reset_at=reset_at,
        )

    async def aclose(self) -> None:
        if self._owns_client:
            await self.client.aclose()
