"""Tests for quest_activate effect and milestone_grant → quest advancement integration."""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from oscilla.engine.character import CharacterState
from oscilla.engine.models.adventure import QuestActivateEffect
from oscilla.engine.registry import ContentRegistry
from oscilla.engine.steps.effects import run_effect


def _make_player() -> CharacterState:
    """Minimal CharacterState for quest effect tests."""
    return CharacterState(
        character_id=uuid4(),
        name="Tester",
        prestige_count=0,
        stats={},
    )


@pytest.mark.asyncio
async def test_quest_activate_starts_quest(
    minimal_quest_registry: ContentRegistry,
) -> None:
    """A quest_activate effect on a known quest adds it to active_quests."""
    player = _make_player()
    tui = AsyncMock()
    effect = QuestActivateEffect(type="quest_activate", quest_ref="test-quest")

    await run_effect(effect=effect, player=player, registry=minimal_quest_registry, tui=tui)

    assert "test-quest" in player.active_quests
    assert player.active_quests["test-quest"] == "stage-a"
    tui.show_text.assert_called()
    shown = " ".join(str(call.args[0]) for call in tui.show_text.call_args_list)
    assert "Test Quest" in shown


@pytest.mark.asyncio
async def test_quest_activate_unknown_ref_is_error(
    minimal_quest_registry: ContentRegistry,
) -> None:
    """A quest_activate with an unknown quest_ref shows an error message and no-ops."""
    player = _make_player()
    tui = AsyncMock()
    effect = QuestActivateEffect(type="quest_activate", quest_ref="nonexistent-quest")

    await run_effect(effect=effect, player=player, registry=minimal_quest_registry, tui=tui)

    assert player.active_quests == {}
    tui.show_text.assert_called()
    shown = str(tui.show_text.call_args_list)
    assert "not found" in shown


@pytest.mark.asyncio
async def test_quest_activate_already_active_is_noop(
    minimal_quest_registry: ContentRegistry,
) -> None:
    """Activating an already-active quest is a no-op (stays at current stage)."""
    player = _make_player()
    player.active_quests["test-quest"] = "stage-a"
    tui = AsyncMock()
    effect = QuestActivateEffect(type="quest_activate", quest_ref="test-quest")

    await run_effect(effect=effect, player=player, registry=minimal_quest_registry, tui=tui)

    assert player.active_quests == {"test-quest": "stage-a"}
    tui.show_text.assert_not_called()


@pytest.mark.asyncio
async def test_quest_activate_already_completed_is_noop(
    minimal_quest_registry: ContentRegistry,
) -> None:
    """Activating an already-completed quest is a no-op."""
    player = _make_player()
    player.completed_quests.add("test-quest")
    tui = AsyncMock()
    effect = QuestActivateEffect(type="quest_activate", quest_ref="test-quest")

    await run_effect(effect=effect, player=player, registry=minimal_quest_registry, tui=tui)

    assert "test-quest" not in player.active_quests
    tui.show_text.assert_not_called()


@pytest.mark.asyncio
async def test_milestone_grant_triggers_quest_advancement(
    minimal_quest_registry: ContentRegistry,
) -> None:
    """Granting a milestone that satisfies an advance_on condition advances the quest."""
    from oscilla.engine.models.adventure import MilestoneGrantEffect

    player = _make_player()
    player.active_quests["test-quest"] = "stage-a"
    tui = AsyncMock()
    effect = MilestoneGrantEffect(type="milestone_grant", milestone="quest-a-done")

    await run_effect(effect=effect, player=player, registry=minimal_quest_registry, tui=tui)

    # Quest should now be complete (stage-b is terminal with completion effect).
    assert "test-quest" not in player.active_quests
    assert "test-quest" in player.completed_quests
    # Completion effect (milestone_grant quest-complete) was fired.
    assert "quest-complete" in player.milestones


@pytest.mark.asyncio
async def test_quest_activate_with_milestone_already_held_advances_immediately(
    minimal_quest_registry: ContentRegistry,
) -> None:
    """Activating a quest when the advance_on milestone is already held advances in same tick."""
    player = _make_player()
    player.grant_milestone("quest-a-done")
    tui = AsyncMock()
    effect = QuestActivateEffect(type="quest_activate", quest_ref="test-quest")

    await run_effect(effect=effect, player=player, registry=minimal_quest_registry, tui=tui)

    # Quest was activated and immediately advanced to terminal.
    assert "test-quest" not in player.active_quests
    assert "test-quest" in player.completed_quests
    # Completion effect fired.
    assert "quest-complete" in player.milestones
