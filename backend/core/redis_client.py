"""Redis client — used for token blacklist, rate limiting, caching."""

import redis.asyncio as aioredis

from core.config import get_settings

settings = get_settings()

redis = aioredis.from_url(
    f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}",
    decode_responses=True,
)
