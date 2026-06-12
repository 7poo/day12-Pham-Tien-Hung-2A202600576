"""Sliding-window rate limiter backed by Redis when available."""
import time
from collections import defaultdict, deque

from fastapi import HTTPException

from app.config import settings
from app.storage import redis_client

_windows: dict[str, deque] = defaultdict(deque)


def check_rate_limit(key: str) -> None:
    now = time.time()
    cutoff = now - 60

    if redis_client is not None:
        redis_key = f"rate:{key}"
        allowed = redis_client.eval(
            """
            redis.call('ZREMRANGEBYSCORE', KEYS[1], 0, ARGV[1])
            if redis.call('ZCARD', KEYS[1]) >= tonumber(ARGV[3]) then
                return 0
            end
            redis.call('ZADD', KEYS[1], ARGV[2], ARGV[4])
            redis.call('EXPIRE', KEYS[1], 60)
            return 1
            """,
            1,
            redis_key,
            cutoff,
            now,
            settings.rate_limit_per_minute,
            time.time_ns(),
        )
        if not allowed:
            raise HTTPException(429, "Rate limit exceeded", headers={"Retry-After": "60"})
        return

    window = _windows[key]
    while window and window[0] < cutoff:
        window.popleft()
    if len(window) >= settings.rate_limit_per_minute:
        raise HTTPException(429, "Rate limit exceeded", headers={"Retry-After": "60"})
    window.append(now)
