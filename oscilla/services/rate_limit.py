"""Rate limiting service using the persistent cache backend.

Uses the aiocache ``persistent`` cache to atomically increment a counter per
key and block requests that exceed the configured threshold.

With ``NoOpCache`` (when ``cache_enabled=False``), ``_increment`` returns
``delta=1`` on every call so the count never accumulates past 1. This means
``check_rate_limit`` always returns ``True`` and rate limiting is transparently
disabled in development without any special-casing.
"""

from logging import getLogger

from aiocache import caches  # type: ignore[import-untyped]

logger = getLogger(__name__)


async def check_rate_limit(key: str, max_attempts: int, window_seconds: int) -> bool:
    """Check whether the given key is within the allowed request rate.

    Atomically increments a counter for ``key`` in the persistent cache.
    On the first increment (count == 1) the TTL is set to ``window_seconds``
    so the window resets automatically.

    Args:
        key: Unique key for this rate-limit bucket (e.g. ``"rl:login:user@example.com"``).
        max_attempts: Maximum allowed increments within the window.
        window_seconds: Length of the sliding window in seconds.

    Returns:
        ``True`` if the request is within the limit, ``False`` if it is exceeded.
    """
    cache = caches.get("persistent")
    count: int = await cache.increment(key, delta=1)

    # On the first increment, set the TTL so the window expires automatically.
    if count == 1:
        await cache.expire(key, ttl=window_seconds)

    if count > max_attempts:
        logger.warning("Rate limit exceeded for key: %s (count=%d, max=%d)", key, count, max_attempts)
        return False

    return True
