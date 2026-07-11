import functools
import hashlib
import json
import logging
import time
from typing import Any, Callable, Optional, TypeVar

from .config import get_settings
from .redis_client import get_redis

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CacheService:
    """Cache-aside layer with TTL-based invalidation and Redis/memory fallback."""

    def __init__(self, prefix: str = "cache") -> None:
        self._redis = get_redis()
        self._settings = get_settings()
        self._prefix = prefix

    def _key(self, namespace: str, key: str) -> str:
        return f"{self._prefix}:{namespace}:{key}"

    def get(self, namespace: str, key: str) -> Optional[Any]:
        raw = self._redis.get(self._key(namespace, key))
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return raw

    def set(self, namespace: str, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        ttl = ttl or self._settings.cache_ttl_seconds
        payload = json.dumps(value) if not isinstance(value, str) else value
        return self._redis.set(self._key(namespace, key), payload, ex=ttl)

    def delete(self, namespace: str, key: str) -> None:
        self._redis.delete(self._key(namespace, key))

    def invalidate_namespace(self, namespace: str, keys: list[str]) -> None:
        if not keys:
            return
        self._redis.delete(*[self._key(namespace, key) for key in keys])

    def get_or_set(
        self,
        namespace: str,
        key: str,
        factory: Callable[[], T],
        ttl: Optional[int] = None,
    ) -> T:
        cached = self.get(namespace, key)
        if cached is not None:
            logger.debug("Cache hit: %s:%s", namespace, key)
            return cached
        logger.debug("Cache miss: %s:%s", namespace, key)
        value = factory()
        self.set(namespace, key, value, ttl=ttl)
        return value

    @staticmethod
    def hash_key(*parts: str) -> str:
        digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
        return digest[:32]


def cached(
    namespace: str,
    ttl: Optional[int] = None,
    key_builder: Optional[Callable[..., str]] = None,
):
    """Decorator for cache-aside pattern on pure functions."""

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            cache = get_cache()
            if key_builder:
                cache_key = key_builder(*args, **kwargs)
            else:
                cache_key = CacheService.hash_key(func.__name__, str(args), str(sorted(kwargs.items())))
            return cache.get_or_set(namespace, cache_key, lambda: func(*args, **kwargs), ttl=ttl)

        return wrapper

    return decorator


class RateLimiter:
    """Simple sliding-window rate limiter per user."""

    def __init__(self, prefix: str = "ratelimit") -> None:
        self._redis = get_redis()
        self._settings = get_settings()
        self._prefix = prefix

    def _key(self, user_id: int, endpoint: str) -> str:
        return f"{self._prefix}:{user_id}:{endpoint}"

    def is_allowed(self, user_id: int, endpoint: str = "default") -> bool:
        if not self._settings.rate_limit_enabled:
            return True

        key = self._key(user_id, endpoint)
        now = int(time.time())
        window = self._settings.rate_limit_window_seconds
        bucket = f"{now // window}"

        count_key = f"{key}:{bucket}"
        raw = self._redis.get(count_key)
        count = int(raw) if raw else 0

        if count >= self._settings.rate_limit_requests:
            logger.warning("Rate limit exceeded for user %s on %s", user_id, endpoint)
            return False

        self._redis.set(count_key, str(count + 1), ex=window + 1)
        return True


_cache_service: Optional[CacheService] = None
_rate_limiter: Optional[RateLimiter] = None


def get_cache() -> CacheService:
    global _cache_service
    if _cache_service is None:
        _cache_service = CacheService()
    return _cache_service


def get_rate_limiter() -> RateLimiter:
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter
