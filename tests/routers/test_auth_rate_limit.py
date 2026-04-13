"""Integration tests verifying rate limiting and lockout are disabled with NoOpCache.

With `cache_enabled=False` (enforced via monkeypatch), `configure_caches()` registers
`NoOpCache` for the persistent cache alias.  `NoOpCache._increment` always returns
`delta=1` and `NoOpCache.exists` always returns `False`, so neither rate limiting
(HTTP 429) nor account lockout (HTTP 423) can trigger in the test environment.
"""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from oscilla.services.cache import configure_caches
from oscilla.settings import settings


@pytest.fixture(autouse=True)
def use_noop_cache(monkeypatch: Any) -> None:
    """Force NoOpCache for the persistent alias so no 429 or 423 responses occur."""
    monkeypatch.setattr(settings, "cache_enabled", False)
    configure_caches()


def test_login_rate_limit_disabled_with_noop_cache(auth_client: TestClient) -> None:
    """20 sequential failed logins against the same email never return 429.

    With NoOpCache, the rate-limit counter never accumulates, so `check_rate_limit`
    always returns True regardless of call count.
    """
    for _ in range(20):
        response = auth_client.post(
            "/auth/login",
            json={"email": "ratelimit@example.com", "password": "wrongpassword"},
        )
        assert response.status_code != 429, f"Unexpected 429 on attempt {_ + 1}"


def test_login_lockout_disabled_with_noop_cache(auth_client: TestClient) -> None:
    """10 sequential failed logins against the same email never return 423.

    NoOpCache.exists always returns False, so is_account_locked is always False
    and no 423 is raised.
    """
    auth_client.post("/auth/register", json={"email": "lockout@example.com", "password": "securepass123"})
    for _ in range(10):
        response = auth_client.post(
            "/auth/login",
            json={"email": "lockout@example.com", "password": "wrongpassword"},
        )
        assert response.status_code != 423, f"Unexpected 423 on attempt {_ + 1}"


def test_register_rate_limit_disabled_with_noop_cache(auth_client: TestClient) -> None:
    """10 sequential registration attempts from the same IP never return 429.

    With NoOpCache, the per-IP registration rate-limit counter never accumulates.
    Each attempt uses a unique email to avoid 409 conflicts.
    """
    for i in range(10):
        response = auth_client.post(
            "/auth/register",
            json={"email": f"newuser{i}@example.com", "password": "securepass123"},
        )
        assert response.status_code != 429, f"Unexpected 429 on attempt {i + 1}"
