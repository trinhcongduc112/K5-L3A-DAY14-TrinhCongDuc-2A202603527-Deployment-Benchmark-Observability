from functools import lru_cache

from fastapi import HTTPException
from redis import Redis, RedisError

from app.config import settings


@lru_cache(maxsize=1)
def get_redis_client() -> Redis:
    if not settings.redis_url:
        raise HTTPException(status_code=503, detail="Redis unavailable")
    try:
        return Redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
    except ValueError:
        raise HTTPException(status_code=503, detail="Redis unavailable") from None


def redis_healthy() -> bool:
    try:
        return bool(get_redis_client().ping())
    except (HTTPException, RedisError):
        return False


def close_redis() -> None:
    if get_redis_client.cache_info().currsize:
        get_redis_client().close()
        get_redis_client.cache_clear()
