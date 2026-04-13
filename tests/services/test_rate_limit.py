"""Tests for the rate limit service."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from oscilla.services.cache import configure_caches
from oscilla.services.rate_limit import check_rate_limit
from oscilla.settings import settings


@pytest.fixture(autouse=True)
def setup_caches(monkeypatch: pytest.MonkeyPatch) -> None:
    """Configure caches with NoOpCache so unit tests never need Redis."""
    monkeypatch.setattr(settings, "cache_enabled", False)
    configure_caches()


@pytest.mark.asyncio
async def test_check_rate_limit_noop_always_allows() -> None:
    """NoOpCache always returns delta=1 so check_rate_limit never blocks."""
    # 100 calls should all return True — NoOpCache never accumulates.
    for _ in range(100):
        result = await check_rate_limit(key="rl:test:noop", max_attempts=5, window_seconds=60)
        assert result is True


@pytest.mark.asyncio
async def test_check_rate_limit_redis_stub_blocks_on_threshold(monkeypatch: Any) -> None:
    """With a real counter, requests beyond max_attempts return False."""
    counter: dict[str, int] = {"count": 0}

    async def fake_increment(key: str, delta: int = 1) -> int:
        counter["count"] += delta
        return counter["count"]

    stub_cache = MagicMock()
    stub_cache.increment = fake_increment
    stub_cache.expire = AsyncMock(return_value=True)

    monkeypatch.setattr("oscilla.services.rate_limit.caches.get", lambda name: stub_cache)

    max_attempts = 3
    for i in range(max_attempts):
        result = await check_rate_limit(key="rl:test:stub", max_attempts=max_attempts, window_seconds=60)
        assert result is True, f"Expected True on attempt {i + 1}"

    # Next call exceeds the threshold
    result = await check_rate_limit(key="rl:test:stub", max_attempts=max_attempts, window_seconds=60)
    assert result is False


@pytest.mark.asyncio
async def test_check_rate_limit_sets_ttl_on_first_increment(monkeypatch: Any) -> None:
    """expire() is called with window_seconds on the first increment and not again."""
    counter: dict[str, int] = {"count": 0}
    expire_calls: list[dict[str, Any]] = []

    async def fake_increment(key: str, delta: int = 1) -> int:
        counter["count"] += delta
        return counter["count"]

    async def fake_expire(key: str, ttl: int) -> bool:
        expire_calls.append({"key": key, "ttl": ttl})
        return True

    stub_cache = MagicMock()
    stub_cache.increment = fake_increment
    stub_cache.expire = fake_expire

    monkeypatch.setattr("oscilla.services.rate_limit.caches.get", lambda name: stub_cache)

    window = 300
    await check_rate_limit(key="rl:test:ttl", max_attempts=10, window_seconds=window)
    assert len(expire_calls) == 1
    assert expire_calls[0]["ttl"] == window

    # Subsequent calls must NOT call expire again
    await check_rate_limit(key="rl:test:ttl", max_attempts=10, window_seconds=window)
    await check_rate_limit(key="rl:test:ttl", max_attempts=10, window_seconds=window)
    assert len(expire_calls) == 1
