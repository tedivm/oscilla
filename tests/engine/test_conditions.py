"""Tests for the condition evaluator."""

from __future__ import annotations

from typing import Any

import pytest

from oscilla.engine.character import CharacterState
from oscilla.engine.conditions import _numeric_compare, evaluate
from oscilla.engine.models.base import (
    AdventuresCompletedCondition,
    AllCondition,
    AnyCondition,
    CharacterStatCondition,
    ClassCondition,
    EnemiesDefeatedCondition,
    ItemCondition,
    LevelCondition,
    LocationsVisitedCondition,
    MilestoneCondition,
    MilestoneTicksElapsedCondition,
    NotCondition,
    PrestigeCountCondition,
    PronounsCondition,
)
from oscilla.engine.templates import PRONOUN_SETS


def test_none_condition_always_true(base_player: CharacterState) -> None:
    assert evaluate(condition=None, player=base_player) is True


def test_level_condition_pass(base_player: CharacterState) -> None:
    cond = LevelCondition(type="level", value=1)
    assert evaluate(condition=cond, player=base_player) is True


def test_level_condition_fail(base_player: CharacterState) -> None:
    cond = LevelCondition(type="level", value=5)
    assert evaluate(condition=cond, player=base_player) is False


def test_milestone_condition_pass(base_player: CharacterState) -> None:
    base_player.grant_milestone("special-flag")
    cond = MilestoneCondition(type="milestone", name="special-flag")
    assert evaluate(condition=cond, player=base_player) is True


def test_milestone_condition_fail(base_player: CharacterState) -> None:
    cond = MilestoneCondition(type="milestone", name="not-granted")
    assert evaluate(condition=cond, player=base_player) is False


def test_item_condition_pass(base_player: CharacterState) -> None:
    base_player.add_item("test-item", quantity=1)
    cond = ItemCondition(type="item", name="test-item")
    assert evaluate(condition=cond, player=base_player) is True


def test_item_condition_fail(base_player: CharacterState) -> None:
    cond = ItemCondition(type="item", name="nonexistent-item")
    assert evaluate(condition=cond, player=base_player) is False


def test_character_stat_gte_pass(base_player: CharacterState) -> None:
    # strength defaults to 10 in the minimal fixture
    cond = CharacterStatCondition(type="character_stat", name="strength", gte=10)
    assert evaluate(condition=cond, player=base_player) is True


def test_character_stat_gte_fail(base_player: CharacterState) -> None:
    cond = CharacterStatCondition(type="character_stat", name="strength", gte=20)
    assert evaluate(condition=cond, player=base_player) is False


def test_character_stat_gt(base_player: CharacterState) -> None:
    cond_pass = CharacterStatCondition(type="character_stat", name="strength", gt=9)
    cond_fail = CharacterStatCondition(type="character_stat", name="strength", gt=10)
    assert evaluate(condition=cond_pass, player=base_player) is True
    assert evaluate(condition=cond_fail, player=base_player) is False


def test_character_stat_lt(base_player: CharacterState) -> None:
    cond_pass = CharacterStatCondition(type="character_stat", name="strength", lt=11)
    cond_fail = CharacterStatCondition(type="character_stat", name="strength", lt=10)
    assert evaluate(condition=cond_pass, player=base_player) is True
    assert evaluate(condition=cond_fail, player=base_player) is False


def test_character_stat_eq(base_player: CharacterState) -> None:
    cond_pass = CharacterStatCondition(type="character_stat", name="strength", eq=10)
    cond_fail = CharacterStatCondition(type="character_stat", name="strength", eq=5)
    assert evaluate(condition=cond_pass, player=base_player) is True
    assert evaluate(condition=cond_fail, player=base_player) is False


def test_all_condition_requires_all(base_player: CharacterState) -> None:
    base_player.grant_milestone("m1")
    # Both pass
    cond_pass = AllCondition(
        type="all",
        conditions=[
            LevelCondition(type="level", value=1),
            MilestoneCondition(type="milestone", name="m1"),
        ],
    )
    assert evaluate(condition=cond_pass, player=base_player) is True

    # One fails
    cond_fail = AllCondition(
        type="all",
        conditions=[
            LevelCondition(type="level", value=1),
            LevelCondition(type="level", value=99),
        ],
    )
    assert evaluate(condition=cond_fail, player=base_player) is False


def test_any_condition_requires_at_least_one(base_player: CharacterState) -> None:
    base_player.grant_milestone("any-flag")
    # One of the two passes
    cond_pass = AnyCondition(
        type="any",
        conditions=[
            LevelCondition(type="level", value=99),
            MilestoneCondition(type="milestone", name="any-flag"),
        ],
    )
    assert evaluate(condition=cond_pass, player=base_player) is True

    # None pass
    cond_fail = AnyCondition(
        type="any",
        conditions=[
            LevelCondition(type="level", value=99),
            LevelCondition(type="level", value=100),
        ],
    )
    assert evaluate(condition=cond_fail, player=base_player) is False


def test_not_condition(base_player: CharacterState) -> None:
    inner = LevelCondition(type="level", value=99)
    cond = NotCondition(type="not", condition=inner)
    assert evaluate(condition=cond, player=base_player) is True

    inner_pass = LevelCondition(type="level", value=1)
    cond_false = NotCondition(type="not", condition=inner_pass)
    assert evaluate(condition=cond_false, player=base_player) is False


def test_class_condition_always_passes(base_player: CharacterState) -> None:
    """Test that ClassCondition always returns True (no-op in v1)."""
    cond = ClassCondition(type="class", name="warrior")
    assert evaluate(condition=cond, player=base_player) is True

    # Test any class name
    cond2 = ClassCondition(type="class", name="mage")
    assert evaluate(condition=cond2, player=base_player) is True


def test_character_stat_non_numeric_warning(base_player: CharacterState, caplog: pytest.LogCaptureFixture) -> None:
    """Test that non-numeric stats trigger a warning and are treated as 0."""
    # Set a string stat
    base_player.stats["text_stat"] = "hello"  # type: ignore[assignment]

    # This should trigger the warning and treat the value as 0
    cond = CharacterStatCondition(type="character_stat", name="text_stat", gte=5)
    result = evaluate(condition=cond, player=base_player)

    # Should be False because 0 is not >= 5
    assert result is False

    # Should have logged a warning
    assert "character_stat condition on non-numeric stat" in caplog.text


def test_iteration_condition(base_player: CharacterState) -> None:
    """Test prestige count conditions."""
    # Default prestige count is 0
    cond_fail = PrestigeCountCondition(type="prestige_count", gte=1)
    assert evaluate(condition=cond_fail, player=base_player) is False

    # Set prestige count and test
    base_player.prestige_count = 2
    cond_pass = PrestigeCountCondition(type="prestige_count", gte=1)
    assert evaluate(condition=cond_pass, player=base_player) is True

    cond_exact = PrestigeCountCondition(type="prestige_count", eq=2)
    assert evaluate(condition=cond_exact, player=base_player) is True


def test_enemies_defeated_condition(base_player: CharacterState) -> None:
    """Test enemies defeated condition."""
    # Initially no enemies defeated
    cond = EnemiesDefeatedCondition(type="enemies_defeated", name="goblin", gte=1)
    assert evaluate(condition=cond, player=base_player) is False

    # Record enemy defeat
    base_player.statistics.enemies_defeated["goblin"] = 3

    cond_pass = EnemiesDefeatedCondition(type="enemies_defeated", name="goblin", gte=2)
    assert evaluate(condition=cond_pass, player=base_player) is True

    cond_exact = EnemiesDefeatedCondition(type="enemies_defeated", name="goblin", eq=3)
    assert evaluate(condition=cond_exact, player=base_player) is True


def test_locations_visited_condition(base_player: CharacterState) -> None:
    """Test locations visited condition."""
    # Initially no locations visited
    cond = LocationsVisitedCondition(type="locations_visited", name="forest", gte=1)
    assert evaluate(condition=cond, player=base_player) is False

    # Record location visit
    base_player.statistics.locations_visited["forest"] = 2

    cond_pass = LocationsVisitedCondition(type="locations_visited", name="forest", gte=1)
    assert evaluate(condition=cond_pass, player=base_player) is True

    cond_exact = LocationsVisitedCondition(type="locations_visited", name="forest", eq=2)
    assert evaluate(condition=cond_exact, player=base_player) is True


def test_adventures_completed_condition(base_player: CharacterState) -> None:
    """Test adventures completed condition."""
    # Initially no adventures completed
    cond = AdventuresCompletedCondition(type="adventures_completed", name="quest-1", gte=1)
    assert evaluate(condition=cond, player=base_player) is False

    # Record adventure completion
    base_player.statistics.adventures_completed["quest-1"] = 1

    cond_pass = AdventuresCompletedCondition(type="adventures_completed", name="quest-1", eq=1)
    assert evaluate(condition=cond_pass, player=base_player) is True


def test_numeric_compare_all_operators() -> None:
    """Test _numeric_compare with all available operators."""

    # Create mock condition objects
    class MockCondition:
        def __init__(self, **kwargs: Any) -> None:
            for key, value in kwargs.items():
                setattr(self, key, value)
            # Set default None for all attributes
            for attr in ["gt", "gte", "lt", "lte", "eq", "mod"]:
                if not hasattr(self, attr):
                    setattr(self, attr, None)

    # Test gt
    cond_gt = MockCondition(gt=3)
    assert _numeric_compare(4, cond_gt) is True
    assert _numeric_compare(3, cond_gt) is False

    # Test gte
    cond_gte = MockCondition(gte=3)
    assert _numeric_compare(3, cond_gte) is True
    assert _numeric_compare(2, cond_gte) is False

    # Test lt
    cond_lt = MockCondition(lt=5)
    assert _numeric_compare(4, cond_lt) is True
    assert _numeric_compare(5, cond_lt) is False

    # Test lte
    cond_lte = MockCondition(lte=5)
    assert _numeric_compare(5, cond_lte) is True
    assert _numeric_compare(6, cond_lte) is False

    # Test eq
    cond_eq = MockCondition(eq=7)
    assert _numeric_compare(7, cond_eq) is True
    assert _numeric_compare(6, cond_eq) is False

    # Test mod - create a mock ModCondition
    class MockModCondition:
        def __init__(self, divisor: int, remainder: int) -> None:
            self.divisor = divisor
            self.remainder = remainder

    cond_mod = MockCondition(mod=MockModCondition(divisor=3, remainder=1))
    assert _numeric_compare(4, cond_mod) is True  # 4 % 3 == 1
    assert _numeric_compare(5, cond_mod) is False  # 5 % 3 == 2


def test_numeric_compare_no_operators_raises_error() -> None:
    """Test that _numeric_compare raises ValueError when no operators are set."""

    class MockCondition:
        def __init__(self) -> None:
            self.gt = None
            self.gte = None
            self.lt = None
            self.lte = None
            self.eq = None
            self.mod = None

    cond = MockCondition()
    with pytest.raises(ValueError, match="has none of gt/gte/lt/lte/eq/mod set"):
        _numeric_compare(5, cond)


def test_numeric_compare_multiple_operators_pass() -> None:
    """Test _numeric_compare when no operators fail (hits return True)."""

    class MockCondition:
        def __init__(self) -> None:
            self.gt = 2
            self.gte = 3
            self.lt = 8
            self.lte = 5
            self.eq = 5
            self.mod = None

    cond = MockCondition()
    # 5 > 2, 5 >= 3, 5 < 8, 5 <= 5, 5 == 5 - all pass
    assert _numeric_compare(5, cond) is True


# ---------------------------------------------------------------------------
# Pronouns condition
# ---------------------------------------------------------------------------


def test_pronouns_condition_matches_default(base_player: CharacterState) -> None:
    # New characters default to they/them.
    cond = PronounsCondition(type="pronouns", set="they_them")
    assert evaluate(condition=cond, player=base_player) is True


def test_pronouns_condition_does_not_match_other_set(base_player: CharacterState) -> None:
    cond = PronounsCondition(type="pronouns", set="she_her")
    assert evaluate(condition=cond, player=base_player) is False


def test_pronouns_condition_matches_after_set(base_player: CharacterState) -> None:
    base_player.pronouns = PRONOUN_SETS["she_her"]
    cond = PronounsCondition(type="pronouns", set="she_her")
    assert evaluate(condition=cond, player=base_player) is True


def test_pronouns_condition_unknown_key_returns_false(base_player: CharacterState) -> None:
    cond = PronounsCondition(type="pronouns", set="unknown_key")
    assert evaluate(condition=cond, player=base_player) is False


# ---------------------------------------------------------------------------
# 8.3 — ItemCondition: stacks and instances paths
# ---------------------------------------------------------------------------


def test_item_condition_via_instance(base_player: CharacterState) -> None:
    """ItemCondition returns True when the item is held as a non-stackable instance."""
    from oscilla.engine.character import ItemInstance
    from oscilla.engine.models.base import ItemCondition

    base_player.instances.append(ItemInstance(instance_id=__import__("uuid").uuid4(), item_ref="rare-sword"))
    cond = ItemCondition(type="item", name="rare-sword")
    assert evaluate(condition=cond, player=base_player) is True


def test_item_condition_absent_from_both(base_player: CharacterState) -> None:
    """ItemCondition returns False when the item is in neither stacks nor instances."""
    from oscilla.engine.models.base import ItemCondition

    cond = ItemCondition(type="item", name="nonexistent-item")
    assert evaluate(condition=cond, player=base_player) is False


def test_item_condition_stack_path(base_player: CharacterState) -> None:
    """ItemCondition returns True when the item is held as a stackable (stacks path)."""
    from oscilla.engine.models.base import ItemCondition

    base_player.stacks["health-potion"] = 2
    cond = ItemCondition(type="item", name="health-potion")
    assert evaluate(condition=cond, player=base_player) is True


# ---------------------------------------------------------------------------
# MilestoneTicksElapsedCondition — evaluator (task 14.10)
# ---------------------------------------------------------------------------


def test_milestone_ticks_elapsed_false_when_not_granted(base_player: CharacterState) -> None:
    """Returns False when the milestone has never been granted."""
    cond = MilestoneTicksElapsedCondition(type="milestone_ticks_elapsed", name="not-held", gte=1)
    assert evaluate(condition=cond, player=base_player) is False


def test_milestone_ticks_elapsed_gte_pass(base_player: CharacterState) -> None:
    """Returns True when elapsed ticks >= gte."""
    base_player.internal_ticks = 10
    base_player.grant_milestone("joined-guild")
    base_player.internal_ticks = 20

    cond = MilestoneTicksElapsedCondition(type="milestone_ticks_elapsed", name="joined-guild", gte=5)
    assert evaluate(condition=cond, player=base_player) is True


def test_milestone_ticks_elapsed_gte_exact(base_player: CharacterState) -> None:
    """Returns True when elapsed ticks exactly equals gte."""
    base_player.internal_ticks = 10
    base_player.grant_milestone("joined-guild")
    base_player.internal_ticks = 15

    cond = MilestoneTicksElapsedCondition(type="milestone_ticks_elapsed", name="joined-guild", gte=5)
    assert evaluate(condition=cond, player=base_player) is True


def test_milestone_ticks_elapsed_gte_fail(base_player: CharacterState) -> None:
    """Returns False when elapsed ticks < gte."""
    base_player.internal_ticks = 10
    base_player.grant_milestone("joined-guild")
    base_player.internal_ticks = 14  # only 4 elapsed

    cond = MilestoneTicksElapsedCondition(type="milestone_ticks_elapsed", name="joined-guild", gte=5)
    assert evaluate(condition=cond, player=base_player) is False


def test_milestone_ticks_elapsed_lte_pass(base_player: CharacterState) -> None:
    """Returns True when elapsed ticks <= lte."""
    base_player.internal_ticks = 10
    base_player.grant_milestone("fresh-flag")
    base_player.internal_ticks = 13  # 3 elapsed

    cond = MilestoneTicksElapsedCondition(type="milestone_ticks_elapsed", name="fresh-flag", lte=5)
    assert evaluate(condition=cond, player=base_player) is True


def test_milestone_ticks_elapsed_lte_fail(base_player: CharacterState) -> None:
    """Returns False when elapsed ticks > lte."""
    base_player.internal_ticks = 10
    base_player.grant_milestone("old-flag")
    base_player.internal_ticks = 20  # 10 elapsed

    cond = MilestoneTicksElapsedCondition(type="milestone_ticks_elapsed", name="old-flag", lte=5)
    assert evaluate(condition=cond, player=base_player) is False


def test_milestone_ticks_elapsed_both_gte_and_lte(base_player: CharacterState) -> None:
    """With both gte and lte set, elapsed must be in window [gte, lte]."""
    base_player.internal_ticks = 0
    base_player.grant_milestone("window-flag")
    cond = MilestoneTicksElapsedCondition(type="milestone_ticks_elapsed", name="window-flag", gte=3, lte=7)

    base_player.internal_ticks = 2  # too early
    assert evaluate(condition=cond, player=base_player) is False
    base_player.internal_ticks = 5  # in window
    assert evaluate(condition=cond, player=base_player) is True
    base_player.internal_ticks = 8  # too late
    assert evaluate(condition=cond, player=base_player) is False
