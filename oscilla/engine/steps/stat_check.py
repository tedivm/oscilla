"""Stat-check step handler — evaluates a condition silently and branches."""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from oscilla.engine.conditions import evaluate
from oscilla.engine.models.adventure import OutcomeBranch, StatCheckStep
from oscilla.engine.pipeline import AdventureOutcome

if TYPE_CHECKING:
    from oscilla.engine.player import PlayerState


def run_stat_check(
    step: StatCheckStep,
    player: "PlayerState",
    run_outcome_branch: Callable[[OutcomeBranch], AdventureOutcome],
) -> AdventureOutcome:
    """Evaluate the step's condition against the player and branch accordingly.

    No TUI output is produced by the stat-check itself; any visible feedback
    lives inside the on_pass / on_fail branch steps authored by the content
    creator.
    """
    if evaluate(step.condition, player):
        return run_outcome_branch(step.on_pass)
    else:
        return run_outcome_branch(step.on_fail)
