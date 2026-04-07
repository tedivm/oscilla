"""Tests for quest failure states: fail_condition, fail_effects, and QuestFailEffect."""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from oscilla.engine.character import CharacterState
from oscilla.engine.models.quest import QuestManifest
from oscilla.engine.quest_engine import _advance_quests_silent, _evaluate_quest_failures
from oscilla.engine.registry import ContentRegistry

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_player() -> CharacterState:
    return CharacterState(
        character_id=uuid4(),
        name="Tester",
        character_class=None,
        level=1,
        xp=0,
        hp=20,
        max_hp=20,
        prestige_count=0,
        current_location=None,
        stats={},
    )


def _make_failable_registry() -> ContentRegistry:
    """Registry with a quest whose active stage has a fail_condition."""
    registry = ContentRegistry()
    quest = QuestManifest.model_validate(
        {
            "apiVersion": "oscilla/v1",
            "kind": "Quest",
            "metadata": {"name": "failable-quest"},
            "spec": {
                "displayName": "Failable Quest",
                "entry_stage": "active",
                "stages": [
                    {
                        "name": "active",
                        "advance_on": ["quest-done"],
                        "next_stage": "complete",
                        "fail_condition": {"type": "milestone", "name": "quest-fail-trigger"},
                        "fail_effects": [{"type": "milestone_grant", "milestone": "quest-failed-side-effect"}],
                    },
                    {
                        "name": "complete",
                        "terminal": True,
                    },
                ],
            },
        }
    )
    registry.quests.register(quest)
    return registry


# ---------------------------------------------------------------------------
# _evaluate_quest_failures — async
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_evaluate_failures_moves_quest_to_failed_when_condition_met() -> None:
    """When fail_condition is met, the quest moves to failed_quests."""
    registry = _make_failable_registry()
    player = _make_player()
    player.active_quests["failable-quest"] = "active"
    player.milestones.add("quest-fail-trigger")
    tui = AsyncMock()

    await _evaluate_quest_failures(player=player, registry=registry, tui=tui)

    assert "failable-quest" not in player.active_quests
    assert "failable-quest" in player.failed_quests


@pytest.mark.asyncio
async def test_evaluate_failures_runs_fail_effects() -> None:
    """When fail_condition fires, fail_effects are executed."""
    registry = _make_failable_registry()
    player = _make_player()
    player.active_quests["failable-quest"] = "active"
    player.milestones.add("quest-fail-trigger")
    tui = AsyncMock()

    await _evaluate_quest_failures(player=player, registry=registry, tui=tui)

    assert "quest-failed-side-effect" in player.milestones


@pytest.mark.asyncio
async def test_evaluate_failures_shows_tui_message() -> None:
    """When fail_condition fires, TUI receives a failure message."""
    registry = _make_failable_registry()
    player = _make_player()
    player.active_quests["failable-quest"] = "active"
    player.milestones.add("quest-fail-trigger")
    tui = AsyncMock()

    await _evaluate_quest_failures(player=player, registry=registry, tui=tui)

    tui.show_text.assert_called()
    shown = " ".join(str(call.args[0]) for call in tui.show_text.call_args_list)
    assert "Failable Quest" in shown


@pytest.mark.asyncio
async def test_evaluate_failures_no_change_when_condition_not_met() -> None:
    """When fail_condition is not met, the quest remains active."""
    registry = _make_failable_registry()
    player = _make_player()
    player.active_quests["failable-quest"] = "active"
    tui = AsyncMock()

    await _evaluate_quest_failures(player=player, registry=registry, tui=tui)

    assert player.active_quests == {"failable-quest": "active"}
    assert "failable-quest" not in player.failed_quests
    tui.show_text.assert_not_called()


# ---------------------------------------------------------------------------
# _advance_quests_silent — fail_quests_silent
# ---------------------------------------------------------------------------


def test_silent_advance_silently_fails_quest_when_condition_met() -> None:
    """Silent advance silently fails quests whose fail_condition is already met."""
    registry = _make_failable_registry()
    player = _make_player()
    player.active_quests["failable-quest"] = "active"
    player.milestones.add("quest-fail-trigger")

    _advance_quests_silent(player=player, registry=registry)

    assert "failable-quest" not in player.active_quests
    assert "failable-quest" in player.failed_quests
    # fail_effects must NOT run during silent correction.
    assert "quest-failed-side-effect" not in player.milestones


def test_silent_advance_does_not_fail_quest_when_condition_not_met() -> None:
    """Without the fail milestone, silent advance does not fail the quest."""
    registry = _make_failable_registry()
    player = _make_player()
    player.active_quests["failable-quest"] = "active"

    _advance_quests_silent(player=player, registry=registry)

    assert player.active_quests == {"failable-quest": "active"}
    assert "failable-quest" not in player.failed_quests


# ---------------------------------------------------------------------------
# QuestFailEffect handler
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_quest_fail_effect_moves_quest_to_failed() -> None:
    """The quest_fail effect moves the target quest from active to failed_quests."""
    from oscilla.engine.models.adventure import QuestFailEffect
    from oscilla.engine.steps.effects import run_effect

    registry = _make_failable_registry()
    player = _make_player()
    player.active_quests["failable-quest"] = "active"
    tui = AsyncMock()

    await run_effect(
        effect=QuestFailEffect(type="quest_fail", quest_ref="failable-quest"),
        player=player,
        registry=registry,
        tui=tui,
    )

    assert "failable-quest" not in player.active_quests
    assert "failable-quest" in player.failed_quests


@pytest.mark.asyncio
async def test_quest_fail_effect_no_op_when_not_active() -> None:
    """The quest_fail effect is a no-op when the quest is not currently active."""
    from oscilla.engine.models.adventure import QuestFailEffect
    from oscilla.engine.steps.effects import run_effect

    registry = _make_failable_registry()
    player = _make_player()
    tui = AsyncMock()

    await run_effect(
        effect=QuestFailEffect(type="quest_fail", quest_ref="failable-quest"),
        player=player,
        registry=registry,
        tui=tui,
    )

    # No state change.
    assert "failable-quest" not in player.failed_quests


@pytest.mark.asyncio
async def test_quest_fail_effect_unknown_quest_logs_error(caplog: pytest.LogCaptureFixture) -> None:
    """The quest_fail effect logs an error and shows TUI message when quest ref is not found."""
    import logging

    from oscilla.engine.models.adventure import QuestFailEffect
    from oscilla.engine.steps.effects import run_effect

    registry = ContentRegistry()
    player = _make_player()
    # Quest not active — but also not in registry
    player.active_quests["ghost-quest"] = "stage-x"
    tui = AsyncMock()

    with caplog.at_level(logging.ERROR, logger="oscilla.engine.steps.effects"):
        await run_effect(
            effect=QuestFailEffect(type="quest_fail", quest_ref="ghost-quest"),
            player=player,
            registry=registry,
            tui=tui,
        )

    # Quest should not be moved to failed (we logged the error and returned).
    tui.show_text.assert_called()
    shown = " ".join(str(call.args[0]) for call in tui.show_text.call_args_list)
    assert "ghost-quest" in shown


# ---------------------------------------------------------------------------
# Model validator: terminal stage must not have fail_condition
# ---------------------------------------------------------------------------


def test_terminal_stage_with_fail_condition_raises() -> None:
    """A terminal stage with fail_condition must raise a ValidationError."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="terminal"):
        QuestManifest.model_validate(
            {
                "apiVersion": "oscilla/v1",
                "kind": "Quest",
                "metadata": {"name": "bad-quest"},
                "spec": {
                    "displayName": "Bad Quest",
                    "entry_stage": "end",
                    "stages": [
                        {
                            "name": "end",
                            "terminal": True,
                            "fail_condition": {"type": "milestone", "name": "some-milestone"},
                        }
                    ],
                },
            }
        )
