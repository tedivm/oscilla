"""Integration tests for the trigger system using GameSession and the trigger_tests fixture."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest
from sqlalchemy import update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession

import oscilla.models  # noqa: F401 — ensure all ORM models are registered for create_all
from oscilla.engine.models.game import GameRejoinTrigger, StatThresholdTrigger
from oscilla.engine.session import GameSession
from oscilla.models.character import CharacterRecord
from tests.engine.conftest import MockTUI
from tests.fixtures.content.trigger_tests import build_trigger_test_registry

# ---------------------------------------------------------------------------
# DB fixture scoped to this module — fresh in-memory SQLite per test.
# Each test function gets its own session via async_session (from root conftest).
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_GAME_NAME = "trigger-test-game"


# ---------------------------------------------------------------------------
# 8.2 — on_character_create fires before game loop
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_on_character_create_fires_before_game_loop(
    async_session: AsyncSession,
) -> None:
    """on_character_create trigger adventure runs before the player enters the world."""
    registry = build_trigger_test_registry(
        trigger_adventures={"on_character_create": ["welcome-adventure"]},
    )
    tui = MockTUI()
    async with GameSession(
        registry=registry,
        tui=tui,
        db_session=async_session,
        game_name=_GAME_NAME,
        character_name="CreateHero",
    ) as session:
        await session.start()
        await session.drain_trigger_queue()

    # The welcome adventure's narrative text should have appeared.
    assert any("welcome" in t.lower() for t in tui.texts), f"Expected 'welcome' in TUI texts; got: {tui.texts}"
    # Queue should be empty after drain.
    assert session._character is not None
    assert session._character.pending_triggers == []


# ---------------------------------------------------------------------------
# 8.3 — on_game_rejoin fires when the player has been absent long enough
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_on_game_rejoin_fires_when_absent(
    async_session: AsyncSession,
) -> None:
    """on_game_rejoin trigger adventure fires when the player has been absent >= absence_hours."""
    registry = build_trigger_test_registry(
        on_game_rejoin=GameRejoinTrigger(absence_hours=1),
        trigger_adventures={"on_game_rejoin": ["rejoin-adventure"]},
    )

    # Session 1: create the character (updated_at = now, no rejoin fired).
    async with GameSession(
        registry=registry,
        tui=MockTUI(),
        db_session=async_session,
        game_name=_GAME_NAME,
        character_name="RejoinHero",
    ) as session1:
        await session1.start()
        character_id: UUID = session1._character.character_id  # type: ignore[union-attr]

    # Backdate the character's updated_at to simulate a long absence.
    old_time = datetime.now(tz=timezone.utc) - timedelta(hours=2)
    await async_session.execute(
        sa_update(CharacterRecord)
        .where(CharacterRecord.id == character_id)
        .values(updated_at=old_time)
        .execution_options(synchronize_session="fetch")
    )
    await async_session.commit()

    # Session 2: load the character — absence is > 1 hour → enqueue rejoin.
    tui = MockTUI()
    async with GameSession(
        registry=registry,
        tui=tui,
        db_session=async_session,
        game_name=_GAME_NAME,
        character_name="RejoinHero",
    ) as session2:
        await session2.start()
        await session2.drain_trigger_queue()

    assert any("welcome back" in t.lower() for t in tui.texts), f"Expected rejoin text; got: {tui.texts}"


# ---------------------------------------------------------------------------
# 8.4 — on_stat_threshold fires after stat_change crosses xp threshold
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_on_stat_threshold_fires_after_xp_change(
    async_session: AsyncSession,
) -> None:
    """on_stat_threshold trigger adventure fires after xp stat crosses the declared threshold."""
    registry = build_trigger_test_registry(
        on_stat_threshold=[StatThresholdTrigger(stat="xp", threshold=100, name="xp-100-reached")],
        trigger_adventures={"xp-100-reached": ["level-up-adventure"]},
    )
    tui = MockTUI()
    async with GameSession(
        registry=registry,
        tui=tui,
        db_session=async_session,
        game_name=_GAME_NAME,
        character_name="LevelHero",
    ) as session:
        await session.start()
        # Run an adventure that grants 100 XP via stat_change.
        await session.run_adventure("test-xp-grant-adventure")
        await session.drain_trigger_queue()

    assert any("level up" in t.lower() for t in tui.texts), f"Expected level-up notification text; got: {tui.texts}"


# ---------------------------------------------------------------------------
# 8.5 — on_outcome_defeated fires after defeat
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_on_outcome_defeated_fires_after_defeat(
    async_session: AsyncSession,
) -> None:
    """on_outcome_defeated trigger adventure fires after an adventure ends with outcome=defeated."""
    registry = build_trigger_test_registry(
        trigger_adventures={"on_outcome_defeated": ["defeat-recovery-adventure"]},
    )
    tui = MockTUI()
    async with GameSession(
        registry=registry,
        tui=tui,
        db_session=async_session,
        game_name=_GAME_NAME,
        character_name="DefeatHero",
    ) as session:
        await session.start()
        # Run an adventure that immediately ends with outcome=defeated.
        await session.run_adventure("test-defeat-outcome-adventure")
        await session.drain_trigger_queue()

    assert any("recover" in t.lower() for t in tui.texts), f"Expected defeat recovery text; got: {tui.texts}"


# ---------------------------------------------------------------------------
# 8.6 — emit_trigger chains into a custom adventure
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_emit_trigger_chains_custom_adventure(
    async_session: AsyncSession,
) -> None:
    """emit_trigger effect enqueues a custom trigger that drains into a second adventure."""
    registry = build_trigger_test_registry(
        custom_triggers=["test-custom"],
        trigger_adventures={
            "on_character_create": ["test-emit-adventure"],
            "test-custom": ["custom-trigger-adventure"],
        },
    )
    tui = MockTUI()
    async with GameSession(
        registry=registry,
        tui=tui,
        db_session=async_session,
        game_name=_GAME_NAME,
        character_name="EmitHero",
    ) as session:
        await session.start()
        await session.drain_trigger_queue()

    assert any("custom trigger" in t.lower() for t in tui.texts), f"Expected custom trigger text; got: {tui.texts}"


# ---------------------------------------------------------------------------
# 8.7 — on_stat_threshold fires on upward crossing
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_on_stat_threshold_fires_on_upward_crossing(
    async_session: AsyncSession,
) -> None:
    """on_stat_threshold trigger fires when a stat crosses its configured threshold upward."""
    registry = build_trigger_test_registry(
        on_stat_threshold=[StatThresholdTrigger(stat="gold", threshold=50, name="gold-milestone")],
        trigger_adventures={"gold-milestone": ["threshold-reached-adventure"]},
    )
    tui = MockTUI()
    async with GameSession(
        registry=registry,
        tui=tui,
        db_session=async_session,
        game_name=_GAME_NAME,
        character_name="GoldHero",
    ) as session:
        await session.start()
        # Run the stat-boost adventure: sets gold from 0 to 60, crossing threshold 50.
        await session.run_adventure("test-stat-boost-adventure")
        await session.drain_trigger_queue()

    assert any("threshold" in t.lower() for t in tui.texts), f"Expected threshold text; got: {tui.texts}"


# ---------------------------------------------------------------------------
# 8.8 — pending_triggers survive a session roundtrip
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pending_triggers_survive_session_roundtrip(
    async_session: AsyncSession,
) -> None:
    """Pending triggers persisted at adventure_end are restored when the character is reloaded."""
    registry = build_trigger_test_registry()
    # "roundtrip-token" is not registered in trigger_index, so it is safe to
    # store and retrieve without accidentally running an adventure.
    roundtrip_trigger = "roundtrip-token"

    character_id: UUID | None = None

    # Session 1: create character, inject a trigger, persist it.
    async with GameSession(
        registry=registry,
        tui=MockTUI(),
        db_session=async_session,
        game_name=_GAME_NAME,
        character_name="RoundtripHero",
    ) as session1:
        await session1.start()
        assert session1._character is not None
        character_id = session1._character.character_id
        session1._character.pending_triggers = [roundtrip_trigger]
        await session1._on_state_change(state=session1._character, event="adventure_end")

    # Session 2: reload the same character and verify the trigger is present.
    async with GameSession(
        registry=registry,
        tui=MockTUI(),
        db_session=async_session,
        game_name=_GAME_NAME,
        character_name="RoundtripHero",
    ) as session2:
        await session2.start()

    assert session2._character is not None
    assert session2._character.character_id == character_id
    assert roundtrip_trigger in session2._character.pending_triggers, (
        f"Expected {roundtrip_trigger!r} in pending_triggers; got: {session2._character.pending_triggers}"
    )
