"""Smoke test Redis-backed rate limiting and idempotency across adapter instances."""

import argparse
import asyncio
import sys
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings
from app.infrastructure.idempotency import (
    RedisIdempotencyStore,
    StoredResponse,
)
from app.infrastructure.rate_limit import RedisRateLimiter


async def run(redis_url: str) -> None:
    from redis.asyncio import Redis

    redis = Redis.from_url(redis_url, decode_responses=False)
    limiter_a = RedisRateLimiter(redis_url)
    limiter_b = RedisRateLimiter(redis_url)
    store_a = RedisIdempotencyStore(redis_url)
    store_b = RedisIdempotencyStore(redis_url)
    rate_key = f"smoke:rate:{uuid4().hex}"
    idempotency_key = f"smoke:idempotency:{uuid4().hex}"
    connected = False

    try:
        await redis.ping()
        connected = True

        first = await limiter_a.check(rate_key, limit=1, window_seconds=60)
        second = await limiter_b.check(rate_key, limit=1, window_seconds=60)
        assert first.allowed is True
        assert second.allowed is False

        concurrent_key = f"{rate_key}:concurrent"
        concurrent_results = await asyncio.gather(
            *(limiter_a.check(concurrent_key, limit=5, window_seconds=60) for _ in range(20))
        )
        assert sum(result.allowed for result in concurrent_results) == 5

        idempotency_claims = await asyncio.gather(
            *(
                store_a.claim(idempotency_key, "payload-hash", 30)
                if index % 2 == 0
                else store_b.claim(idempotency_key, "payload-hash", 30)
                for index in range(20)
            )
        )
        assert sum(claim.state == "claimed" for claim in idempotency_claims) == 1
        assert sum(claim.state == "in_progress" for claim in idempotency_claims) == 19
        first_claim = next(claim for claim in idempotency_claims if claim.state == "claimed")
        assert first_claim.owner is not None

        response = StoredResponse(
            status_code=201,
            headers={"content-type": "application/json"},
            body=b'{"created":true}',
        )
        await store_a.complete(
            idempotency_key,
            first_claim.owner,
            "payload-hash",
            response,
            60,
        )
        replay = await store_b.claim(idempotency_key, "payload-hash", 60)
        assert replay.state == "replay"
        assert replay.response == response
    finally:
        if connected:
            await redis.delete(rate_key, f"{rate_key}:concurrent", idempotency_key)
        await redis.aclose()
        await limiter_a.client.aclose()
        await limiter_b.client.aclose()
        await store_a.client.aclose()
        await store_b.client.aclose()

    print("Redis smoke passed: multi-instance rate-limit atomicity and idempotency replay")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--redis-url", default=get_settings().redis_url)
    args = parser.parse_args()
    try:
        asyncio.run(run(args.redis_url))
    except Exception as error:
        raise SystemExit(f"Redis smoke failed: {error}") from error


if __name__ == "__main__":
    main()
