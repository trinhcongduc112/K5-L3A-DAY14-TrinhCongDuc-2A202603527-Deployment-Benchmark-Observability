import hashlib
import uuid

from fastapi import HTTPException

from app.config import settings
from app.redis_client import get_redis_client

WINDOW_SECONDS = 60

# Redis serializes this script across all workers and provides a shared clock.
SLIDING_WINDOW = """
local time = redis.call('TIME')
local now = tonumber(time[1]) * 1000000 + tonumber(time[2])
local window = tonumber(ARGV[1]) * 1000000
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', now - window)
if redis.call('ZCARD', KEYS[1]) >= tonumber(ARGV[2]) then
    local oldest = redis.call('ZRANGE', KEYS[1], 0, 0, 'WITHSCORES')
    return math.max(1, math.ceil((tonumber(oldest[2]) + window - now) / 1000000))
end
redis.call('ZADD', KEYS[1], now, ARGV[3])
redis.call('EXPIRE', KEYS[1], tonumber(ARGV[1]) + 1)
return 0
"""


def check_rate_limit(api_key: str) -> None:
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    retry_after = get_redis_client().eval(
        SLIDING_WINDOW,
        1,
        f"ratelimit:{key_hash}",
        WINDOW_SECONDS,
        max(1, settings.rate_limit_per_minute),
        uuid.uuid4().hex,
    )
    if retry_after:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(retry_after)},
        )
