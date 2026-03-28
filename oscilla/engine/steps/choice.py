"""Choice step handler — filters options by condition and presents a menu."""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from oscilla.engine.conditions import evaluate
from oscilla.engine.models.adventure import ChoiceStep, OutcomeBranch
from oscilla.engine.pipeline import AdventureOutcome, TUICallbacks

if TYPE_CHECKING:
    from oscilla.engine.player import PlayerState


def run_choice(
    step: ChoiceStep,
    player: "PlayerState",
    tui: TUICallbacks,
    run_outcome_branch: Callable[[OutcomeBranch], AdventureOutcome],
) -> AdventureOutcome:
    """Filter eligible options, present a numbered menu, then execute the chosen branch.

    Options whose requires condition is not met are hidden entirely — the player
    never sees them. If all options are gated (empty eligible list), a fallback
    message is shown and the step completes without branching.
    """
    eligible = [opt for opt in step.options if evaluate(opt.requires, player)]

    if not eligible:
        # No options available; show a notice and continue the adventure.
        tui.show_text("(No options are available here.)")
        return AdventureOutcome.COMPLETED

    labels = [opt.label for opt in eligible]
    choice_idx = tui.show_menu(step.prompt, labels)
    chosen = eligible[choice_idx - 1]

    # Fire option-level effects first, then branch via steps or goto.
    from oscilla.engine.models.adventure import OutcomeBranch as OB

    branch = OB(effects=chosen.effects, steps=list(chosen.steps), goto=chosen.goto)
    return run_outcome_branch(branch)
