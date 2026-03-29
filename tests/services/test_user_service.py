"""Unit tests for the user service layer."""

from __future__ import annotations

import os
import socket
from unittest.mock import patch

from sqlalchemy.ext.asyncio import AsyncSession

from oscilla.services.user import derive_tui_user_key, get_or_create_user


def test_derive_tui_user_key_format() -> None:
    """Result is in USER@hostname format."""
    key = derive_tui_user_key()
    assert "@" in key
    hostname = socket.gethostname()
    assert key.endswith(f"@{hostname}")


def test_derive_tui_user_key_uses_user_env() -> None:
    """Resolution order picks USER over LOGNAME."""
    with patch.dict(os.environ, {"USER": "alice", "LOGNAME": "bob"}, clear=False):
        key = derive_tui_user_key()
    assert key.startswith("alice@")


def test_derive_tui_user_key_fallback_to_logname() -> None:
    """Falls back to LOGNAME when USER is absent."""
    env = {k: v for k, v in os.environ.items() if k not in ("USER", "LOGNAME")}
    env["LOGNAME"] = "carol"
    with patch.dict(os.environ, env, clear=True):
        key = derive_tui_user_key()
    assert key.startswith("carol@")


def test_derive_tui_user_key_fallback_to_unknown() -> None:
    """Falls back to 'unknown' when both USER and LOGNAME are absent."""
    env = {k: v for k, v in os.environ.items() if k not in ("USER", "LOGNAME")}
    with patch.dict(os.environ, env, clear=True):
        key = derive_tui_user_key()
    assert key.startswith("unknown@")


async def test_get_or_create_user_creates_new(async_session: AsyncSession) -> None:
    """get_or_create_user inserts a new row on first call."""
    user = await get_or_create_user(session=async_session, user_key="testuser@testhost")
    assert user.id is not None
    assert user.user_key == "testuser@testhost"


async def test_get_or_create_user_idempotent(async_session: AsyncSession) -> None:
    """Second call for the same user_key returns the previously created row."""
    user_key = "sameid@host"
    user1 = await get_or_create_user(session=async_session, user_key=user_key)
    user2 = await get_or_create_user(session=async_session, user_key=user_key)
    assert user1.id == user2.id
