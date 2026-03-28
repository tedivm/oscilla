"""Effect dispatcher — applies silent mechanical outcomes to player state."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

from oscilla.engine.models.adventure import (Effect, EndAdventureEffect,
                                             HealEffect, ItemDropEffect,
                                             MilestoneGrantEffect,
                                             XpGrantEffect)
from oscilla.engine.signals import _EndSignal

if TYPE_CHECKING:
    from oscilla.engine.player import PlayerState
    from oscilla.engine.registry import ContentRegistry


def run_effect(
    effect: Effect,
    player: "PlayerState",
    registry: "ContentRegistry",
) -> None:
    """Dispatch a single effect to its handler.

    Effects are always silent — they mutate player state with no TUI calls.
    EndAdventureEffect raises _EndSignal which propagates up to the pipeline's
    run() loop; it never escapes AdventurePipeline.
    """
    match effect:
        case XpGrantEffect(amount=amount):
            game = registry.game
            if game is not None:
                thresholds = game.spec.xp_thresholds
                hp_per = game.spec.hp_formula.hp_per_level
            else:
                thresholds = []
                hp_per = 0
            player.add_xp(amount=amount, xp_thresholds=thresholds, hp_per_level=hp_per)

        case ItemDropEffect(count=count, loot=loot):
            items = [entry.item for entry in loot]
            weights = [entry.weight for entry in loot]
            # Roll independently count times with replacement.
            chosen_items = random.choices(population=items, weights=weights, k=count)
            for item_ref in chosen_items:
                player.add_item(ref=item_ref, quantity=1)

        case MilestoneGrantEffect(milestone=milestone):
            player.grant_milestone(milestone)

        case EndAdventureEffect(outcome=outcome):
            raise _EndSignal(outcome)

        case HealEffect(amount=amount):
            if amount == "full":
                player.hp = player.max_hp
            else:
                player.hp = min(player.hp + int(amount), player.max_hp)
