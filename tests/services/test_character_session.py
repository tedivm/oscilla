"""Integration tests for web session locking and session output service functions.

All tests use the async_session fixture (in-memory SQLite) and never touch
the real filesystem database.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from oscilla.engine.character import CharacterState
from oscilla.engine.loader import load_from_disk
from oscilla.engine.registry import ContentRegistry
from oscilla.models.character_iteration import CharacterIterationRecord
from oscilla.services.character import (
    acquire_web_session_lock,
    clear_session_output,
    force_acquire_web_session_lock,
    get_active_iteration_id,
    get_session_output,
    release_web_session_lock,
    save_character,
    save_session_output,
)
from oscilla.services.user import get_or_create_user
from tests.engine.conftest import FIXTURES


def _make_player(registry: ContentRegistry, name: str = "TestHero") -> CharacterState:
    assert registry.game is not None
    assert registry.character_config is not None
    return CharacterState.new_character(
        name=name,
        game_manifest=registry.game,
        character_config=registry.character_config,
    )


@pytest.fixture(scope="module")
def minimal_registry() -> ContentRegistry:
    registry, _warnings = load_from_disk(FIXTURES / "minimal")
    return registry


# ---------------------------------------------------------------------------
# acquire_web_session_lock
# ---------------------------------------------------------------------------


async def test_acquire_web_lock_returns_none_when_free(
    async_session: AsyncSession,
    minimal_registry: ContentRegistry,
) -> None:
    """acquire_web_session_lock() returns None and writes token when lock is free."""
    user = await get_or_create_user(session=async_session, user_key="web-lock-free@host")
    player = _make_player(minimal_registry, name="WebLockFree")
    await save_character(session=async_session, state=player, user_id=user.id, game_name="test-game")

    iteration_id = await get_active_iteration_id(session=async_session, character_id=player.character_id)
    assert iteration_id is not None

    token = str(uuid4())
    result = await acquire_web_session_lock(
        session=async_session,
        iteration_id=iteration_id,
        token=token,
        stale_threshold_minutes=10,
    )
    assert result is None

    stmt = select(CharacterIterationRecord).where(CharacterIterationRecord.id == iteration_id)
    row = (await async_session.execute(stmt)).scalar_one()
    assert row.session_token == token
    assert row.session_token_acquired_at is not None


async def test_acquire_web_lock_returns_datetime_when_live(
    async_session: AsyncSession,
    minimal_registry: ContentRegistry,
) -> None:
    """acquire_web_session_lock() returns datetime when a live session holds the lock."""
    user = await get_or_create_user(session=async_session, user_key="web-lock-live@host")
    player = _make_player(minimal_registry, name="WebLockLive")
    await save_character(session=async_session, state=player, user_id=user.id, game_name="test-game")

    iteration_id = await get_active_iteration_id(session=async_session, character_id=player.character_id)
    assert iteration_id is not None

    token_a = str(uuid4())
    # First acquire — should succeed.
    first_result = await acquire_web_session_lock(
        session=async_session,
        iteration_id=iteration_id,
        token=token_a,
        stale_threshold_minutes=10,
    )
    assert first_result is None

    # Second acquire with a different token — should return the acquired_at datetime.
    token_b = str(uuid4())
    conflict_result = await acquire_web_session_lock(
        session=async_session,
        iteration_id=iteration_id,
        token=token_b,
        stale_threshold_minutes=10,
    )
    assert conflict_result is not None
    assert isinstance(conflict_result, datetime)


async def test_acquire_web_lock_succeeds_on_stale_session(
    async_session: AsyncSession,
    minimal_registry: ContentRegistry,
) -> None:
    """acquire_web_session_lock() takes over and returns None when lock is stale."""
    user = await get_or_create_user(session=async_session, user_key="web-lock-stale@host")
    player = _make_player(minimal_registry, name="WebLockStale")
    await save_character(session=async_session, state=player, user_id=user.id, game_name="test-game")

    iteration_id = await get_active_iteration_id(session=async_session, character_id=player.character_id)
    assert iteration_id is not None

    # Manually write a stale lock (acquired well in the past).
    stmt = select(CharacterIterationRecord).where(CharacterIterationRecord.id == iteration_id)
    row = (await async_session.execute(stmt)).scalar_one()
    row.session_token = "old-stale-token"
    row.session_token_acquired_at = datetime.now(tz=timezone.utc) - timedelta(minutes=30)
    await async_session.commit()

    new_token = str(uuid4())
    result = await acquire_web_session_lock(
        session=async_session,
        iteration_id=iteration_id,
        token=new_token,
        stale_threshold_minutes=10,  # 10 min threshold; lock is 30 min old → stale
    )
    assert result is None

    row2 = (await async_session.execute(stmt)).scalar_one()
    assert row2.session_token == new_token


# ---------------------------------------------------------------------------
# release_web_session_lock
# ---------------------------------------------------------------------------


async def test_release_web_lock_clears_when_token_matches(
    async_session: AsyncSession,
    minimal_registry: ContentRegistry,
) -> None:
    """release_web_session_lock() clears both columns when token matches."""
    user = await get_or_create_user(session=async_session, user_key="web-lock-release@host")
    player = _make_player(minimal_registry, name="WebLockRelease")
    await save_character(session=async_session, state=player, user_id=user.id, game_name="test-game")

    iteration_id = await get_active_iteration_id(session=async_session, character_id=player.character_id)
    assert iteration_id is not None

    token = str(uuid4())
    await acquire_web_session_lock(
        session=async_session, iteration_id=iteration_id, token=token, stale_threshold_minutes=10
    )
    await release_web_session_lock(session=async_session, iteration_id=iteration_id, token=token)

    stmt = select(CharacterIterationRecord).where(CharacterIterationRecord.id == iteration_id)
    row = (await async_session.execute(stmt)).scalar_one()
    assert row.session_token is None
    assert row.session_token_acquired_at is None


async def test_release_web_lock_noop_when_token_wrong(
    async_session: AsyncSession,
    minimal_registry: ContentRegistry,
) -> None:
    """release_web_session_lock() is a no-op when token does not match."""
    user = await get_or_create_user(session=async_session, user_key="web-lock-noop@host")
    player = _make_player(minimal_registry, name="WebLockNoop")
    await save_character(session=async_session, state=player, user_id=user.id, game_name="test-game")

    iteration_id = await get_active_iteration_id(session=async_session, character_id=player.character_id)
    assert iteration_id is not None

    real_token = str(uuid4())
    await acquire_web_session_lock(
        session=async_session, iteration_id=iteration_id, token=real_token, stale_threshold_minutes=10
    )
    # Release with wrong token — should not clear the lock.
    await release_web_session_lock(session=async_session, iteration_id=iteration_id, token="wrong-token")

    stmt = select(CharacterIterationRecord).where(CharacterIterationRecord.id == iteration_id)
    row = (await async_session.execute(stmt)).scalar_one()
    assert row.session_token == real_token


# ---------------------------------------------------------------------------
# force_acquire_web_session_lock
# ---------------------------------------------------------------------------


async def test_force_acquire_unconditionally_clears_adventure_state(
    async_session: AsyncSession,
    minimal_registry: ContentRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """force_acquire_web_session_lock() unconditionally acquires and clears adventure state."""
    user = await get_or_create_user(session=async_session, user_key="web-lock-force@host")
    player = _make_player(minimal_registry, name="WebLockForce")
    await save_character(session=async_session, state=player, user_id=user.id, game_name="test-game")

    iteration_id = await get_active_iteration_id(session=async_session, character_id=player.character_id)
    assert iteration_id is not None

    # Write an existing lock and some adventure state.
    old_token = "prior-session-token"
    stmt = select(CharacterIterationRecord).where(CharacterIterationRecord.id == iteration_id)
    row = (await async_session.execute(stmt)).scalar_one()
    row.session_token = old_token
    row.session_token_acquired_at = datetime.now(tz=timezone.utc)
    row.adventure_ref = "some-adventure"
    row.adventure_step_index = 2
    await async_session.commit()

    new_token = str(uuid4())
    with caplog.at_level(logging.WARNING, logger="oscilla.services.character"):
        await force_acquire_web_session_lock(session=async_session, iteration_id=iteration_id, token=new_token)

    # Log should mention the old token.
    assert any(old_token in record.message for record in caplog.records)

    row2 = (await async_session.execute(stmt)).scalar_one()
    assert row2.session_token == new_token
    assert row2.adventure_ref is None
    assert row2.adventure_step_index is None
    assert row2.adventure_step_state is None


# ---------------------------------------------------------------------------
# save_session_output / get_session_output / clear_session_output
# ---------------------------------------------------------------------------


async def test_save_and_get_session_output_round_trip(
    async_session: AsyncSession,
    minimal_registry: ContentRegistry,
) -> None:
    """save_session_output / get_session_output round-trips preserving order and content."""
    user = await get_or_create_user(session=async_session, user_key="session-output@host")
    player = _make_player(minimal_registry, name="SessionOutputHero")
    await save_character(session=async_session, state=player, user_id=user.id, game_name="test-game")

    iteration_id = await get_active_iteration_id(session=async_session, character_id=player.character_id)
    assert iteration_id is not None

    events = [
        {"type": "narrative", "data": {"text": "You enter the dungeon.", "context": {}}},
        {"type": "choice", "data": {"prompt": "What do you do?", "options": ["Fight", "Flee"], "context": {}}},
    ]
    await save_session_output(session=async_session, iteration_id=iteration_id, events=events)

    retrieved = await get_session_output(session=async_session, iteration_id=iteration_id)
    assert len(retrieved) == 2
    assert retrieved[0] == events[0]
    assert retrieved[1] == events[1]


async def test_save_session_output_replaces_existing(
    async_session: AsyncSession,
    minimal_registry: ContentRegistry,
) -> None:
    """save_session_output() replaces all existing rows for the iteration."""
    user = await get_or_create_user(session=async_session, user_key="session-replace@host")
    player = _make_player(minimal_registry, name="SessionReplaceHero")
    await save_character(session=async_session, state=player, user_id=user.id, game_name="test-game")

    iteration_id = await get_active_iteration_id(session=async_session, character_id=player.character_id)
    assert iteration_id is not None

    first_events = [{"type": "narrative", "data": {"text": "Step 1.", "context": {}}}]
    await save_session_output(session=async_session, iteration_id=iteration_id, events=first_events)

    second_events = [
        {"type": "narrative", "data": {"text": "Step A.", "context": {}}},
        {"type": "narrative", "data": {"text": "Step B.", "context": {}}},
        {"type": "ack_required", "data": {"context": {}}},
    ]
    await save_session_output(session=async_session, iteration_id=iteration_id, events=second_events)

    retrieved = await get_session_output(session=async_session, iteration_id=iteration_id)
    assert len(retrieved) == 3
    assert retrieved[0]["data"]["text"] == "Step A."


async def test_clear_session_output_removes_all_rows(
    async_session: AsyncSession,
    minimal_registry: ContentRegistry,
) -> None:
    """clear_session_output() removes all rows for the iteration."""
    user = await get_or_create_user(session=async_session, user_key="session-clear@host")
    player = _make_player(minimal_registry, name="SessionClearHero")
    await save_character(session=async_session, state=player, user_id=user.id, game_name="test-game")

    iteration_id = await get_active_iteration_id(session=async_session, character_id=player.character_id)
    assert iteration_id is not None

    events = [{"type": "narrative", "data": {"text": "Before clear.", "context": {}}}]
    await save_session_output(session=async_session, iteration_id=iteration_id, events=events)
    await clear_session_output(session=async_session, iteration_id=iteration_id)

    retrieved = await get_session_output(session=async_session, iteration_id=iteration_id)
    assert retrieved == []
