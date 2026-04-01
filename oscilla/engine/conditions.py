"""Condition evaluator — pure recursive evaluation of condition trees against player state."""

from __future__ import annotations

from logging import getLogger
from typing import TYPE_CHECKING

from oscilla.engine.models.base import (
    AdventuresCompletedCondition,
    AllCondition,
    AnyCondition,
    CharacterStatCondition,
    ClassCondition,
    Condition,
    EnemiesDefeatedCondition,
    ItemCondition,
    LevelCondition,
    LocationsVisitedCondition,
    MilestoneCondition,
    NotCondition,
    PrestigeCountCondition,
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
) -> bool:
    """Evaluate a condition tree against the given player state.

    Returns True if condition is None (no gate) or every node evaluates to True.
    Pass registry to enable equipment-aware stat evaluation via effective_stats().
    """
    if condition is None:
        return True

    match condition:
        # --- Branch nodes ---
        case AllCondition(conditions=children):
            return all(evaluate(c, player, registry) for c in children)
        case AnyCondition(conditions=children):
            return any(evaluate(c, player, registry) for c in children)
        case NotCondition(condition=child):
            return not evaluate(child, player, registry)

        # --- Player attribute leaves ---
        case LevelCondition(value=v):
            return player.level >= v
        case MilestoneCondition(name=n):
            return n in player.milestones
        case ItemCondition(name=n):
            return player.stacks.get(n, 0) > 0
        case ClassCondition():
            # No-op in v1: class mechanics are a placeholder; every class always passes.
            return True
        case PrestigeCountCondition() as c:
            return _numeric_compare(player.iteration, c)

        # --- CharacterConfig stat leaves ---
        case CharacterStatCondition(name=n) as c:
            # Use effective_stats when registry available to include equipment bonuses
            stats = player.effective_stats(registry=registry) if registry is not None else player.stats
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
