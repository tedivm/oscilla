"""Effect dispatcher — applies mechanical outcomes to player state and notifies the TUI."""

from __future__ import annotations

import random
from collections import Counter
from logging import getLogger
from typing import TYPE_CHECKING, Dict, List

from oscilla.engine.character import _INT64_MAX, _INT64_MIN, cascade_unequip_invalid
from oscilla.engine.combat_context import ActiveCombatEffect, CombatContext
from oscilla.engine.models.adventure import (
    ApplyBuffEffect,
    DispelEffect,
    Effect,
    EndAdventureEffect,
    HealEffect,
    ItemDropEffect,
    MilestoneGrantEffect,
    QuestActivateEffect,
    QuestFailEffect,
    SetPronounsEffect,
    SkillGrantEffect,
    StatChangeEffect,
    StatSetEffect,
    UseItemEffect,
    XpGrantEffect,
)
from oscilla.engine.signals import _EndSignal

if TYPE_CHECKING:
    from oscilla.engine.character import CharacterState
    from oscilla.engine.models.loot_table import LootEntry
    from oscilla.engine.pipeline import TUICallbacks
    from oscilla.engine.registry import ContentRegistry
    from oscilla.engine.templates import ExpressionContext

logger = getLogger(__name__)


def _resolve_stat_bounds(stat: str, registry: "ContentRegistry") -> tuple[int, int]:
    """Return the effective (min, max) bounds for a named stat.

    Looks up the stat in the registry's CharacterConfig.  If no CharacterConfig
    is loaded, or the stat has no explicit bounds, defaults to INT64_MIN/MAX.
    """
    char_config = registry.character_config
    if char_config is None:
        return _INT64_MIN, _INT64_MAX
    all_stats = char_config.spec.public_stats + char_config.spec.hidden_stats
    for stat_def in all_stats:
        if stat_def.name == stat:
            if stat_def.bounds is None:
                return _INT64_MIN, _INT64_MAX
            lo = stat_def.bounds.min if stat_def.bounds.min is not None else _INT64_MIN
            hi = stat_def.bounds.max if stat_def.bounds.max is not None else _INT64_MAX
            return lo, hi
    return _INT64_MIN, _INT64_MAX


def _resolve_loot_list(
    effect: ItemDropEffect,
    registry: "ContentRegistry",
) -> "List[LootEntry]":
    """Return the effective loot entry list for an ItemDropEffect.

    Precondition: the loader has already validated that every loot_ref resolves
    to a known table or enemy (_validate_loot_refs). An unresolvable ref here
    indicates a programming error or a hot-reload race — assert rather than
    silently skip.
    """

    if effect.loot is not None:
        return effect.loot
    # loot_ref path — guaranteed resolvable by load-time validation.
    assert effect.loot_ref is not None
    entries = registry.resolve_loot_entries(effect.loot_ref)
    assert entries is not None, (
        f"loot_ref {effect.loot_ref!r} not found at runtime — "
        "this should have been caught by _validate_loot_refs at load time."
    )
    return entries


async def run_effect(
    effect: Effect,
    player: "CharacterState",
    registry: "ContentRegistry",
    tui: "TUICallbacks",
    combat: "CombatContext | None" = None,
    ctx: "ExpressionContext | None" = None,
) -> None:
    """Dispatch a single effect to its handler.

    combat must be provided for any effect with target="enemy". When absent and
    target="enemy" is requested, a warning is logged and the effect is skipped
    rather than crashing — this can occur if a skill with combat-only effects is
    somehow invoked outside combat.
    """
    # Resolve any template strings in numeric fields before dispatch.
    if registry.template_engine is not None:
        from oscilla.engine.templates import ExpressionContext, PlayerContext

        if ctx is None:
            ctx = ExpressionContext(player=PlayerContext.from_character(player))
        engine = registry.template_engine

        if isinstance(effect, XpGrantEffect) and isinstance(effect.amount, str):
            template_id = f"__effect_xp_{id(effect)}"
            resolved_amount = engine.render_int(template_id, ctx)
            effect = XpGrantEffect(type="xp_grant", amount=resolved_amount)

        elif isinstance(effect, StatChangeEffect) and isinstance(effect.amount, str):
            template_id = f"__effect_statchange_{id(effect)}"
            resolved_amount = engine.render_int(template_id, ctx)
            effect = StatChangeEffect(
                type="stat_change",
                stat=effect.stat,
                amount=resolved_amount,
                target=effect.target,
            )

        elif isinstance(effect, ItemDropEffect) and isinstance(effect.count, str):
            template_id = f"__effect_itemdrop_{id(effect)}"
            resolved_count = engine.render_int(template_id, ctx)
            # Preserve whichever loot source was declared (inline or ref).
            effect = ItemDropEffect(
                type="item_drop",
                count=resolved_count,
                loot=effect.loot,
                loot_ref=effect.loot_ref,
            )

    match effect:
        case XpGrantEffect(amount=amount):
            # String amounts are resolved to int by template resolution above.
            assert isinstance(amount, int), f"Unexpected non-int XP amount after template resolution: {amount!r}"
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

        case ItemDropEffect(count=count) if isinstance(count, int):
            loot_entries = _resolve_loot_list(effect=effect, registry=registry)
            weights = [entry.weight for entry in loot_entries]
            # Roll independently count times with replacement.
            chosen_entries = random.choices(population=loot_entries, weights=weights, k=count)
            for entry in chosen_entries:
                player.add_item(ref=entry.item, quantity=entry.quantity, registry=registry)
            # Announce grouped findings.
            item_totals: Counter[str] = Counter()
            for entry in chosen_entries:
                item_totals[entry.item] += entry.quantity
            parts = []
            for item_ref, total_qty in item_totals.items():
                item = registry.items.get(item_ref)
                name = item.spec.displayName if item is not None else item_ref
                parts.append(f"{name} \u00d7 {total_qty}" if total_qty > 1 else name)
            await tui.show_text(f"You found: {', '.join(parts)}")

        case MilestoneGrantEffect(milestone=milestone):
            player.grant_milestone(milestone)
            # Quest stage advancement is evaluated after every milestone grant.
            # This is the primary runtime trigger for quest progression.
            from oscilla.engine.quest_engine import evaluate_quest_advancements

            await evaluate_quest_advancements(player=player, registry=registry, tui=tui)

        case QuestActivateEffect(quest_ref=quest_ref):
            if quest_ref in player.completed_quests:
                logger.warning("quest_activate: %r is already completed — no-op.", quest_ref)
                return
            if quest_ref in player.active_quests:
                logger.warning("quest_activate: %r is already active — no-op.", quest_ref)
                return
            quest_manifest = registry.quests.get(quest_ref)
            if quest_manifest is None:
                logger.error("quest_activate: quest %r not found in registry — skipping.", quest_ref)
                await tui.show_text(f"[red]Error: quest {quest_ref!r} not found.[/red]")
                return
            entry_stage = quest_manifest.spec.entry_stage
            player.active_quests[quest_ref] = entry_stage
            display_name = quest_manifest.spec.displayName
            await tui.show_text(f"[bold]Quest started:[/bold] {display_name}")
            # Immediately evaluate advancement — the entry stage might already be
            # satisfiable if the player already holds any advance_on milestones.
            from oscilla.engine.quest_engine import evaluate_quest_advancements

            await evaluate_quest_advancements(player=player, registry=registry, tui=tui)

        case EndAdventureEffect(outcome=outcome):
            raise _EndSignal(outcome)

        case HealEffect(amount=amount, target=target):
            if target == "enemy":
                if combat is None:
                    logger.warning("heal with target='enemy' called outside combat — skipping effect.")
                    return
                if amount == "full":
                    # Enemy max_hp is not tracked; log warning and skip.
                    logger.warning("heal target='enemy' with amount='full' is not supported — skipping.")
                    return
                combat.enemy_hp = max(0, combat.enemy_hp + int(amount))
                await tui.show_text(f"Enemy healed for {amount}. (Enemy HP: {combat.enemy_hp})")
                return
            # — player target (original logic) —
            before_hp = player.hp
            if amount == "full":
                player.hp = player.max_hp
            else:
                player.hp = min(player.hp + int(amount), player.max_hp)
            healed = player.hp - before_hp
            if healed > 0:
                await tui.show_text(f"Restored {healed} HP. (HP: {player.hp} / {player.max_hp})")

        case StatChangeEffect(stat=stat, amount=amount, target=target):
            # String amounts are resolved to int by template resolution above.
            assert isinstance(amount, int), (
                f"Unexpected non-int stat change amount after template resolution: {amount!r}"
            )
            if target == "enemy":
                if combat is None:
                    logger.warning("stat_change with target='enemy' called outside combat — skipping effect.")
                    return
                combat.enemy_hp += amount
                # Enemy HP floor is 0.
                combat.enemy_hp = max(0, combat.enemy_hp)
                action = "damaged" if amount < 0 else "healed"
                await tui.show_text(f"Enemy {action} for {abs(amount)}. (Enemy HP: {combat.enemy_hp})")
                return
            # — player target (original logic) —
            if stat not in player.stats:
                await tui.show_text(f"[red]Error: stat {stat!r} not found[/red]")
                return
            old_value = player.stats[stat]
            # bool is a subclass of int; the isinstance guard keeps bool stats blocked.
            if not isinstance(old_value, int) or isinstance(old_value, bool):
                await tui.show_text(f"[red]Error: cannot change non-numeric stat {stat!r}[/red]")
                return
            raw_new = old_value + amount
            lo, hi = _resolve_stat_bounds(stat=stat, registry=registry)
            new_value = max(lo, min(hi, raw_new))
            if new_value != raw_new:
                logger.warning(
                    "stat_change on %r: attempted %d, clamped to %d (bounds %d..%d).",
                    stat,
                    raw_new,
                    new_value,
                    lo,
                    hi,
                )
                await tui.show_text(
                    f"[yellow]Warning: stat {stat!r} clamped to {new_value} (attempted {raw_new}).[/yellow]"
                )
            player.set_stat(name=stat, value=new_value)
            await tui.show_text(f"Changed {stat}: {old_value} → {new_value}")
            # Cascade-unequip items whose requirements are no longer satisfied.
            displaced = cascade_unequip_invalid(player=player, registry=registry)
            for name in displaced:
                await tui.show_text(f"[yellow]⚠ {name} unequipped: requirements no longer met.[/yellow]")

        case StatSetEffect(stat=stat, value=value):
            if stat not in player.stats:
                await tui.show_text(f"[red]Error: stat {stat!r} not found[/red]")
                return
            old_value = player.stats[stat]
            # bool set — bypass integer bounds entirely; True/False are always valid.
            if isinstance(value, bool):
                player.stats[stat] = value
                await tui.show_text(f"Set {stat}: {old_value} → {value}")
                displaced = cascade_unequip_invalid(player=player, registry=registry)
                for name in displaced:
                    await tui.show_text(f"[yellow]⚠ {name} unequipped: requirements no longer met.[/yellow]")
                return
            if value is None:
                player.stats[stat] = None
                await tui.show_text(f"Set {stat}: {old_value} → None")
                displaced = cascade_unequip_invalid(player=player, registry=registry)
                for name in displaced:
                    await tui.show_text(f"[yellow]⚠ {name} unequipped: requirements no longer met.[/yellow]")
                return
            lo, hi = _resolve_stat_bounds(stat=stat, registry=registry)
            clamped = max(lo, min(hi, value))
            if clamped != value:
                logger.warning(
                    "stat_set on %r: attempted %d, clamped to %d (bounds %d..%d).",
                    stat,
                    value,
                    clamped,
                    lo,
                    hi,
                )
                await tui.show_text(
                    f"[yellow]Warning: stat {stat!r} clamped to {clamped} (attempted {value}).[/yellow]"
                )
            player.set_stat(name=stat, value=clamped)
            await tui.show_text(f"Set {stat}: {old_value} → {clamped}")
            # Cascade-unequip items whose requirements are no longer satisfied.
            displaced = cascade_unequip_invalid(player=player, registry=registry)
            for name in displaced:
                await tui.show_text(f"[yellow]⚠ {name} unequipped: requirements no longer met.[/yellow]")

        case UseItemEffect(item=item_ref):
            item = registry.items.get(item_ref)
            if item is None:
                await tui.show_text(f"[red]Error: item {item_ref!r} not found[/red]")
                return

            # Verify the player has the item (stackable) or an instance of it
            if item.spec.stackable:
                if player.stacks.get(item_ref, 0) == 0:
                    await tui.show_text(f"[red]You do not have {item.spec.displayName}.[/red]")
                    return
            else:
                instance = next((inst for inst in player.instances if inst.item_ref == item_ref), None)
                if instance is None:
                    await tui.show_text(f"[red]You do not have {item.spec.displayName}.[/red]")
                    return

            await tui.show_text(f"You use {item.spec.displayName}.")

            # Apply use_effects
            for sub_effect in item.spec.use_effects:
                await run_effect(effect=sub_effect, player=player, registry=registry, tui=tui, combat=combat)

            # Decrement charges if the item has a charge counter.
            if not item.spec.stackable and item.spec.charges is not None:
                instance = next((inst for inst in player.instances if inst.item_ref == item_ref), None)
                if instance is not None and instance.charges_remaining is not None:
                    instance.charges_remaining -= 1
                    if instance.charges_remaining <= 0:
                        player.remove_instance(instance_id=instance.instance_id)
                        await tui.show_text(f"[yellow]{item.spec.displayName} has been used up.[/yellow]")

            # Consume the item if configured
            if item.spec.consumed_on_use:
                if item.spec.stackable:
                    player.remove_item(ref=item_ref, quantity=1)
                else:
                    instance = next((inst for inst in player.instances if inst.item_ref == item_ref), None)
                    if instance is not None:
                        player.remove_instance(instance_id=instance.instance_id)

        case SkillGrantEffect(skill=skill_ref):
            granted = player.grant_skill(skill_ref=skill_ref, registry=registry)
            if granted:
                skill = registry.skills.get(skill_ref)
                name = skill.spec.displayName if skill is not None else skill_ref
                await tui.show_text(f"You learned: {name}!")
            # Already-known — silent no-op (grant_skill returns False)

        case DispelEffect(label=label, target=target):
            if combat is None:
                # Outside combat there are no active effects to remove.
                logger.debug("dispel(%r) called outside combat — no-op.", label)
                return
            before = len(combat.active_effects)
            combat.active_effects = [
                ae for ae in combat.active_effects if not (ae.label == label and ae.target == target)
            ]
            removed = before - len(combat.active_effects)
            if removed > 0:
                await tui.show_text(f"[green]{removed} effect(s) with label {label!r} dispelled.[/green]")
            else:
                logger.debug("dispel(%r): no matching active effects found.", label)

        case ApplyBuffEffect(buff_ref=buff_ref, target=buff_target, variables=call_vars):
            if combat is None:
                # Buffs only make sense inside the combat turn loop.
                logger.warning("apply_buff(%r) called outside combat — skipping.", buff_ref)
                return
            buff_manifest = registry.buffs.get(buff_ref)
            if buff_manifest is None:
                logger.error("apply_buff: buff ref %r not found in registry — skipping.", buff_ref)
                await tui.show_text(f"[red]Error: buff {buff_ref!r} not found.[/red]")
                return
            spec = buff_manifest.spec
            # Merge manifest variable defaults with call-site overrides.
            resolved_vars: Dict[str, int] = {**spec.variables, **call_vars}

            def _resolve_percent(v: int | str) -> int:
                """Resolve a modifier percent — either a literal int or a variable name."""
                if isinstance(v, int):
                    return v
                if v in resolved_vars:
                    return resolved_vars[v]
                # Should never reach here when load-time validation passes.
                logger.error("apply_buff: variable %r not in resolved_vars — using 0.", v)
                return 0

            # Build resolved modifier copies with concrete int percent values.
            resolved_modifiers = [
                mod.model_copy(update={"percent": _resolve_percent(mod.percent)}) for mod in spec.modifiers
            ]

            # Buff manifest name is used as the stable label for DispelEffect matching.
            combat.active_effects.append(
                ActiveCombatEffect(
                    source_skill=buff_manifest.metadata.name,
                    target=buff_target,
                    remaining_turns=spec.duration_turns,
                    per_turn_effects=list(spec.per_turn_effects),
                    modifiers=resolved_modifiers,
                    label=buff_manifest.metadata.name,
                )
            )
            await tui.show_text(f"[bold]{spec.displayName}[/bold] applied for {spec.duration_turns} turn(s).")

        case QuestFailEffect(quest_ref=quest_ref):
            if quest_ref not in player.active_quests:
                logger.warning("quest_fail: quest %r is not active — no-op.", quest_ref)
                return
            quest_manifest = registry.quests.get(quest_ref)
            if quest_manifest is None:
                logger.error("quest_fail: quest %r not found in registry — skipping.", quest_ref)
                await tui.show_text(f"[red]Error: quest {quest_ref!r} not found.[/red]")
                return
            stage_name = player.active_quests.pop(quest_ref)
            player.failed_quests.add(quest_ref)
            display_name = quest_manifest.spec.displayName
            await tui.show_text(f"[bold red]Quest failed: {display_name}[/bold red]")
            # Run fail_effects from the stage that was active at the time of failure.
            stage_map = {s.name: s for s in quest_manifest.spec.stages}
            stage = stage_map.get(stage_name)
            if stage is not None:
                for eff in stage.fail_effects:
                    await run_effect(effect=eff, player=player, registry=registry, tui=tui, combat=combat)

        case SetPronounsEffect(set=pronoun_key):
            from oscilla.engine.templates import resolve_pronoun_set

            ps = resolve_pronoun_set(key=pronoun_key, registry=registry)
            if ps is None:
                logger.warning("set_pronouns: unknown pronoun set key %r — skipping.", pronoun_key)
                await tui.show_text(f"[red]Error: unknown pronoun set {pronoun_key!r}[/red]")
                return
            player.pronouns = ps
            await tui.show_text(f"Pronouns set to {pronoun_key}.")
