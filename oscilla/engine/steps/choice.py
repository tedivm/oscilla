"""Choice step handler — filters options by condition and presents a menu."""

from __future__ import annotations

from typing import TYPE_CHECKING, Awaitable, Callable

from oscilla.engine.conditions import evaluate
from oscilla.engine.models.adventure import ChoiceStep, OutcomeBranch
from oscilla.engine.pipeline import AdventureOutcome, UICallbacks

if TYPE_CHECKING:
    from oscilla.engine.character import CharacterState
    from oscilla.engine.registry import ContentRegistry


async def run_choice(
    step: ChoiceStep,
    player: "CharacterState",
    tui: UICallbacks,
    run_outcome_branch: Callable[[OutcomeBranch], Awaitable[AdventureOutcome]],
    registry: "ContentRegistry | None" = None,
) -> AdventureOutcome:
    """Filter eligible options, present a menu, then execute the chosen branch.

    Options whose requires condition is not met are hidden entirely — the player
    never sees them. If all options are gated (empty eligible list), a fallback
    message is shown and the step completes without branching.
    """
    eligible = [opt for opt in step.options if evaluate(condition=opt.requires, player=player, registry=registry)]

    if not eligible:
        # No options available; show a notice and continue the adventure.
        await tui.show_text("(No options are available here.)")
        return AdventureOutcome.COMPLETED

    labels = [opt.label for opt in eligible]
    choice_idx = await tui.show_menu(step.prompt, labels)
    chosen = eligible[choice_idx - 1]

    # Fire option-level effects first, then branch via steps or goto.
    from oscilla.engine.models.adventure import OutcomeBranch as OB

    branch = OB(effects=chosen.effects, steps=list(chosen.steps), goto=chosen.goto)
    return await run_outcome_branch(branch)
