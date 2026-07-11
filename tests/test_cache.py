from backend.app.cache import CacheService


def test_cache_get_or_set(test_env):
    from backend.app.redis_client import get_redis

    get_redis()
    cache = CacheService(prefix="test_cache")
    calls = {"count": 0}

    def factory():
        calls["count"] += 1
        return {"value": 42}

    first = cache.get_or_set("ns", "key1", factory, ttl=60)
    second = cache.get_or_set("ns", "key1", factory, ttl=60)

    assert first == {"value": 42}
    assert second == {"value": 42}
    assert calls["count"] == 1


def test_cache_delete(test_env):
    from backend.app.redis_client import get_redis

    get_redis()
    cache = CacheService(prefix="test_cache2")
    cache.set("ns", "delkey", {"a": 1}, ttl=60)
    assert cache.get("ns", "delkey") == {"a": 1}
    cache.delete("ns", "delkey")
    assert cache.get("ns", "delkey") is None


def test_cache_hash_key():
    key1 = CacheService.hash_key("hello", "world")
    key2 = CacheService.hash_key("hello", "world")
    key3 = CacheService.hash_key("hello", "other")
    assert key1 == key2
    assert key1 != key3
