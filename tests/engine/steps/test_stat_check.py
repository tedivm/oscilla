"""Tests for stat check step handler."""

from __future__ import annotations

from oscilla.engine.models.adventure import OutcomeBranch, StatCheckStep
from oscilla.engine.models.base import CharacterStatCondition, LevelCondition, MilestoneCondition
from oscilla.engine.pipeline import AdventureOutcome
from oscilla.engine.player import PlayerState
from oscilla.engine.steps.stat_check import run_stat_check


def test_stat_check_condition_passes(base_player: PlayerState) -> None:
    """Test stat check when condition passes."""
    # Player is level 1, so level >= 1 should pass
    condition = LevelCondition(type="level", value=1)

    on_pass = OutcomeBranch(effects=[], steps=[], goto=None)
    on_fail = OutcomeBranch(effects=[], steps=[], goto=None)

    step = StatCheckStep(type="stat_check", condition=condition, on_pass=on_pass, on_fail=on_fail)

    branch_calls = []

    def mock_run_outcome_branch(branch: OutcomeBranch) -> AdventureOutcome:
        branch_calls.append(branch)
        return AdventureOutcome.COMPLETED

    result = run_stat_check(step=step, player=base_player, run_outcome_branch=mock_run_outcome_branch)

    assert result == AdventureOutcome.COMPLETED
    assert len(branch_calls) == 1
    assert branch_calls[0] == on_pass


def test_stat_check_condition_fails(base_player: PlayerState) -> None:
    """Test stat check when condition fails."""
    # Player is level 1, so level >= 5 should fail
    condition = LevelCondition(type="level", value=5)

    on_pass = OutcomeBranch(effects=[], steps=[], goto=None)
    on_fail = OutcomeBranch(effects=[], steps=[], goto=None)

    step = StatCheckStep(type="stat_check", condition=condition, on_pass=on_pass, on_fail=on_fail)

    branch_calls = []

    def mock_run_outcome_branch(branch: OutcomeBranch) -> AdventureOutcome:
        branch_calls.append(branch)
        return AdventureOutcome.COMPLETED

    result = run_stat_check(step=step, player=base_player, run_outcome_branch=mock_run_outcome_branch)

    assert result == AdventureOutcome.COMPLETED
    assert len(branch_calls) == 1
    assert branch_calls[0] == on_fail


def test_stat_check_character_stat_condition(base_player: PlayerState) -> None:
    """Test stat check with character stat condition."""
    # Base player has strength = 10
    condition = CharacterStatCondition(type="character_stat", name="strength", gte=10)

    on_pass = OutcomeBranch(effects=[], steps=[], goto=None)
    on_fail = OutcomeBranch(effects=[], steps=[], goto=None)

    step = StatCheckStep(type="stat_check", condition=condition, on_pass=on_pass, on_fail=on_fail)

    branch_calls = []

    def mock_run_outcome_branch(branch: OutcomeBranch) -> AdventureOutcome:
        branch_calls.append(branch)
        return AdventureOutcome.COMPLETED

    result = run_stat_check(step=step, player=base_player, run_outcome_branch=mock_run_outcome_branch)

    assert result == AdventureOutcome.COMPLETED
    assert len(branch_calls) == 1
    assert branch_calls[0] == on_pass


def test_stat_check_milestone_condition(base_player: PlayerState) -> None:
    """Test stat check with milestone condition."""
    # Grant a milestone to test against
    base_player.grant_milestone("test-milestone")

    condition = MilestoneCondition(type="milestone", name="test-milestone")

    on_pass = OutcomeBranch(effects=[], steps=[], goto=None)
    on_fail = OutcomeBranch(effects=[], steps=[], goto=None)

    step = StatCheckStep(type="stat_check", condition=condition, on_pass=on_pass, on_fail=on_fail)

    branch_calls = []

    def mock_run_outcome_branch(branch: OutcomeBranch) -> AdventureOutcome:
        branch_calls.append(branch)
        return AdventureOutcome.COMPLETED

    result = run_stat_check(step=step, player=base_player, run_outcome_branch=mock_run_outcome_branch)

    assert result == AdventureOutcome.COMPLETED
    assert len(branch_calls) == 1
    assert branch_calls[0] == on_pass


def test_stat_check_propagates_branch_outcome(base_player: PlayerState) -> None:
    """Test that stat check propagates the outcome from the branch."""
    condition = LevelCondition(type="level", value=1)  # Will pass

    on_pass = OutcomeBranch(effects=[], steps=[], goto=None)
    on_fail = OutcomeBranch(effects=[], steps=[], goto=None)

    step = StatCheckStep(type="stat_check", condition=condition, on_pass=on_pass, on_fail=on_fail)

    def mock_run_outcome_branch(branch: OutcomeBranch) -> AdventureOutcome:
        # Return a different outcome to test propagation
        return AdventureOutcome.FLED

    result = run_stat_check(step=step, player=base_player, run_outcome_branch=mock_run_outcome_branch)

    assert result == AdventureOutcome.FLED


def test_stat_check_fail_branch_outcome(base_player: PlayerState) -> None:
    """Test stat check fail branch can return different outcomes."""
    condition = LevelCondition(type="level", value=10)  # Will fail

    on_pass = OutcomeBranch(effects=[], steps=[], goto=None)
    on_fail = OutcomeBranch(effects=[], steps=[], goto=None)

    step = StatCheckStep(type="stat_check", condition=condition, on_pass=on_pass, on_fail=on_fail)

    branch_calls = []

    def mock_run_outcome_branch(branch: OutcomeBranch) -> AdventureOutcome:
        branch_calls.append(branch)
        if branch == on_fail:
            return AdventureOutcome.DEFEATED
        return AdventureOutcome.COMPLETED

    result = run_stat_check(step=step, player=base_player, run_outcome_branch=mock_run_outcome_branch)

    assert result == AdventureOutcome.DEFEATED
    assert len(branch_calls) == 1
    assert branch_calls[0] == on_fail
