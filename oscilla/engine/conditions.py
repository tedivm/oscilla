"""Condition evaluator — pure recursive evaluation of condition trees against player state."""

from __future__ import annotations

from logging import getLogger
from typing import TYPE_CHECKING

from oscilla.engine.models.base import (
    AdventuresCompletedCondition,
    AllCondition,
    AnyCondition,
    AnyItemEquippedCondition,
    CharacterStatCondition,
    ClassCondition,
    Condition,
    EnemiesDefeatedCondition,
    ItemCondition,
    ItemEquippedCondition,
    ItemHeldLabelCondition,
    LevelCondition,
    LocationsVisitedCondition,
    MilestoneCondition,
    NotCondition,
    PrestigeCountCondition,
    PronounsCondition,
    SkillCondition,
)

if TYPE_CHECKING:
    from oscilla.engine.character import CharacterState
    from oscilla.engine.registry import ContentRegistry

logger = getLogger(__name__)


def evaluate(
    condition: Condition | None,
    player: "CharacterState",
    registry: "ContentRegistry | None" = None,
    exclude_item: str | None = None,
) -> bool:
    """Evaluate a condition tree against the given player state.

    Returns True if condition is None (no gate) or every node evaluates to True.
    Pass registry to enable equipment-aware stat evaluation via effective_stats().

    exclude_item: when set, the named item's stat bonuses are excluded from
    effective_stats() lookups. Used for the self-justification guard when
    evaluating EquipSpec.requires.
    """
    if condition is None:
        return True

    match condition:
        # --- Branch nodes ---
        case AllCondition(conditions=children):
            return all(evaluate(c, player, registry, exclude_item) for c in children)
        case AnyCondition(conditions=children):
            return any(evaluate(c, player, registry, exclude_item) for c in children)
        case NotCondition(condition=child):
            return not evaluate(child, player, registry, exclude_item)

        # --- Player attribute leaves ---
        case LevelCondition(value=v):
            return player.level >= v
        case MilestoneCondition(name=n):
            return n in player.milestones
        case ItemCondition(name=n):
            # Fixed: check both stackable items and non-stackable instances.
            in_stacks = player.stacks.get(n, 0) > 0
            in_instances = any(inst.item_ref == n for inst in player.instances)
            return in_stacks or in_instances
        case ClassCondition():
            # No-op in v1: class mechanics are a placeholder; every class always passes.
            return True
        case PrestigeCountCondition() as c:
            return _numeric_compare(player.iteration, c)

        # --- Item equipment/label predicates ---
        case ItemEquippedCondition(name=n):
            # True when the named non-stackable item is currently in an equipment slot.
            equipped_ids = set(player.equipment.values())
            return any(inst.item_ref == n and inst.instance_id in equipped_ids for inst in player.instances)
        case ItemHeldLabelCondition(label=lbl):
            # True when any held item (stack or instance) has the given label.
            if registry is None:
                logger.warning("item_held_label condition on %r requires registry — evaluating False.", lbl)
                return False
            for item_ref in player.stacks:
                item = registry.items.get(item_ref)
                if item is not None and lbl in item.spec.labels:
                    return True
            for inst in player.instances:
                item = registry.items.get(inst.item_ref)
                if item is not None and lbl in item.spec.labels:
                    return True
            return False
        case AnyItemEquippedCondition(label=lbl):
            # True when any equipped item instance has the given label.
            if registry is None:
                logger.warning("any_item_equipped condition on %r requires registry — evaluating False.", lbl)
                return False
            equipped_ids = set(player.equipment.values())
            for inst in player.instances:
                if inst.instance_id not in equipped_ids:
                    continue
                item = registry.items.get(inst.item_ref)
                if item is not None and lbl in item.spec.labels:
                    return True
            return False

        # --- CharacterConfig stat leaves ---
        case CharacterStatCondition(name=n, stat_source=stat_source) as c:
            # Use base stats when stat_source is "base" or registry is unavailable.
            if stat_source == "base" or registry is None:
                stats = player.stats
            else:
                stats = player.effective_stats(registry=registry, exclude_item=exclude_item)
            value = stats.get(n, 0)
            # Stats may be bool; only numeric stats are comparable.
            if not isinstance(value, int):
                logger.warning(
                    "character_stat condition on non-numeric stat %r (value=%r); treating as 0",
                    n,
                    value,
                )
                return _numeric_compare(0, c)
            return _numeric_compare(value, c)

        # --- Statistics leaves ---
        case EnemiesDefeatedCondition(name=n) as c:
            return _numeric_compare(player.statistics.enemies_defeated.get(n, 0), c)
        case LocationsVisitedCondition(name=n) as c:
            return _numeric_compare(player.statistics.locations_visited.get(n, 0), c)
        case AdventuresCompletedCondition(name=n) as c:
            return _numeric_compare(player.statistics.adventures_completed.get(n, 0), c)

        # --- Skill leaves ---
        case SkillCondition(name=n, mode=mode):
            if mode == "learned":
                # Only permanently learned skills — registry not required.
                return n in player.known_skills
            else:
                # mode == "available": includes item-granted skills; requires registry.
                # Without a registry (e.g. some test contexts) falls back to known_skills only.
                return n in player.available_skills(registry)

        # --- Pronoun leaves ---
        case PronounsCondition(set=pronoun_key):
            from oscilla.engine.templates import resolve_pronoun_set

            target_ps = resolve_pronoun_set(key=pronoun_key, registry=registry)
            if target_ps is None:
                logger.warning(
                    "pronouns condition: unknown pronoun set key %r — evaluating False.",
                    pronoun_key,
                )
                return False
            return player.pronouns == target_ps

    # Unreachable if all Condition subtypes are handled above; guards against
    # extending the union without adding a case branch.
    raise ValueError(f"Unhandled condition type: {condition!r}")  # pragma: no cover


def _numeric_compare(value: int, condition: object) -> bool:
    """Apply gt / gte / lt / lte / eq / mod comparisons from a condition object.

    All comparators that are set must pass (logical AND).
    Raises ValueError if no comparators are set — this should have been caught
    by the Pydantic model_validator at load time, but serves as a runtime guard.
    """
    have_gt = getattr(condition, "gt", None)
    have_gte = getattr(condition, "gte", None)
    have_lt = getattr(condition, "lt", None)
    have_lte = getattr(condition, "lte", None)
    have_eq = getattr(condition, "eq", None)
    have_mod = getattr(condition, "mod", None)

    if all(v is None for v in (have_gt, have_gte, have_lt, have_lte, have_eq, have_mod)):
        raise ValueError(
            f"Numeric condition {condition!r} has none of gt/gte/lt/lte/eq/mod set — "
            "at least one comparator is required."
        )

    if have_gt is not None and not (value > have_gt):
        return False
    if have_gte is not None and not (value >= have_gte):
        return False
    if have_lt is not None and not (value < have_lt):
        return False
    if have_lte is not None and not (value <= have_lte):
        return False
    if have_eq is not None and not (value == have_eq):
        return False
    if have_mod is not None and not (value % have_mod.divisor == have_mod.remainder):
        return False
    return True
