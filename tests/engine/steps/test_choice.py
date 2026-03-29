"""Tests for choice step handler."""

from __future__ import annotations

import pytest

from oscilla.engine.models.adventure import ChoiceOption, ChoiceStep, OutcomeBranch
from oscilla.engine.models.base import LevelCondition, MilestoneCondition
from oscilla.engine.pipeline import AdventureOutcome
from oscilla.engine.character import CharacterState
from oscilla.engine.steps.choice import run_choice
from tests.engine.conftest import MockTUI


async def test_choice_step_with_all_options_available(base_player: CharacterState) -> None:
    """Test choice step when all options are available."""
    mock_tui = MockTUI(menu_responses=[1])  # Choose first option

    options = [
        ChoiceOption(label="Option A", requires=None, effects=[], steps=[], goto=None),
        ChoiceOption(label="Option B", requires=None, effects=[], steps=[], goto=None),
    ]
    step = ChoiceStep(type="choice", prompt="Choose wisely:", options=options)

    outcome_calls = []

    async def mock_run_outcome_branch(branch: OutcomeBranch) -> AdventureOutcome:
        outcome_calls.append(branch)
        return AdventureOutcome.COMPLETED

    result = await run_choice(step=step, player=base_player, tui=mock_tui, run_outcome_branch=mock_run_outcome_branch)

    assert result == AdventureOutcome.COMPLETED
    assert len(outcome_calls) == 1
    assert len(mock_tui.menus) == 1  # One menu call made


async def test_choice_step_with_filtered_options(base_player: CharacterState) -> None:
    """Test choice step with some options filtered out by conditions."""
    mock_tui = MockTUI(menu_responses=[1])  # Choose first available option

    options = [
        ChoiceOption(
            label="High Level Option",
            requires=LevelCondition(type="level", value=5),  # Player is level 1
            effects=[],
            steps=[],
            goto=None,
        ),
        ChoiceOption(
            label="Available Option",
            requires=LevelCondition(type="level", value=1),  # Player is level 1
            effects=[],
            steps=[],
            goto=None,
        ),
    ]
    step = ChoiceStep(type="choice", prompt="Choose wisely:", options=options)

    outcome_calls = []

    async def mock_run_outcome_branch(branch: OutcomeBranch) -> AdventureOutcome:
        outcome_calls.append(branch)
        return AdventureOutcome.COMPLETED

    result = await run_choice(step=step, player=base_player, tui=mock_tui, run_outcome_branch=mock_run_outcome_branch)

    assert result == AdventureOutcome.COMPLETED
    assert len(outcome_calls) == 1
    # Only "Available Option" should be shown
    assert len(mock_tui.menus) == 1
    prompt, options_shown = mock_tui.menus[0]
    assert options_shown == ["Available Option"]


async def test_choice_step_no_options_available(base_player: CharacterState) -> None:
    """Test choice step when no options are available."""
    mock_tui = MockTUI()

    options = [
        ChoiceOption(
            label="Unavailable Option",
            requires=LevelCondition(type="level", value=10),  # Player is level 1
            effects=[],
            steps=[],
            goto=None,
        ),
    ]
    step = ChoiceStep(type="choice", prompt="Choose wisely:", options=options)

    async def mock_run_outcome_branch(branch: OutcomeBranch) -> AdventureOutcome:
        pytest.fail("run_outcome_branch should not be called when no options available")

    result = await run_choice(step=step, player=base_player, tui=mock_tui, run_outcome_branch=mock_run_outcome_branch)

    assert result == AdventureOutcome.COMPLETED
    assert len(mock_tui.menus) == 0  # No menu shown
    assert "(No options are available here.)" in mock_tui.texts


async def test_choice_step_with_milestone_condition(base_player: CharacterState) -> None:
    """Test choice option filtering based on milestone conditions."""
    base_player.grant_milestone("special-flag")
    mock_tui = MockTUI(menu_responses=[2])  # Choose second option

    options = [
        ChoiceOption(label="Option A", requires=None, effects=[], steps=[], goto=None),
        ChoiceOption(
            label="Special Option",
            requires=MilestoneCondition(type="milestone", name="special-flag"),
            effects=[],
            steps=[],
            goto=None,
        ),
        ChoiceOption(
            label="Missing Milestone",
            requires=MilestoneCondition(type="milestone", name="missing-flag"),
            effects=[],
            steps=[],
            goto=None,
        ),
    ]
    step = ChoiceStep(type="choice", prompt="Choose:", options=options)

    outcome_calls = []

    async def mock_run_outcome_branch(branch: OutcomeBranch) -> AdventureOutcome:
        outcome_calls.append(branch)
        return AdventureOutcome.COMPLETED

    result = await run_choice(step=step, player=base_player, tui=mock_tui, run_outcome_branch=mock_run_outcome_branch)

    assert result == AdventureOutcome.COMPLETED
    assert len(outcome_calls) == 1
    # Should show Option A and Special Option, but not Missing Milestone
    assert len(mock_tui.menus) == 1
    prompt, options_shown = mock_tui.menus[0]
    assert options_shown == ["Option A", "Special Option"]


async def test_choice_step_creates_outcome_branch_correctly(base_player: CharacterState) -> None:
    """Test that choice step creates OutcomeBranch with correct attributes."""
    from oscilla.engine.models.adventure import MilestoneGrantEffect

    mock_tui = MockTUI(menu_responses=[1])

    effects = [MilestoneGrantEffect(type="milestone_grant", milestone="test-choice-made")]
    options = [
        ChoiceOption(label="Test Option", requires=None, effects=effects, steps=[], goto="test-label"),
    ]
    step = ChoiceStep(type="choice", prompt="Choose:", options=options)

    outcome_calls = []

    async def mock_run_outcome_branch(branch: OutcomeBranch) -> AdventureOutcome:
        outcome_calls.append(branch)
        return AdventureOutcome.COMPLETED

    await run_choice(step=step, player=base_player, tui=mock_tui, run_outcome_branch=mock_run_outcome_branch)

    assert len(outcome_calls) == 1
    branch = outcome_calls[0]
    assert len(branch.effects) == 1
    assert isinstance(branch.effects[0], MilestoneGrantEffect)
    assert branch.effects[0].milestone == "test-choice-made"
    assert branch.goto == "test-label"
    assert list(branch.steps) == []
