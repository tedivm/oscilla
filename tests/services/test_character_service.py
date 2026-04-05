"""Integration tests for the character persistence service layer.

All tests use the async_session fixture (in-memory SQLite) and never touch
the real filesystem database or the content/ package.
"""

from __future__ import annotations

import logging
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.exc import StaleDataError

from oscilla.engine.character import CharacterState
from oscilla.engine.loader import load
from oscilla.engine.registry import ContentRegistry
from oscilla.models.character_iteration import CharacterIterationRecord
from oscilla.services.character import (
    acquire_session_lock,
    get_active_iteration_id,
    list_characters_for_user,
    load_all_iterations,
    load_character,
    prestige_character,
    release_session_lock,
    save_character,
    set_quest,
    upsert_adventure_state,
)
from oscilla.services.user import get_or_create_user
from tests.engine.conftest import FIXTURES

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


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
    registry, _warnings = load(FIXTURES / "minimal")
    return registry


# ---------------------------------------------------------------------------
# save_character / load_character
# ---------------------------------------------------------------------------


async def test_save_character_inserts_row(
    async_session: AsyncSession,
    minimal_registry: ContentRegistry,
) -> None:
    """save_character() inserts a new CharacterRecord without error."""
    user = await get_or_create_user(session=async_session, user_key="svc@host")
    player = _make_player(minimal_registry)
    await save_character(session=async_session, state=player, user_id=user.id, game_name="test-game")

    characters = await list_characters_for_user(session=async_session, user_id=user.id, game_name="test-game")
    assert len(characters) == 1
    assert characters[0].name == player.name


async def test_save_character_duplicate_raises(
    async_session: AsyncSession,
    minimal_registry: ContentRegistry,
) -> None:
    """Saving the same character_id twice raises IntegrityError."""
    user = await get_or_create_user(session=async_session, user_key="dup@host")
    player = _make_player(minimal_registry, name="DupChar")
    await save_character(session=async_session, state=player, user_id=user.id, game_name="test-game")

    with pytest.raises(IntegrityError):
        await save_character(session=async_session, state=player, user_id=user.id, game_name="test-game")


async def test_stale_version_raises_stale_data_error(
    async_session: AsyncSession,
    minimal_registry: ContentRegistry,
) -> None:
    """StaleDataError is raised when the version column differs between memory and DB.

    Uses no_autoflush so that `iteration.level = 2` is not automatically flushed
    before the bulk version bump.  After the bump, the identity map still holds
    version = 0 while the DB (in the same transaction) has version = 1.  An
    explicit flush() then generates ``WHERE version = 0``, matches 0 rows, and
    raises StaleDataError.
    """
    from sqlalchemy import select, update

    user = await get_or_create_user(session=async_session, user_key="stale@host")
    player = _make_player(minimal_registry, name="StaleHero")
    await save_character(session=async_session, state=player, user_id=user.id, game_name="test-game")

    iteration_id = await get_active_iteration_id(session=async_session, character_id=player.character_id)
    assert iteration_id is not None

    # Load the record into the identity map — version = 0 in memory.
    stmt = select(CharacterIterationRecord).where(CharacterIterationRecord.id == iteration_id)
    result = await async_session.execute(stmt)
    iteration = result.scalar_one()

    # Disable autoflush while we set up the stale state.  Without this,
    # executing the bulk UPDATE below would trigger an autoflush of
    # `iteration.level = 2` BEFORE the version bump, allowing it to succeed
    # (defeating the point of the test).
    with async_session.no_autoflush:
        iteration.level = 2  # mark dirty (not yet flushed)

        # Bump version in the DB via a bulk UPDATE with synchronize_session=False
        # so the identity map is NOT updated.  version in memory = 0; DB = 1.
        await async_session.execute(
            update(CharacterIterationRecord)
            .where(CharacterIterationRecord.id == iteration_id)
            .values(version=iteration.version + 1),
            execution_options={"synchronize_session": False},
        )

    # flush() → SQLAlchemy generates WHERE version = 0, DB has 1 → 0 rows → StaleDataError.
    with pytest.raises(StaleDataError):
        await async_session.flush()


async def test_load_character_returns_none_for_unknown(
    async_session: AsyncSession,
    minimal_registry: ContentRegistry,
) -> None:
    """load_character() returns None for a character_id not in the database."""
    assert minimal_registry.character_config is not None
    result = await load_character(
        session=async_session,
        character_id=uuid4(),
        character_config=minimal_registry.character_config,
    )
    assert result is None


async def test_load_character_matches_saved_state(
    async_session: AsyncSession,
    minimal_registry: ContentRegistry,
) -> None:
    """load_character() reconstructs a CharacterState that matches what was saved."""
    assert minimal_registry.character_config is not None
    user = await get_or_create_user(session=async_session, user_key="load@host")
    player = _make_player(minimal_registry, name="LoadHero")
    player.level = 3
    player.xp = 90
    player.add_item(ref="test-potion", quantity=2)
    player.grant_milestone("found-sword")
    await save_character(session=async_session, state=player, user_id=user.id, game_name="test-game")

    loaded = await load_character(
        session=async_session,
        character_id=player.character_id,
        character_config=minimal_registry.character_config,
    )
    assert loaded is not None
    assert loaded.name == player.name
    assert loaded.level == player.level
    assert loaded.xp == player.xp
    assert loaded.stacks == player.stacks
    assert loaded.milestones == player.milestones


# ---------------------------------------------------------------------------
# prestige_character / load_all_iterations
# ---------------------------------------------------------------------------


async def test_prestige_character_creates_new_iteration(
    async_session: AsyncSession,
    minimal_registry: ContentRegistry,
) -> None:
    """prestige_character() flips is_active on old row and opens a new iteration."""
    assert minimal_registry.character_config is not None
    user = await get_or_create_user(session=async_session, user_key="prestige@host")
    player = _make_player(minimal_registry, name="PrestigeHero")
    await save_character(session=async_session, state=player, user_id=user.id, game_name="test-game")

    new_iter = await prestige_character(
        session=async_session,
        character_id=player.character_id,
        character_config=minimal_registry.character_config,
    )

    assert new_iter.is_active is True
    assert new_iter.iteration == 1  # 0-indexed: second run

    all_iters = await load_all_iterations(session=async_session, character_id=player.character_id)
    assert len(all_iters) == 2
    # old iteration must be closed
    old = next(i for i in all_iters if i.iteration == 0)
    assert old.is_active is False
    assert old.completed_at is not None


async def test_load_all_iterations_ordered(
    async_session: AsyncSession,
    minimal_registry: ContentRegistry,
) -> None:
    """load_all_iterations() returns rows in iteration ASC order."""
    assert minimal_registry.character_config is not None
    user = await get_or_create_user(session=async_session, user_key="alliter@host")
    player = _make_player(minimal_registry, name="IterHero")
    await save_character(session=async_session, state=player, user_id=user.id, game_name="test-game")
    await prestige_character(
        session=async_session,
        character_id=player.character_id,
        character_config=minimal_registry.character_config,
    )

    iters = await load_all_iterations(session=async_session, character_id=player.character_id)
    assert len(iters) == 2
    assert iters[0].iteration < iters[1].iteration


# ---------------------------------------------------------------------------
# acquire_session_lock / release_session_lock
# ---------------------------------------------------------------------------


async def test_acquire_lock_on_free_iteration(
    async_session: AsyncSession,
    minimal_registry: ContentRegistry,
) -> None:
    """acquire_session_lock() sets session_token when it is currently NULL."""
    user = await get_or_create_user(session=async_session, user_key="lockfree@host")
    player = _make_player(minimal_registry, name="LockFreeHero")
    await save_character(session=async_session, state=player, user_id=user.id, game_name="test-game")

    iteration_id = await get_active_iteration_id(session=async_session, character_id=player.character_id)
    assert iteration_id is not None

    token = "token-free-123"
    await acquire_session_lock(session=async_session, iteration_id=iteration_id, token=token)

    from sqlalchemy import select

    stmt = select(CharacterIterationRecord).where(CharacterIterationRecord.id == iteration_id)
    result = await async_session.execute(stmt)
    row = result.scalar_one()
    assert row.session_token == token


async def test_acquire_lock_steals_stale_token(
    async_session: AsyncSession,
    minimal_registry: ContentRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """acquire_session_lock() steals a non-NULL token and logs a WARNING."""
    user = await get_or_create_user(session=async_session, user_key="locksteal@host")
    player = _make_player(minimal_registry, name="StealLockHero")
    await save_character(session=async_session, state=player, user_id=user.id, game_name="test-game")

    iteration_id = await get_active_iteration_id(session=async_session, character_id=player.character_id)
    assert iteration_id is not None

    old_token = "old-dead-process-token"
    await acquire_session_lock(session=async_session, iteration_id=iteration_id, token=old_token)

    new_token = "new-session-token"
    with caplog.at_level(logging.WARNING, logger="oscilla.services.character"):
        await acquire_session_lock(session=async_session, iteration_id=iteration_id, token=new_token)

    assert any(old_token in record.message for record in caplog.records)

    from sqlalchemy import select

    stmt = select(CharacterIterationRecord).where(CharacterIterationRecord.id == iteration_id)
    result = await async_session.execute(stmt)
    row = result.scalar_one()
    assert row.session_token == new_token


async def test_release_lock_matches_token(
    async_session: AsyncSession,
    minimal_registry: ContentRegistry,
) -> None:
    """release_session_lock() clears token when it matches."""
    user = await get_or_create_user(session=async_session, user_key="release@host")
    player = _make_player(minimal_registry, name="ReleaseHero")
    await save_character(session=async_session, state=player, user_id=user.id, game_name="test-game")

    iteration_id = await get_active_iteration_id(session=async_session, character_id=player.character_id)
    assert iteration_id is not None

    token = "release-token"
    await acquire_session_lock(session=async_session, iteration_id=iteration_id, token=token)
    await release_session_lock(session=async_session, iteration_id=iteration_id, token=token)

    from sqlalchemy import select

    stmt = select(CharacterIterationRecord).where(CharacterIterationRecord.id == iteration_id)
    result = await async_session.execute(stmt)
    row = result.scalar_one()
    assert row.session_token is None


async def test_release_lock_noop_wrong_token(
    async_session: AsyncSession,
    minimal_registry: ContentRegistry,
) -> None:
    """release_session_lock() is a no-op when the token doesn't match."""
    user = await get_or_create_user(session=async_session, user_key="noop@host")
    player = _make_player(minimal_registry, name="NoopReleaseHero")
    await save_character(session=async_session, state=player, user_id=user.id, game_name="test-game")

    iteration_id = await get_active_iteration_id(session=async_session, character_id=player.character_id)
    assert iteration_id is not None

    token = "real-token"
    await acquire_session_lock(session=async_session, iteration_id=iteration_id, token=token)
    # Wrong token — should not clear the lock
    await release_session_lock(session=async_session, iteration_id=iteration_id, token="wrong-token")

    from sqlalchemy import select

    stmt = select(CharacterIterationRecord).where(CharacterIterationRecord.id == iteration_id)
    result = await async_session.execute(stmt)
    row = result.scalar_one()
    assert row.session_token == token


# ---------------------------------------------------------------------------
# Adventure repeat-control state persistence (round-trip)
# ---------------------------------------------------------------------------


async def test_adventure_repeat_state_persists_and_reloads(
    async_session: AsyncSession,
    minimal_registry: ContentRegistry,
) -> None:
    """adventure_last_completed_on / adventure_last_completed_at_ticks round-trip.

    upsert_adventure_state() writes the row; load_character() reads it back
    into CharacterState.adventure_last_completed_on and
    adventure_last_completed_at_ticks.
    """
    assert minimal_registry.character_config is not None
    user = await get_or_create_user(session=async_session, user_key="advstate@host")
    player = _make_player(minimal_registry, name="AdvStateHero")
    await save_character(session=async_session, state=player, user_id=user.id, game_name="test-game")

    iteration_id = await get_active_iteration_id(session=async_session, character_id=player.character_id)
    assert iteration_id is not None

    await upsert_adventure_state(
        session=async_session,
        iteration_id=iteration_id,
        adventure_ref="test-quest",
        last_completed_on="2026-04-04",
        last_completed_at_ticks=7,
    )

    loaded = await load_character(
        session=async_session,
        character_id=player.character_id,
        character_config=minimal_registry.character_config,
    )
    assert loaded is not None
    assert loaded.adventure_last_completed_on["test-quest"] == "2026-04-04"
    assert loaded.adventure_last_completed_at_ticks["test-quest"] == 7


# ---------------------------------------------------------------------------
# Quest failure state persistence (round-trip)
# ---------------------------------------------------------------------------


async def test_failed_quests_persists_and_reloads(
    async_session: AsyncSession,
    minimal_registry: ContentRegistry,
) -> None:
    """set_quest(status='failed') persists; load_character() restores failed_quests.

    Verifies the full persistence round-trip: a quest marked 'failed' via
    set_quest() reappears in CharacterState.failed_quests after load_character().
    """
    assert minimal_registry.character_config is not None
    user = await get_or_create_user(session=async_session, user_key="failquest@host")
    player = _make_player(minimal_registry, name="FailQuestHero")
    await save_character(session=async_session, state=player, user_id=user.id, game_name="test-game")

    iteration_id = await get_active_iteration_id(session=async_session, character_id=player.character_id)
    assert iteration_id is not None

    await set_quest(
        session=async_session,
        iteration_id=iteration_id,
        quest_ref="test-hostage-rescue",
        status="failed",
        stage=None,
    )

    loaded = await load_character(
        session=async_session,
        character_id=player.character_id,
        character_config=minimal_registry.character_config,
    )
    assert loaded is not None
    assert "test-hostage-rescue" in loaded.failed_quests
    assert "test-hostage-rescue" not in loaded.active_quests
