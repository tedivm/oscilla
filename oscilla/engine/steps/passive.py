"""Passive step handler — auto-applies effects with optional bypass condition."""

from __future__ import annotations

from logging import getLogger
from typing import TYPE_CHECKING

from oscilla.engine.conditions import evaluate
from oscilla.engine.models.adventure import PassiveStep
from oscilla.engine.pipeline import AdventureOutcome
from oscilla.engine.steps.effects import run_effect

if TYPE_CHECKING:
    from oscilla.engine.character import CharacterState
    from oscilla.engine.pipeline import UICallbacks
    from oscilla.engine.registry import ContentRegistry

logger = getLogger(__name__)


async def run_passive(
    step: PassiveStep,
    player: "CharacterState",
    registry: "ContentRegistry",
    tui: "UICallbacks",
) -> AdventureOutcome:
    """Execute a passive step.

    1. Evaluate bypass condition (if any).
    2a. If bypassed and bypass_text is set — show bypass_text, skip effects.
    2b. If bypassed and no bypass_text — skip silently.
    3. If not bypassed — show text (if any), then apply all effects in order.
    """
    if step.bypass is not None and evaluate(condition=step.bypass, player=player, registry=registry):
        if step.bypass_text:
            await tui.show_text(step.bypass_text)
        return AdventureOutcome.COMPLETED

    if step.text:
        await tui.show_text(step.text)

    for effect in step.effects:
        await run_effect(effect=effect, player=player, registry=registry, tui=tui)

    return AdventureOutcome.COMPLETED
