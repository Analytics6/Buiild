import json
import logging
import threading
import time
from typing import Any, Optional, Set

from .config import get_settings

logger = logging.getLogger(__name__)


class InMemoryStore:
    """Thread-safe in-memory fallback when Redis is unavailable."""

    def __init__(self) -> None:
        self._data: dict[str, tuple[str, Optional[float]]] = {}
        self._lock = threading.RLock()

    def get(self, key: str) -> Optional[str]:
        with self._lock:
            entry = self._data.get(key)
            if not entry:
                return None
            value, expires_at = entry
            if expires_at is not None and time.time() > expires_at:
                del self._data[key]
                return None
            return value

    def set(self, key: str, value: str, ex: Optional[int] = None) -> bool:
        with self._lock:
            expires_at = time.time() + ex if ex else None
            self._data[key] = (value, expires_at)
            return True

    def delete(self, *keys: str) -> int:
        with self._lock:
            removed = 0
            for key in keys:
                if key in self._data:
                    del self._data[key]
                    removed += 1
            return removed

    def exists(self, key: str) -> bool:
        return self.get(key) is not None

    def sadd(self, key: str, *values: str) -> int:
        with self._lock:
            entry = self._data.get(key)
            raw = entry[0] if entry and (entry[1] is None or time.time() <= entry[1]) else None
            members = set(json.loads(raw)) if raw else set()
            before = len(members)
            members.update(values)
            self._data[key] = (json.dumps(list(members)), entry[1] if entry else None)
            return len(members) - before

    def srem(self, key: str, *values: str) -> int:
        with self._lock:
            entry = self._data.get(key)
            raw = entry[0] if entry and (entry[1] is None or time.time() <= entry[1]) else None
            if not raw:
                return 0
            members = set(json.loads(raw))
            before = len(members)
            for value in values:
                members.discard(value)
            self._data[key] = (json.dumps(list(members)), entry[1] if entry else None)
            return before - len(members)

    def smembers(self, key: str) -> Set[str]:
        raw = self.get(key)
        if not raw:
            return set()
        return set(json.loads(raw))

    def expire(self, key: str, seconds: int) -> bool:
        with self._lock:
            entry = self._data.get(key)
            if not entry:
                return False
            value, _ = entry
            self._data[key] = (value, time.time() + seconds)
            return True

    def ping(self) -> bool:
        return True


class RedisClient:
    """Redis wrapper with graceful in-memory fallback."""

    def __init__(self) -> None:
        self._settings = get_settings()
        self._client: Any = None
        self._fallback = InMemoryStore()
        self._using_fallback = False
        self._connect()

    def _connect(self) -> None:
        if not self._settings.redis_enabled:
            self._using_fallback = True
            logger.info("Redis disabled via REDIS_ENABLED=false; using in-memory store")
            return
        try:
            import redis

            self._client = redis.from_url(
                self._settings.redis_url,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
            )
            self._client.ping()
            self._using_fallback = False
            logger.info("Connected to Redis at %s", self._settings.redis_url)
        except Exception as exc:
            self._client = None
            self._using_fallback = True
            logger.warning("Redis unavailable (%s); using in-memory fallback", exc)

    @property
    def is_redis_available(self) -> bool:
        return not self._using_fallback and self._client is not None

    @property
    def backend(self) -> str:
        return "redis" if self.is_redis_available else "memory"

    def _store(self) -> Any:
        if self.is_redis_available:
            return self._client
        return self._fallback

    def get(self, key: str) -> Optional[str]:
        try:
            return self._store().get(key)
        except Exception as exc:
            logger.warning("Redis get failed for %s: %s", key, exc)
            return self._fallback.get(key)

    def set(self, key: str, value: str, ex: Optional[int] = None) -> bool:
        try:
            return bool(self._store().set(key, value, ex=ex))
        except Exception as exc:
            logger.warning("Redis set failed for %s: %s", key, exc)
            return self._fallback.set(key, value, ex=ex)

    def delete(self, *keys: str) -> int:
        try:
            return int(self._store().delete(*keys))
        except Exception as exc:
            logger.warning("Redis delete failed: %s", exc)
            return self._fallback.delete(*keys)

    def exists(self, key: str) -> bool:
        try:
            store = self._store()
            if hasattr(store, "exists"):
                return bool(store.exists(key))
            return store.get(key) is not None
        except Exception:
            return self._fallback.exists(key)

    def sadd(self, key: str, *values: str) -> int:
        try:
            return int(self._store().sadd(key, *values))
        except Exception as exc:
            logger.warning("Redis sadd failed for %s: %s", key, exc)
            return self._fallback.sadd(key, *values)

    def srem(self, key: str, *values: str) -> int:
        try:
            return int(self._store().srem(key, *values))
        except Exception as exc:
            logger.warning("Redis srem failed for %s: %s", key, exc)
            return self._fallback.srem(key, *values)

    def smembers(self, key: str) -> Set[str]:
        try:
            members = self._store().smembers(key)
            return set(members) if members else set()
        except Exception as exc:
            logger.warning("Redis smembers failed for %s: %s", key, exc)
            return self._fallback.smembers(key)

    def expire(self, key: str, seconds: int) -> bool:
        try:
            return bool(self._store().expire(key, seconds))
        except Exception as exc:
            logger.warning("Redis expire failed for %s: %s", key, exc)
            return self._fallback.expire(key, seconds)

    def ping(self) -> bool:
        try:
            if self.is_redis_available:
                return bool(self._client.ping())
            return self._fallback.ping()
        except Exception:
            return False


_redis_client: Optional[RedisClient] = None


def get_redis() -> RedisClient:
    global _redis_client
    if _redis_client is None:
        _redis_client = RedisClient()
    return _redis_client
