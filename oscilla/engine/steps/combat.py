"""Combat step handler — turn-based fight loop."""

from __future__ import annotations

from typing import TYPE_CHECKING, Awaitable, Callable

from oscilla.engine.models.adventure import CombatStep, OutcomeBranch
from oscilla.engine.pipeline import AdventureOutcome, TUICallbacks

if TYPE_CHECKING:
    from oscilla.engine.character import CharacterState
    from oscilla.engine.registry import ContentRegistry


async def run_combat(
    step: CombatStep,
    player: "CharacterState",
    registry: "ContentRegistry",
    tui: TUICallbacks,
    run_outcome_branch: Callable[[OutcomeBranch], Awaitable[AdventureOutcome]],
    on_round_complete: Callable[[], Awaitable[None]] | None = None,
) -> AdventureOutcome:
    """Execute the turn-based combat loop.

    Player attacks first each round. Fleeing hands control to the on_flee branch
    immediately. If the enemy is defeated, the kill counter is incremented and
    on_win fires. If the player is reduced to 0 HP, on_defeat fires.

    Enemy HP is persisted in active_adventure.step_state so mid-combat state
    survives if Phase 3 needs to checkpoint a session between rounds.

    on_round_complete is called after both the player and enemy have resolved
    their attacks for the round (but before checking defeat / win conditions on
    the next iteration). This is the persistence hook used by GameSession.
    """
    enemy = registry.enemies.require(step.enemy, "Enemy")

    # Restore persisted enemy HP (e.g. after a save/restore) or start fresh.
    if player.active_adventure and "enemy_hp" in player.active_adventure.step_state:
        enemy_hp: int = int(player.active_adventure.step_state["enemy_hp"] or 0)
    else:
        enemy_hp = enemy.spec.hp
        if player.active_adventure:
            player.active_adventure.step_state["enemy_hp"] = enemy_hp

    while True:
        await tui.show_combat_round(
            player_hp=player.hp,
            enemy_hp=enemy_hp,
            player_name=player.name,
            enemy_name=enemy.spec.displayName,
        )
        action = await tui.show_menu("Your move:", ["Attack", "Flee"])

        if action == 2:  # Flee
            await run_outcome_branch(step.on_flee)
            return AdventureOutcome.FLED

        # Player attacks — strength reduces enemy defence
        strength = player.stats.get("strength", 10)
        player_damage = max(0, int(strength if isinstance(strength, (int, float)) else 10) - enemy.spec.defense)
        enemy_hp -= player_damage
        if player.active_adventure:
            player.active_adventure.step_state["enemy_hp"] = enemy_hp

        # Enemy attacks — player dexterity reduces incoming damage
        # (skip enemy retaliation when already dead so we don't subtract HP
        # from an enemy that the player just defeated this turn)
        if enemy_hp > 0:
            dexterity = player.stats.get("dexterity", 10)
            mitigation = int(dexterity if isinstance(dexterity, (int, float)) else 10) // 5
            incoming = max(0, enemy.spec.attack - mitigation)
            player.hp = max(0, player.hp - incoming)

        # Checkpoint after all HP changes for this round are committed.
        if on_round_complete is not None:
            await on_round_complete()

        if enemy_hp <= 0:
            player.statistics.record_enemy_defeated(step.enemy)
            await run_outcome_branch(step.on_win)
            return AdventureOutcome.COMPLETED

        if player.hp <= 0:
            await run_outcome_branch(step.on_defeat)
            return AdventureOutcome.DEFEATED
