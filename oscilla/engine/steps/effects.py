"""Effect dispatcher — applies mechanical outcomes to player state and notifies the TUI."""

from __future__ import annotations

import random
from collections import Counter
from typing import TYPE_CHECKING

from oscilla.engine.models.adventure import (
    Effect,
    EndAdventureEffect,
    HealEffect,
    ItemDropEffect,
    MilestoneGrantEffect,
    StatChangeEffect,
    StatSetEffect,
    XpGrantEffect,
)
from oscilla.engine.signals import _EndSignal

if TYPE_CHECKING:
    from oscilla.engine.character import CharacterState
    from oscilla.engine.pipeline import TUICallbacks
    from oscilla.engine.registry import ContentRegistry


async def run_effect(
    effect: Effect,
    player: "CharacterState",
    registry: "ContentRegistry",
    tui: "TUICallbacks",
) -> None:
    """Dispatch a single effect to its handler.

    Each effect mutates player state and emits a summary message via tui so
    the player sees XP gains, item finds, and heals in the narrative log.
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
            levels_gained, levels_lost = player.add_xp(amount=amount, xp_thresholds=thresholds, hp_per_level=hp_per)
            if amount >= 0:
                await tui.show_text(f"Gained {amount} XP.")
            else:
                await tui.show_text(f"Lost {abs(amount)} XP.")
            for level in levels_gained:
                await tui.show_text(f"[bold]Level up![/bold] You are now level {level}!")
            for level in levels_lost:
                await tui.show_text(f"[bold red]Level down![/bold red] You are now level {level}.")

        case ItemDropEffect(count=count, loot=loot):
            items = [entry.item for entry in loot]
            weights = [entry.weight for entry in loot]
            # Roll independently count times with replacement.
            chosen_items = random.choices(population=items, weights=weights, k=count)
            for item_ref in chosen_items:
                player.add_item(ref=item_ref, quantity=1)
            # Announce what was found, grouping identical items.
            item_counts: Counter[str] = Counter(chosen_items)
            parts = []
            for item_ref, qty in item_counts.items():
                item = registry.items.get(item_ref)
                name = item.spec.displayName if item is not None else item_ref
                parts.append(f"{name} \u00d7 {qty}" if qty > 1 else name)
            await tui.show_text(f"You found: {', '.join(parts)}")

        case MilestoneGrantEffect(milestone=milestone):
            player.grant_milestone(milestone)

        case EndAdventureEffect(outcome=outcome):
            raise _EndSignal(outcome)

        case HealEffect(amount=amount):
            before_hp = player.hp
            if amount == "full":
                player.hp = player.max_hp
            else:
                player.hp = min(player.hp + int(amount), player.max_hp)
            healed = player.hp - before_hp
            if healed > 0:
                await tui.show_text(f"Restored {healed} HP. (HP: {player.hp} / {player.max_hp})")

        case StatChangeEffect(stat=stat, amount=amount):
            if stat not in player.stats:
                await tui.show_text(f"[red]Error: stat {stat!r} not found[/red]")
                return
            old_value = player.stats[stat]
            if isinstance(old_value, (int, float)) and isinstance(amount, (int, float)):
                new_value = old_value + amount
                player.stats[stat] = new_value
                await tui.show_text(f"Changed {stat}: {old_value} → {new_value}")
            else:
                await tui.show_text(f"[red]Error: cannot change non-numeric stat {stat!r}[/red]")

        case StatSetEffect(stat=stat, value=value):
            if stat not in player.stats:
                await tui.show_text(f"[red]Error: stat {stat!r} not found[/red]")
                return
            old_value = player.stats[stat]
            player.stats[stat] = value
            await tui.show_text(f"Set {stat}: {old_value} → {value}")
