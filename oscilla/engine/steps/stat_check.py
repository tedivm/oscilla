"""Stat-check step handler — evaluates a condition silently and branches."""

from __future__ import annotations

from typing import TYPE_CHECKING, Awaitable, Callable

from oscilla.engine.conditions import evaluate
from oscilla.engine.models.adventure import OutcomeBranch, StatCheckStep
from oscilla.engine.pipeline import AdventureOutcome

if TYPE_CHECKING:
    from oscilla.engine.character import CharacterState
    from oscilla.engine.registry import ContentRegistry


async def run_stat_check(
    step: StatCheckStep,
    player: "CharacterState",
    run_outcome_branch: Callable[[OutcomeBranch], Awaitable[AdventureOutcome]],
    registry: "ContentRegistry | None" = None,
) -> AdventureOutcome:
    """Evaluate the step's condition against the player and branch accordingly.

    No TUI output is produced by the stat-check itself; any visible feedback
    lives inside the on_pass / on_fail branch steps authored by the content
    creator.
    """
    if evaluate(condition=step.condition, player=player, registry=registry):
        return await run_outcome_branch(step.on_pass)
    else:
        return await run_outcome_branch(step.on_fail)
