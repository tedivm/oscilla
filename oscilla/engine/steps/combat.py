"""Combat step handler — turn-based fight loop with skill support."""

from __future__ import annotations

import time
from logging import getLogger
from typing import TYPE_CHECKING, Awaitable, Callable, Dict, List, Literal, Set

from oscilla.engine.combat_context import ActiveCombatEffect, CombatContext
from oscilla.engine.models.adventure import ApplyBuffEffect, CombatStep, ItemDropEffect, OutcomeBranch
from oscilla.engine.models.buff import StoredBuff
from oscilla.engine.pipeline import AdventureOutcome, TUICallbacks
from oscilla.engine.steps.effects import run_effect

if TYPE_CHECKING:
    from oscilla.engine.character import CharacterState
    from oscilla.engine.registry import ContentRegistry

logger = getLogger(__name__)


async def _tick_active_effects(
    ctx: CombatContext,
    player: "CharacterState",
    registry: "ContentRegistry",
    tui: TUICallbacks,
) -> None:
    """Fire per-turn effects for all active periodic effects, then expire finished ones.

    Called at the top of each combat round before the player acts.
    """
    expired: List[int] = []
    for i, ae in enumerate(ctx.active_effects):
        if ae.per_turn_effects:
            await tui.show_text(f"[italic]{ae.source_skill}[/italic] ticks ({ae.remaining_turns} turn(s) left).")
            for eff in ae.per_turn_effects:
                await run_effect(effect=eff, player=player, registry=registry, tui=tui, combat=ctx)
        ae.remaining_turns -= 1
        if ae.remaining_turns <= 0:
            expired.append(i)
    # Remove expired in reverse order to preserve indices.
    for i in reversed(expired):
        ctx.active_effects.pop(i)


def _apply_damage_amplify(base: int, target: Literal["player", "enemy"], ctx: CombatContext) -> int:
    """Scale outgoing damage by any damage_amplify modifiers active for target.

    All active damage_amplify modifiers for the named target are summed and applied
    as a single multiplicative bonus: base * (1 + total_percent / 100).
    """
    total = sum(
        m.percent
        for ae in ctx.active_effects
        for m in ae.modifiers
        if m.type == "damage_amplify" and m.target == target
        if isinstance(m.percent, int)
    )
    if total <= 0:
        return base
    return int(base * (1 + total / 100))


def _apply_incoming_modifiers(base: int, target: Literal["player", "enemy"], ctx: CombatContext) -> int:
    """Apply damage_reduction and damage_vulnerability modifiers to incoming damage for target.

    Reductions and vulnerabilities are summed independently, then combined:
        factor = max(0.0, 1.0 - (total_reduction / 100) + (total_vulnerability / 100))
    If base > 0 the result is at minimum 1 (no hit is silently absorbed unless base was 0).
    """
    net_reduction = sum(
        m.percent
        for ae in ctx.active_effects
        for m in ae.modifiers
        if m.type == "damage_reduction" and m.target == target
        if isinstance(m.percent, int)
    )
    net_vuln = sum(
        m.percent
        for ae in ctx.active_effects
        for m in ae.modifiers
        if m.type == "damage_vulnerability" and m.target == target
        if isinstance(m.percent, int)
    )
    factor = max(0.0, 1.0 - net_reduction / 100 + net_vuln / 100)
    if base <= 0:
        return 0
    return max(1, int(base * factor))


async def _apply_reflect(
    taken: int,
    target: Literal["player", "enemy"],
    ctx: CombatContext,
    player: "CharacterState",
    tui: TUICallbacks,
) -> None:
    """Reflect a portion of damage taken back to the attacker.

    Sums all damage_reflect modifiers active for target and reflects that
    percentage of `taken` damage onto the opposing side.
    """
    total_reflect = sum(
        m.percent
        for ae in ctx.active_effects
        for m in ae.modifiers
        if m.type == "damage_reflect" and m.target == target
        if isinstance(m.percent, int)
    )
    if total_reflect <= 0 or taken <= 0:
        return
    reflected = max(1, int(taken * total_reflect / 100))
    if target == "player":
        # Player has thorns — attacker (enemy) takes the reflected damage.
        ctx.enemy_hp = max(0, ctx.enemy_hp - reflected)
        await tui.show_text(f"[yellow]Thorns! {reflected} damage reflected to the enemy.[/yellow]")
    else:
        # Enemy has thorns — attacker (player) takes the reflected damage.
        player.set_stat(name="hp", value=max(0, int(player.stats.get("hp") or 0) - reflected))
        await tui.show_text(f"[yellow]{reflected} damage reflected back at you![/yellow]")


async def _use_skill_in_combat(
    skill_ref: str,
    ctx: CombatContext,
    player: "CharacterState",
    registry: "ContentRegistry",
    tui: TUICallbacks,
) -> bool:
    """Attempt to activate a skill during combat. Returns True if the skill fired.

    Validates cooldown, resource cost, and activation condition before firing.
    """
    skill = registry.skills.get(skill_ref)
    if skill is None:
        await tui.show_text(f"[red]Error: skill {skill_ref!r} not found in registry.[/red]")
        return False

    spec = skill.spec

    # Turn-scope cooldown check.
    if spec.cooldown is not None and spec.cooldown.scope == "turn":
        last_used = ctx.skill_uses_this_combat.get(skill_ref, 0)
        turns_required = spec.cooldown.turns
        if isinstance(turns_required, str):
            try:
                turns_required = int(turns_required)
            except (ValueError, TypeError):
                turns_required = 0
        if turns_required is None:
            turns_required = 0
        if last_used > 0 and (ctx.turn_number - last_used) < turns_required:
            remaining = turns_required - (ctx.turn_number - last_used)
            await tui.show_text(f"[yellow]{spec.displayName} is on cooldown ({remaining} turn(s) remaining).[/yellow]")
            return False

    # Adventure-scope cooldown check.
    from oscilla.engine.actions import _skill_on_cooldown

    if spec.cooldown is not None and spec.cooldown.scope != "turn":
        if _skill_on_cooldown(player=player, skill_ref=skill_ref):
            await tui.show_text(f"[yellow]{spec.displayName} is on cooldown.[/yellow]")
            return False

    # Resource cost check.
    if spec.cost is not None:
        current = player.stats.get(spec.cost.stat, 0)
        if not isinstance(current, int) or isinstance(current, bool):
            await tui.show_text(f"[red]Error: resource stat {spec.cost.stat!r} is not numeric.[/red]")
            return False
        if current < spec.cost.amount:
            await tui.show_text(
                f"[red]Not enough {spec.cost.stat} to use {spec.displayName} "
                f"(need {spec.cost.amount}, have {current}).[/red]"
            )
            return False

    # Activation condition check.
    from oscilla.engine.conditions import evaluate

    if not evaluate(condition=spec.requires, player=player, registry=registry):
        await tui.show_text(f"[red]You cannot use {spec.displayName} right now.[/red]")
        return False

    # All checks passed — deduct resource cost.
    if spec.cost is not None:
        old = int(player.stats.get(spec.cost.stat) or 0)
        player.set_stat(name=spec.cost.stat, value=old - spec.cost.amount)

    # Record use for cooldown tracking.
    if spec.cooldown is not None:
        if spec.cooldown.scope == "turn":
            ctx.skill_uses_this_combat[skill_ref] = ctx.turn_number
        else:  # adventure-scope — persist via tick/real expiry
            from oscilla.engine.actions import _set_skill_cooldown

            _set_skill_cooldown(player=player, skill_ref=skill_ref, cooldown=spec.cooldown)

    # Dispatch immediate use_effects (including any apply_buff effects).
    await tui.show_text(f"You use [bold]{spec.displayName}[/bold]!")
    for eff in spec.use_effects:
        await run_effect(effect=eff, player=player, registry=registry, tui=tui, combat=ctx)

    return True


async def _enemy_skill_phase(
    ctx: CombatContext,
    player: "CharacterState",
    registry: "ContentRegistry",
    tui: TUICallbacks,
) -> None:
    """Check and fire any enemy skills whose use_every_n_turns threshold is met.

    Called at the end of each round, after the enemy's basic attack.
    Skills with use_every_n_turns=0 are never auto-fired.
    """
    enemy = registry.enemies.require(ctx.enemy_ref, "Enemy")
    for skill_entry in enemy.spec.skills:
        n = skill_entry.use_every_n_turns
        if n == 0:
            continue
        if ctx.turn_number % n == 0:
            skill = registry.skills.get(skill_entry.skill_ref)
            if skill is None:
                logger.warning("Enemy skill ref %r not found in registry — skipping.", skill_entry.skill_ref)
                continue
            spec = skill.spec

            # Resource check for enemy.
            if spec.cost is not None:
                available = ctx.enemy_resources.get(spec.cost.stat, 0)
                if available < spec.cost.amount:
                    continue  # Not enough resource; skip silently.
                ctx.enemy_resources[spec.cost.stat] = available - spec.cost.amount

            await tui.show_text(f"[bold]{enemy.spec.displayName}[/bold] uses [italic]{spec.displayName}[/italic]!")
            for eff in spec.use_effects:
                await run_effect(effect=eff, player=player, registry=registry, tui=tui, combat=ctx)


async def run_combat(
    step: CombatStep,
    player: "CharacterState",
    registry: "ContentRegistry",
    tui: TUICallbacks,
    run_outcome_branch: Callable[[OutcomeBranch], Awaitable[AdventureOutcome]],
    on_round_complete: Callable[[], Awaitable[None]] | None = None,
) -> AdventureOutcome:
    """Execute the turn-based combat loop with skill support.

    Player acts first each round. Fleeing hands control to on_flee immediately.
    CombatContext is constructed here and passed to all sub-functions — it is
    never serialized. Enemy HP is still mirrored to step_state each round for
    persistence compatibility with the existing save/restore path.

    on_round_complete is called after all HP changes for the round are committed.
    This is the persistence hook used by GameSession.
    """
    enemy = registry.enemies.require(step.enemy, "Enemy")

    # Restore or initialize enemy HP.
    if player.active_adventure and "enemy_hp" in player.active_adventure.step_state:
        initial_hp: int = int(player.active_adventure.step_state["enemy_hp"] or 0)
    else:
        initial_hp = enemy.spec.hp
        if player.active_adventure:
            player.active_adventure.step_state["enemy_hp"] = initial_hp

    ctx = CombatContext(
        enemy_hp=initial_hp,
        enemy_ref=step.enemy,
        enemy_resources=dict(enemy.spec.skill_resources),
    )

    # Sweep and re-inject persistent buffs from CharacterState.
    now_ts = int(time.time())
    player.sweep_expired_buffs(
        now_tick=player.internal_ticks,
        now_game_tick=player.game_ticks,
        now_ts=now_ts,
    )
    # Track all buff refs injected from StoredBuff; needed for correct writeback even when
    # a buff expires during combat and is removed from ctx.active_effects before the loop ends.
    injected_persistent_refs: Set[str] = set()
    for stored in player.active_buffs:
        buff_manifest = registry.buffs.get(stored.buff_ref)
        if buff_manifest is None:
            logger.warning(
                "Stored buff %r not found in registry at combat start — skipping.",
                stored.buff_ref,
            )
            continue
        spec = buff_manifest.spec
        resolved_vars: Dict[str, int] = {**spec.variables, **stored.variables}
        resolved_modifiers = [
            mod.model_copy(
                update={"percent": resolved_vars.get(mod.percent, 0) if isinstance(mod.percent, str) else mod.percent}
            )
            for mod in spec.modifiers
        ]
        ae = ActiveCombatEffect(
            source_skill=buff_manifest.metadata.name,
            target="player",
            remaining_turns=stored.remaining_turns,
            per_turn_effects=list(spec.per_turn_effects),
            modifiers=resolved_modifiers,
            label=stored.buff_ref,
            exclusion_group=spec.exclusion_group or "",
            priority=resolved_vars.get(spec.priority, 0) if isinstance(spec.priority, str) else int(spec.priority),
            exclusion_mode=spec.exclusion_mode,
            is_persistent=True,
            variables=dict(resolved_vars),
        )
        ctx.active_effects.append(ae)
        injected_persistent_refs.add(stored.buff_ref)

    # Apply combat-entry buffs granted by equipped and held items.
    equipped_refs: Set[str] = {
        inst.item_ref for inst in player.instances if inst.instance_id in player.equipment.values()
    }
    for item_ref in equipped_refs:
        item_m = registry.items.get(item_ref)
        if item_m is not None:
            for grant in item_m.spec.grants_buffs_equipped:
                await run_effect(
                    effect=ApplyBuffEffect(
                        type="apply_buff",
                        buff_ref=grant.buff_ref,
                        target="player",
                        variables=grant.variables,
                    ),
                    player=player,
                    registry=registry,
                    tui=tui,
                    combat=ctx,
                )
    held_refs: Set[str] = {inst.item_ref for inst in player.instances} | set(player.stacks.keys())
    for item_ref in held_refs:
        item_m = registry.items.get(item_ref)
        if item_m is not None:
            for grant in item_m.spec.grants_buffs_held:
                await run_effect(
                    effect=ApplyBuffEffect(
                        type="apply_buff",
                        buff_ref=grant.buff_ref,
                        target="player",
                        variables=grant.variables,
                    ),
                    player=player,
                    registry=registry,
                    tui=tui,
                    combat=ctx,
                )

    # Determine which skills the player can use in combat.
    combat_skills: List[str] = [
        skill_ref
        for skill_ref in player.available_skills(registry=registry)
        if (s := registry.skills.get(skill_ref)) is not None and "combat" in s.spec.contexts
    ]

    outcome: AdventureOutcome = AdventureOutcome.COMPLETED  # default; set by break statements

    while True:
        # Tick periodic effects at the top of each round.
        await _tick_active_effects(ctx=ctx, player=player, registry=registry, tui=tui)

        await tui.show_combat_round(
            player_hp=int(player.stats.get("hp") or 0),
            enemy_hp=ctx.enemy_hp,
            player_name=player.name,
            enemy_name=enemy.spec.displayName,
        )

        # Build action menu: Attack always first, then skills, then Flee last.
        menu_options: List[str] = ["Attack"]
        skill_indices: List[str] = []  # parallel to skill menu slots
        if combat_skills:
            for skill_ref in combat_skills:
                skill = registry.skills.get(skill_ref)
                if skill is not None:
                    menu_options.append(f"Skill: {skill.spec.displayName}")
                    skill_indices.append(skill_ref)
        menu_options.append("Flee")
        flee_index = len(menu_options)  # 1-based

        action = await tui.show_menu("Your move:", menu_options)

        if action == flee_index:
            await run_outcome_branch(step.on_flee)
            outcome = AdventureOutcome.FLED
            break

        if action == 1:
            # Standard attack — strength reduces enemy defence.
            strength = player.stats.get("strength", 10)
            base_damage = max(0, int(strength if isinstance(strength, (int, float)) else 10) - enemy.spec.defense)
            # Apply any damage_amplify modifiers active on the player.
            player_damage = _apply_damage_amplify(base=base_damage, target="player", ctx=ctx)
            if player_damage > 0:
                await tui.show_text(f"You attack for {player_damage} damage!")
            ctx.enemy_hp = max(0, ctx.enemy_hp - player_damage)
        elif 2 <= action < flee_index:
            # Skill use: action 2 → skill_indices[0], etc.
            skill_ref = skill_indices[action - 2]
            await _use_skill_in_combat(skill_ref=skill_ref, ctx=ctx, player=player, registry=registry, tui=tui)

        # Persist enemy HP in step_state for save/restore.
        if player.active_adventure:
            player.active_adventure.step_state["enemy_hp"] = ctx.enemy_hp

        # Enemy retaliation — only when still alive.
        if ctx.enemy_hp > 0:
            dexterity = player.stats.get("dexterity", 10)
            mitigation = int(dexterity if isinstance(dexterity, (int, float)) else 10) // 5
            raw_incoming = max(0, enemy.spec.attack - mitigation)
            # Apply damage_reduction and damage_vulnerability modifiers active on the player.
            incoming = _apply_incoming_modifiers(base=raw_incoming, target="player", ctx=ctx)
            if incoming > 0:
                await tui.show_text(f"{enemy.spec.displayName} attacks for {incoming} damage!")
            player.set_stat(name="hp", value=max(0, int(player.stats.get("hp") or 0) - incoming))
            # Reflect a portion of incoming damage back to the enemy if player has thorns.
            await _apply_reflect(taken=incoming, target="player", ctx=ctx, player=player, tui=tui)

        # Enemy skill phase (periodic / scheduled skill use).
        await _enemy_skill_phase(ctx=ctx, player=player, registry=registry, tui=tui)

        ctx.turn_number += 1

        # Checkpoint after all HP changes for this round are committed.
        if on_round_complete is not None:
            await on_round_complete()

        if ctx.enemy_hp <= 0:
            player.statistics.record_enemy_defeated(step.enemy)
            # Automatically apply the enemy's own loot groups before the on_win branch.
            if enemy.spec.loot:
                loot_effect = ItemDropEffect(type="item_drop", groups=enemy.spec.loot)
                await run_effect(effect=loot_effect, player=player, registry=registry, tui=tui)
            await run_outcome_branch(step.on_win)
            outcome = AdventureOutcome.COMPLETED
            break

        if (player.stats.get("hp") or 0) <= 0:
            await run_outcome_branch(step.on_defeat)
            outcome = AdventureOutcome.DEFEATED
            break

    # Write back persistent buffs to CharacterState after combat.
    # Buffs that still have remaining turns are updated; exhausted buffs are removed.
    # Use injected_persistent_refs (not just currently active) so buffs that expired
    # during combat (ticked to 0 and already popped) are also cleared from active_buffs.
    player.active_buffs = [sb for sb in player.active_buffs if sb.buff_ref not in injected_persistent_refs]
    for ae in ctx.active_effects:
        if ae.is_persistent and ae.remaining_turns > 0:
            player.active_buffs.append(
                StoredBuff(
                    buff_ref=ae.label,
                    remaining_turns=ae.remaining_turns,
                    variables=dict(ae.variables),
                )
            )

    return outcome
