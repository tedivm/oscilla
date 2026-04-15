"""Tests for the passive step handler."""

from __future__ import annotations

from uuid import uuid4

import pytest

from oscilla.engine.character import CharacterState
from oscilla.engine.models.adventure import PassiveStep
from oscilla.engine.models.base import MilestoneCondition
from oscilla.engine.pipeline import AdventureOutcome
from oscilla.engine.registry import ContentRegistry
from oscilla.engine.steps.passive import run_passive
from tests.engine.conftest import MockTUI


def _make_player() -> CharacterState:
    return CharacterState(
        character_id=uuid4(),
        name="Tester",
        character_class=None,
        prestige_count=0,
        stats={},
    )


@pytest.mark.asyncio
async def test_passive_no_bypass_applies_effects() -> None:
    """Without a bypass condition, effects are applied and text is shown."""
    player = _make_player()
    tui = MockTUI()
    registry = ContentRegistry()
    step = PassiveStep(
        type="passive",
        text="The spring glows.",
        effects=[{"type": "milestone_grant", "milestone": "found-spring"}],
    )

    outcome = await run_passive(step=step, player=player, registry=registry, tui=tui)

    assert outcome == AdventureOutcome.COMPLETED
    assert "The spring glows." in tui.texts
    assert "found-spring" in player.milestones


@pytest.mark.asyncio
async def test_passive_bypass_true_skips_effects_shows_bypass_text() -> None:
    """When bypass condition is met, effects are skipped and bypass_text is shown."""
    player = _make_player()
    player.grant_milestone("nimble")
    tui = MockTUI()
    registry = ContentRegistry()
    step = PassiveStep(
        type="passive",
        text="A dart fires!",
        effects=[{"type": "milestone_grant", "milestone": "dart-hit"}],
        bypass=MilestoneCondition(type="milestone", name="nimble"),
        bypass_text="Your reflexes save you.",
    )

    outcome = await run_passive(step=step, player=player, registry=registry, tui=tui)

    assert outcome == AdventureOutcome.COMPLETED
    assert "Your reflexes save you." in tui.texts
    assert "A dart fires!" not in tui.texts
    assert "dart-hit" not in player.milestones


@pytest.mark.asyncio
async def test_passive_bypass_true_no_bypass_text_silent_skip() -> None:
    """When bypass fires and no bypass_text is set, skip is silent."""
    player = _make_player()
    player.grant_milestone("nimble")
    tui = MockTUI()
    registry = ContentRegistry()
    step = PassiveStep(
        type="passive",
        text="A dart fires!",
        effects=[{"type": "milestone_grant", "milestone": "dart-hit"}],
        bypass=MilestoneCondition(type="milestone", name="nimble"),
    )

    outcome = await run_passive(step=step, player=player, registry=registry, tui=tui)

    assert outcome == AdventureOutcome.COMPLETED
    assert tui.texts == []
    assert "dart-hit" not in player.milestones


@pytest.mark.asyncio
async def test_passive_bypass_false_applies_effects() -> None:
    """When bypass condition is NOT met, effects apply normally."""
    player = _make_player()
    # Player does NOT have 'nimble' milestone — bypass should not fire.
    tui = MockTUI()
    registry = ContentRegistry()
    step = PassiveStep(
        type="passive",
        text="A dart fires!",
        effects=[{"type": "milestone_grant", "milestone": "dart-hit"}],
        bypass=MilestoneCondition(type="milestone", name="nimble"),
        bypass_text="Your reflexes save you.",
    )

    outcome = await run_passive(step=step, player=player, registry=registry, tui=tui)

    assert outcome == AdventureOutcome.COMPLETED
    assert "A dart fires!" in tui.texts
    assert "Your reflexes save you." not in tui.texts
    assert "dart-hit" in player.milestones


@pytest.mark.asyncio
async def test_passive_no_text_applies_effects_silently() -> None:
    """A passive step with no text applies effects without producing any output."""
    player = _make_player()
    tui = MockTUI()
    registry = ContentRegistry()
    step = PassiveStep(
        type="passive",
        effects=[{"type": "milestone_grant", "milestone": "silent-trigger"}],
    )

    outcome = await run_passive(step=step, player=player, registry=registry, tui=tui)

    assert outcome == AdventureOutcome.COMPLETED
    assert tui.texts == []
    assert "silent-trigger" in player.milestones
