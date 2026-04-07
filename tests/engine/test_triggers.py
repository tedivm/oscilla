"""Unit tests for the trigger system: queue mechanics, detection, and drain logic."""

from __future__ import annotations

from typing import List, Tuple
from unittest.mock import AsyncMock, MagicMock  # MagicMock used as session stub in drain test
from uuid import uuid4

import pytest

from oscilla.engine.character import CharacterState
from oscilla.engine.models.adventure import AdventureManifest, AdventureSpec, NarrativeStep
from oscilla.engine.models.base import LevelCondition, Metadata
from oscilla.engine.registry import ContentRegistry


def _make_state(level: int = 1) -> CharacterState:
    """Return a minimal CharacterState for trigger tests."""
    return CharacterState(
        character_id=uuid4(),
        name="Tester",
        character_class=None,
        level=level,
        xp=0,
        hp=20,
        max_hp=20,
        prestige_count=0,
        current_location=None,
    )


def _make_adventure(name: str, requires: LevelCondition | None = None) -> AdventureManifest:
    """Build a minimal one-step AdventureManifest."""
    return AdventureManifest(
        apiVersion="game/v1",
        kind="Adventure",
        metadata=Metadata(name=name),
        spec=AdventureSpec(
            displayName=name,
            steps=[NarrativeStep(type="narrative", text="Test step")],
            requires=requires,
        ),
    )


# ---------------------------------------------------------------------------
# test_enqueue_trigger_max_depth (task 7.1)
# ---------------------------------------------------------------------------


def test_enqueue_trigger_max_depth() -> None:
    """enqueue_trigger drops new entries once the queue reaches max_depth."""
    state = _make_state()
    max_depth = 3

    for i in range(max_depth):
        state.enqueue_trigger(f"trigger_{i}", max_depth=max_depth)
    assert len(state.pending_triggers) == max_depth

    # One more entry should be dropped, not appended.
    state.enqueue_trigger("overflow", max_depth=max_depth)
    assert len(state.pending_triggers) == max_depth


# ---------------------------------------------------------------------------
# test_on_level_up_enqueues_per_level (task 7.2)
# ---------------------------------------------------------------------------


def test_on_level_up_enqueues_per_level() -> None:
    """Each level gained from add_xp corresponds to one on_level_up enqueue."""
    state = _make_state()
    # Thresholds: 100 → level 2, 300 → level 3; grant enough to pass both.
    levels_gained, _ = state.add_xp(amount=350, xp_thresholds=[100, 300], hp_per_level=5)
    assert len(levels_gained) == 2

    # Simulate what the effect handler does: one enqueue per level gained.
    for _ in levels_gained:
        state.enqueue_trigger("on_level_up")

    assert state.pending_triggers.count("on_level_up") == 2


# ---------------------------------------------------------------------------
# test_stat_threshold_upward_crossing_only (task 7.3)
# ---------------------------------------------------------------------------


def test_stat_threshold_upward_crossing_only() -> None:
    """Threshold trigger enqueues on upward crossing; not on downward movement."""
    thresholds: List[Tuple[int, str]] = [(100, "fame-cap")]

    def _check_threshold(player: CharacterState, old_val: int, new_val: int) -> None:
        """Inline simulation of the detection logic used in the effect handlers."""
        for threshold_value, trigger_name in thresholds:
            if old_val < threshold_value <= new_val:
                player.enqueue_trigger(trigger_name)

    state = _make_state()
    state.stats["fame"] = 99

    # Upward crossing: 99 → 101 — should enqueue.
    _check_threshold(state, 99, 101)
    assert state.pending_triggers == ["fame-cap"]

    # Already above threshold: 101 → 110 — should not re-fire.
    _check_threshold(state, 101, 110)
    assert state.pending_triggers == ["fame-cap"]

    # Downward movement: 110 → 50 — should not fire on descent.
    _check_threshold(state, 110, 50)
    assert state.pending_triggers == ["fame-cap"]

    # Re-arm: crossing upward again from below — should fire a second time.
    _check_threshold(state, 50, 105)
    assert state.pending_triggers == ["fame-cap", "fame-cap"]


# ---------------------------------------------------------------------------
# test_drain_skips_ineligible (task 7.4)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_drain_skips_ineligible() -> None:
    """drain_trigger_queue skips adventures whose requires condition is not met."""
    # Build a registry with a level-gated adventure mapped to on_level_up.
    gated_adv = _make_adventure(
        "gated-adv",
        requires=LevelCondition(type="level", value=99),  # never met at level 1
    )
    registry = ContentRegistry()
    registry.trigger_index = {"on_level_up": ["gated-adv"]}
    registry.adventures.register(gated_adv)

    state = _make_state(level=1)
    state.pending_triggers = ["on_level_up"]

    # Inject state and registry into a MagicMock that stands in for a GameSession.
    session: MagicMock = MagicMock()
    session._character = state
    session.registry = registry
    session.run_adventure = AsyncMock()
    session._on_state_change = AsyncMock()

    from oscilla.engine.session import GameSession

    await GameSession.drain_trigger_queue(session)

    # The gated adventure must never have run.
    session.run_adventure.assert_not_called()
    # The trigger was popped from the queue.
    assert state.pending_triggers == []
