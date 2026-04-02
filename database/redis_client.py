"""Redis client for hot cache access."""

import json
import os
from typing import Any, Optional

import redis.asyncio as aioredis

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

_client = None


def get_redis():
    global _client
    if _client is None:
        _client = aioredis.from_url(
            REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )
    return _client


async def cache_set(
    key: str,
    value: Any,
    ttl_seconds: int = 3600,
) -> None:
    try:
        await get_redis().setex(
            key,
            ttl_seconds,
            json.dumps(value),
        )
    except Exception:
        pass


async def cache_get(key: str) -> Optional[Any]:
    try:
        val = await get_redis().get(key)
        return json.loads(val) if val else None
    except Exception:
        return None


async def cache_delete(key: str) -> None:
    try:
        await get_redis().delete(key)
    except Exception:
        pass


async def ping_redis() -> bool:
    try:
        await get_redis().ping()
        return True
    except Exception:
        return False
