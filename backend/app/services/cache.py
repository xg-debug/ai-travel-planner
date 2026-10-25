"""Simple cache for POI/search results with optional Redis support.

Uses an in-memory LRU dict by default. If REDIS_URL is configured and
redis-py is installed, it transparently upgrades to Redis with TTL.
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
from typing import Any, Dict, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

_redis_client: Any = None
_redis_available = False
_memory_cache: Dict[str, tuple[float, Any]] = {}
_memory_cache_lock = threading.RLock()
CACHE_TTL_SECONDS = 1800  # 30 minutes


def _redis_key(namespace: str, *parts: str) -> str:
    raw = "|".join([namespace, *parts])
    return f"travel_cache:{hashlib.sha256(raw.encode()).hexdigest()[:16]}"


def _try_init_redis() -> bool:
    global _redis_client, _redis_available
    if _redis_available:
        return True
    try:
        import redis
    except ImportError:
        return False
    try:
        _redis_client = redis.Redis.from_url(settings.REDIS_URL, socket_connect_timeout=2, decode_responses=True)
        _redis_client.ping()
        _redis_available = True
        logger.info("Redis cache connected")
        return True
    except Exception:
        logger.debug("Redis not available, using in-memory cache")
        return False


def _memory_get(key: str) -> Optional[Any]:
    with _memory_cache_lock:
        entry = _memory_cache.get(key)
        if not entry:
            return None
        expires_at, value = entry
        if time.monotonic() > expires_at:
            _memory_cache.pop(key, None)
            return None
        return value


def _memory_set(key: str, value: Any) -> None:
    with _memory_cache_lock:
        _memory_cache[key] = (time.monotonic() + CACHE_TTL_SECONDS, value)
        if len(_memory_cache) > 500:
            expired = [k for k, (exp, _) in _memory_cache.items() if time.monotonic() > exp]
            for k in expired:
                _memory_cache.pop(k, None)


def get_cache(key: str) -> Optional[Any]:
    if _try_init_redis():
        try:
            raw = _redis_client.get(key)
            return json.loads(raw) if raw else None
        except Exception:
            pass
    return _memory_get(key)


def set_cache(key: str, value: Any) -> None:
    if _try_init_redis():
        try:
            _redis_client.setex(key, CACHE_TTL_SECONDS, json.dumps(value, ensure_ascii=False, default=str))
            return
        except Exception:
            pass
    _memory_set(key, value)


def cache_key(*parts: str) -> str:
    return _redis_key("poi", *parts)
