"""Tests for the account lockout service functions."""

import pytest

from oscilla.services.auth import clear_lockout, is_account_locked, record_failed_login
from oscilla.services.cache import configure_caches
from oscilla.settings import settings


@pytest.fixture(autouse=True)
def setup_caches(monkeypatch: pytest.MonkeyPatch) -> None:
    """Configure caches with NoOpCache so unit tests never need Redis."""
    monkeypatch.setattr(settings, "cache_enabled", False)
    configure_caches()


@pytest.mark.asyncio
async def test_is_account_locked_false_by_default() -> None:
    """is_account_locked returns False for an unknown email (NoOpCache.exists -> False)."""
    result = await is_account_locked("unknown@example.com")
    assert result is False


@pytest.mark.asyncio
async def test_record_failed_login_returns_false_below_threshold() -> None:
    """Below the lockout threshold, record_failed_login returns False.

    With NoOpCache, increment always returns delta=1 so the counter never
    accumulates — all calls return False (no lockout triggered).
    """
    threshold = settings.max_login_attempts_before_lockout
    for _ in range(threshold - 1):
        result = await record_failed_login("test@example.com")
        assert result is False


@pytest.mark.asyncio
async def test_clear_lockout_no_error() -> None:
    """clear_lockout completes without raising an exception."""
    await clear_lockout("test@example.com")
