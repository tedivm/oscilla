"""Tests for quest_engine.py — _advance_quests_silent and evaluate_quest_advancements."""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from oscilla.engine.character import CharacterState
from oscilla.engine.quest_engine import _advance_quests_silent, evaluate_quest_advancements
from oscilla.engine.registry import ContentRegistry


def _make_player() -> CharacterState:
    """Minimal CharacterState for quest engine tests."""
    return CharacterState(
        character_id=uuid4(),
        name="Tester",
        prestige_count=0,
        stats={},
    )


# ---------------------------------------------------------------------------
# _advance_quests_silent tests
# ---------------------------------------------------------------------------


def test_silent_advance_moves_stage_to_terminal(
    minimal_quest_registry: ContentRegistry,
) -> None:
    """When the advance_on milestone is held, silent advance moves quest to terminal stage."""
    player = _make_player()
    player.active_quests["test-quest"] = "stage-a"
    player.grant_milestone("quest-a-done")

    _advance_quests_silent(player=player, registry=minimal_quest_registry)

    # Stage-b is terminal — quest should now be completed, not active.
    assert "test-quest" not in player.active_quests
    assert "test-quest" in player.completed_quests


def test_silent_advance_no_milestone_no_change(
    minimal_quest_registry: ContentRegistry,
) -> None:
    """Without the required milestone, silent advance does not move the quest."""
    player = _make_player()
    player.active_quests["test-quest"] = "stage-a"

    _advance_quests_silent(player=player, registry=minimal_quest_registry)

    assert player.active_quests == {"test-quest": "stage-a"}
    assert "test-quest" not in player.completed_quests


def test_silent_advance_no_active_quests_is_noop() -> None:
    """With no active quests, silent advance returns immediately without errors."""
    registry = ContentRegistry()
    player = _make_player()

    _advance_quests_silent(player=player, registry=registry)

    assert player.active_quests == {}
    assert player.completed_quests == set()


def test_silent_advance_unknown_quest_logs_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """An active quest not found in registry produces a warning and is skipped."""
    registry = ContentRegistry()
    player = _make_player()
    player.active_quests["ghost-quest"] = "stage-x"

    import logging

    with caplog.at_level(logging.WARNING, logger="oscilla.engine.quest_engine"):
        _advance_quests_silent(player=player, registry=registry)

    # Quest unchanged — unknown quest is skipped, not raised.
    assert player.active_quests == {"ghost-quest": "stage-x"}
    assert any("ghost-quest" in record.message for record in caplog.records)


# ---------------------------------------------------------------------------
# evaluate_quest_advancements tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_evaluate_advancements_fires_completion_effects(
    minimal_quest_registry: ContentRegistry,
) -> None:
    """When the advance milestone is held, full evaluation fires completion effects."""
    player = _make_player()
    player.active_quests["test-quest"] = "stage-a"
    player.grant_milestone("quest-a-done")
    tui = AsyncMock()

    await evaluate_quest_advancements(player=player, registry=minimal_quest_registry, tui=tui)

    # Completion effect was milestone_grant("quest-complete").
    assert "quest-complete" in player.milestones
    assert "test-quest" in player.completed_quests
    # TUI was notified of quest completion.
    tui.show_text.assert_called()
    shown = " ".join(str(call.args[0]) for call in tui.show_text.call_args_list)
    assert "Test Quest" in shown


@pytest.mark.asyncio
async def test_evaluate_advancements_no_milestone_no_change(
    minimal_quest_registry: ContentRegistry,
) -> None:
    """Without the advance milestone, evaluate_quest_advancements makes no changes."""
    player = _make_player()
    player.active_quests["test-quest"] = "stage-a"
    tui = AsyncMock()

    await evaluate_quest_advancements(player=player, registry=minimal_quest_registry, tui=tui)

    assert player.active_quests == {"test-quest": "stage-a"}
    assert "test-quest" not in player.completed_quests
    tui.show_text.assert_not_called()


@pytest.mark.asyncio
async def test_evaluate_advancements_no_active_quests_is_noop() -> None:
    """With no active quests, evaluate_quest_advancements returns without calling TUI."""
    registry = ContentRegistry()
    player = _make_player()
    tui = AsyncMock()

    await evaluate_quest_advancements(player=player, registry=registry, tui=tui)

    tui.show_text.assert_not_called()


# ---------------------------------------------------------------------------
# Model validator tests
# ---------------------------------------------------------------------------


def test_completion_effects_on_non_terminal_stage_raises() -> None:
    """A non-terminal stage with completion_effects must raise a ValidationError."""
    from pydantic import ValidationError

    from oscilla.engine.models.quest import QuestManifest

    with pytest.raises(ValidationError, match="not terminal"):
        QuestManifest.model_validate(
            {
                "apiVersion": "oscilla/v1",
                "kind": "Quest",
                "metadata": {"name": "bad-quest"},
                "spec": {
                    "displayName": "Bad Quest",
                    "entry_stage": "stage-a",
                    "stages": [
                        {
                            "name": "stage-a",
                            "advance_on": ["done"],
                            "next_stage": "stage-b",
                            "completion_effects": [{"type": "milestone_grant", "milestone": "early-reward"}],
                        },
                        {"name": "stage-b", "terminal": True},
                    ],
                },
            }
        )
