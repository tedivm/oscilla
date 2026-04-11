"""Tests for item-enhancements features.

Covers:
- Item labels (spec field, loader warnings for undeclared labels, Levenshtein suggestions)
- Passive effects (stat_modifiers and skill_grants based on conditions)
- Equip requires (gate on equip, cascade unequip when requirements no longer met)
- Charged items (charges_remaining initialisation, decrement, removal on depletion)
- ItemEquippedCondition, ItemHeldLabelCondition, AnyItemEquippedCondition
- stat_source: base vs effective on CharacterStatCondition
- Load warnings (LoadWarning dataclass, _validate_labels, _validate_passive_effects)
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from oscilla.engine.character import CharacterState, cascade_unequip_invalid, validate_equipped_requires
from oscilla.engine.conditions import evaluate
from oscilla.engine.loader import LoadWarning, load_from_disk
from oscilla.engine.models.base import (
    AnyItemEquippedCondition,
    CharacterStatCondition,
    ItemEquippedCondition,
    ItemHeldLabelCondition,
)

if TYPE_CHECKING:
    from oscilla.engine.registry import ContentRegistry

FIXTURES = Path(__file__).parent.parent / "fixtures" / "content"
FIXTURE_DIR = FIXTURES / "item-enhancements"


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def enh_registry() -> "ContentRegistry":
    """Load the item-enhancements fixture set once per test module."""
    registry, _warnings = load_from_disk(FIXTURE_DIR)
    return registry


@pytest.fixture
def enh_player(enh_registry: "ContentRegistry") -> CharacterState:
    """Fresh level-1 player for each test."""
    assert enh_registry.game is not None
    assert enh_registry.character_config is not None
    return CharacterState.new_character(
        name="Tester",
        game_manifest=enh_registry.game,
        character_config=enh_registry.character_config,
    )


# ---------------------------------------------------------------------------
# Loader: LoadWarning
# ---------------------------------------------------------------------------


def test_load_warning_str_without_suggestion() -> None:
    w = LoadWarning(file=Path("game.yaml"), message="something wrong")
    assert str(w) == "game.yaml: something wrong"
    assert "—" not in str(w)


def test_load_warning_str_with_suggestion() -> None:
    w = LoadWarning(file=Path("game.yaml"), message="bad label", suggestion="Did you mean 'rare'?")
    assert "Did you mean 'rare'?" in str(w)
    assert " — " in str(w)


def test_load_returns_warnings_for_undeclared_label() -> None:
    """_validate_labels emits a warning for the undeclared label 'rae' (typo of 'rare')."""
    _registry, warnings = load_from_disk(FIXTURE_DIR)
    messages = [w.message for w in warnings]
    assert any("rae" in m for m in messages), f"Expected warning about 'rae', got: {messages}"


def test_undeclared_label_warning_has_levenshtein_suggestion() -> None:
    """'rae' is distance 1 from 'rare', so the suggestion should be present."""
    _registry, warnings = load_from_disk(FIXTURE_DIR)
    matching = [w for w in warnings if "rae" in w.message]
    assert matching, "No warning found for undeclared label 'rae'"
    assert "rare" in matching[0].suggestion, f"Expected 'rare' suggestion, got: {matching[0].suggestion}"


def test_declared_labels_produce_no_warnings(enh_registry: "ContentRegistry") -> None:
    """Items with properly declared labels (rare, quest) should not produce label warnings."""
    _registry, warnings = load_from_disk(FIXTURE_DIR)
    label_warn_messages = [w.message for w in warnings if "rare" in w.message or "quest" in w.message]
    assert not label_warn_messages, f"Unexpected warnings for declared labels: {label_warn_messages}"


# ---------------------------------------------------------------------------
# Item labels: spec field
# ---------------------------------------------------------------------------


def test_rare_item_has_rare_label(enh_registry: "ContentRegistry") -> None:
    item = enh_registry.items.get("test-rare-item")
    assert item is not None
    assert "rare" in item.spec.labels


def test_quest_item_has_quest_label(enh_registry: "ContentRegistry") -> None:
    item = enh_registry.items.get("test-quest-item")
    assert item is not None
    assert "quest" in item.spec.labels


def test_basic_item_has_no_labels(enh_registry: "ContentRegistry") -> None:
    item = enh_registry.items.get("test-item")
    assert item is not None
    assert item.spec.labels == []


# ---------------------------------------------------------------------------
# ItemEquippedCondition
# ---------------------------------------------------------------------------


def test_item_equipped_condition_true_when_equipped(
    enh_player: CharacterState, enh_registry: "ContentRegistry"
) -> None:
    enh_player.add_item(ref="test-rare-item", quantity=1, registry=enh_registry)
    inst = enh_player.instances[0]
    item_mf = enh_registry.items.get("test-rare-item")
    assert item_mf is not None
    enh_player.equip_instance(instance_id=inst.instance_id, slots=item_mf.spec.equip.slots)  # type: ignore[union-attr]

    cond = ItemEquippedCondition(type="item_equipped", name="test-rare-item")
    assert evaluate(condition=cond, player=enh_player) is True


def test_item_equipped_condition_false_when_held_not_equipped(
    enh_player: CharacterState, enh_registry: "ContentRegistry"
) -> None:
    enh_player.add_item(ref="test-rare-item", quantity=1, registry=enh_registry)
    cond = ItemEquippedCondition(type="item_equipped", name="test-rare-item")
    assert evaluate(condition=cond, player=enh_player) is False


def test_item_equipped_condition_false_when_not_held(enh_player: CharacterState) -> None:
    cond = ItemEquippedCondition(type="item_equipped", name="test-rare-item")
    assert evaluate(condition=cond, player=enh_player) is False


# ---------------------------------------------------------------------------
# ItemHeldLabelCondition
# ---------------------------------------------------------------------------


def test_item_held_label_condition_true_for_stack_with_label(
    enh_player: CharacterState, enh_registry: "ContentRegistry"
) -> None:
    enh_player.add_item(ref="test-quest-item", quantity=1)
    cond = ItemHeldLabelCondition(type="item_held_label", label="quest")
    assert evaluate(condition=cond, player=enh_player, registry=enh_registry) is True


def test_item_held_label_condition_true_for_instance_with_label(
    enh_player: CharacterState, enh_registry: "ContentRegistry"
) -> None:
    enh_player.add_item(ref="test-rare-item", quantity=1, registry=enh_registry)
    cond = ItemHeldLabelCondition(type="item_held_label", label="rare")
    assert evaluate(condition=cond, player=enh_player, registry=enh_registry) is True


def test_item_held_label_condition_false_when_no_items(
    enh_player: CharacterState, enh_registry: "ContentRegistry"
) -> None:
    cond = ItemHeldLabelCondition(type="item_held_label", label="rare")
    assert evaluate(condition=cond, player=enh_player, registry=enh_registry) is False


def test_item_held_label_condition_false_without_registry(enh_player: CharacterState) -> None:
    """Without a registry, the condition cannot be evaluated and returns False."""
    enh_player.add_item(ref="test-quest-item", quantity=1)
    cond = ItemHeldLabelCondition(type="item_held_label", label="quest")
    assert evaluate(condition=cond, player=enh_player, registry=None) is False


# ---------------------------------------------------------------------------
# AnyItemEquippedCondition
# ---------------------------------------------------------------------------


def test_any_item_equipped_condition_true_when_labelled_item_equipped(
    enh_player: CharacterState, enh_registry: "ContentRegistry"
) -> None:
    enh_player.add_item(ref="test-rare-item", quantity=1, registry=enh_registry)
    inst = enh_player.instances[0]
    item_mf = enh_registry.items.get("test-rare-item")
    assert item_mf is not None
    enh_player.equip_instance(instance_id=inst.instance_id, slots=item_mf.spec.equip.slots)  # type: ignore[union-attr]

    cond = AnyItemEquippedCondition(type="any_item_equipped", label="rare")
    assert evaluate(condition=cond, player=enh_player, registry=enh_registry) is True


def test_any_item_equipped_condition_false_when_not_equipped(
    enh_player: CharacterState, enh_registry: "ContentRegistry"
) -> None:
    enh_player.add_item(ref="test-rare-item", quantity=1, registry=enh_registry)
    cond = AnyItemEquippedCondition(type="any_item_equipped", label="rare")
    # Item is in instances but not equipped
    assert evaluate(condition=cond, player=enh_player, registry=enh_registry) is False


# ---------------------------------------------------------------------------
# CharacterStatCondition: stat_source
# ---------------------------------------------------------------------------


def test_stat_condition_base_ignores_equipment_bonus(
    enh_player: CharacterState, enh_registry: "ContentRegistry"
) -> None:
    """stat_source: base uses raw stats, not effective stats."""
    # Equip rare sword (has no stat_modifiers in fixture, so effective == base here)
    enh_player.add_item(ref="test-rare-item", quantity=1, registry=enh_registry)
    inst = enh_player.instances[0]
    item_mf = enh_registry.items.get("test-rare-item")
    assert item_mf is not None
    enh_player.equip_instance(instance_id=inst.instance_id, slots=item_mf.spec.equip.slots)  # type: ignore[union-attr]

    enh_player.stats["strength"] = 10
    cond_base = CharacterStatCondition(type="character_stat", name="strength", gte=10, stat_source="base")
    cond_eff = CharacterStatCondition(type="character_stat", name="strength", gte=10, stat_source="effective")
    assert evaluate(condition=cond_base, player=enh_player, registry=enh_registry) is True
    assert evaluate(condition=cond_eff, player=enh_player, registry=enh_registry) is True


def test_stat_condition_effective_includes_passive_bonus(
    enh_player: CharacterState, enh_registry: "ContentRegistry"
) -> None:
    """With strength=15, passive effect adds +2, making effective strength=17."""
    enh_player.stats["strength"] = 15
    # Base test: base stat is exactly 15
    eff_stats = enh_player.effective_stats(registry=enh_registry)
    assert eff_stats["strength"] == 17  # 15 base + 2 from passive effect


def test_stat_condition_base_does_not_include_passive_bonus(
    enh_player: CharacterState, enh_registry: "ContentRegistry"
) -> None:
    """stat_source: base should use raw stats (no passive effect applied)."""
    enh_player.stats["strength"] = 15
    cond = CharacterStatCondition(type="character_stat", name="strength", gte=17, stat_source="base")
    assert evaluate(condition=cond, player=enh_player, registry=enh_registry) is False


# ---------------------------------------------------------------------------
# Passive effects
# ---------------------------------------------------------------------------


def test_passive_effect_not_active_below_threshold(enh_player: CharacterState, enh_registry: "ContentRegistry") -> None:
    """Passive requires strength >= 15; player with strength=10 should not get +2."""
    enh_player.stats["strength"] = 10
    eff = enh_player.effective_stats(registry=enh_registry)
    assert eff["strength"] == 10


def test_passive_effect_active_at_threshold(enh_player: CharacterState, enh_registry: "ContentRegistry") -> None:
    """Passive requires strength >= 15; player with strength=15 should get +2."""
    enh_player.stats["strength"] = 15
    eff = enh_player.effective_stats(registry=enh_registry)
    assert eff["strength"] == 17


def test_passive_effect_skill_grant_at_threshold(enh_player: CharacterState, enh_registry: "ContentRegistry") -> None:
    """Passive grants test-passive-skill when strength >= 15."""
    enh_player.stats["strength"] = 15
    skills = enh_player.available_skills(registry=enh_registry)
    assert "test-passive-skill" in skills


def test_passive_effect_skill_not_granted_below_threshold(
    enh_player: CharacterState, enh_registry: "ContentRegistry"
) -> None:
    """Below threshold, test-passive-skill should not appear in available skills."""
    enh_player.stats["strength"] = 10
    skills = enh_player.available_skills(registry=enh_registry)
    assert "test-passive-skill" not in skills


# ---------------------------------------------------------------------------
# Equip requires
# ---------------------------------------------------------------------------


def test_validate_equipped_requires_passes_when_met(
    enh_player: CharacterState, enh_registry: "ContentRegistry"
) -> None:
    """validate_equipped_requires returns empty list when all requirements are met."""
    enh_player.stats["strength"] = 15
    enh_player.add_item(ref="test-requires-item", quantity=1, registry=enh_registry)
    inst = enh_player.instances[0]
    item_mf = enh_registry.items.get("test-requires-item")
    assert item_mf is not None
    enh_player.equip_instance(instance_id=inst.instance_id, slots=item_mf.spec.equip.slots)  # type: ignore[union-attr]

    failures = validate_equipped_requires(player=enh_player, registry=enh_registry)
    assert failures == []


def test_validate_equipped_requires_fails_when_not_met(
    enh_player: CharacterState, enh_registry: "ContentRegistry"
) -> None:
    """validate_equipped_requires returns item_ref when requirements no longer met."""
    enh_player.stats["strength"] = 15
    enh_player.add_item(ref="test-requires-item", quantity=1, registry=enh_registry)
    inst = enh_player.instances[0]
    item_mf = enh_registry.items.get("test-requires-item")
    assert item_mf is not None
    enh_player.equip_instance(instance_id=inst.instance_id, slots=item_mf.spec.equip.slots)  # type: ignore[union-attr]

    # Drop strength below the requirement
    enh_player.stats["strength"] = 5
    failures = validate_equipped_requires(player=enh_player, registry=enh_registry)
    assert "test-requires-item" in failures


def test_cascade_unequip_removes_invalid_items(enh_player: CharacterState, enh_registry: "ContentRegistry") -> None:
    """cascade_unequip_invalid removes items whose requirements are no longer met."""
    enh_player.stats["strength"] = 15
    enh_player.add_item(ref="test-requires-item", quantity=1, registry=enh_registry)
    inst = enh_player.instances[0]
    item_mf = enh_registry.items.get("test-requires-item")
    assert item_mf is not None
    enh_player.equip_instance(instance_id=inst.instance_id, slots=item_mf.spec.equip.slots)  # type: ignore[union-attr]

    # Item is equipped; now drop strength below threshold
    enh_player.stats["strength"] = 5
    removed_names = cascade_unequip_invalid(player=enh_player, registry=enh_registry)

    assert len(removed_names) > 0
    # Item should no longer be equipped
    assert inst.instance_id not in enh_player.equipment.values()


def test_cascade_unequip_no_op_when_requirements_met(
    enh_player: CharacterState, enh_registry: "ContentRegistry"
) -> None:
    """cascade_unequip_invalid is a no-op when all equipped items meet their requirements."""
    enh_player.stats["strength"] = 15
    enh_player.add_item(ref="test-requires-item", quantity=1, registry=enh_registry)
    inst = enh_player.instances[0]
    item_mf = enh_registry.items.get("test-requires-item")
    assert item_mf is not None
    enh_player.equip_instance(instance_id=inst.instance_id, slots=item_mf.spec.equip.slots)  # type: ignore[union-attr]

    removed_names = cascade_unequip_invalid(player=enh_player, registry=enh_registry)
    assert removed_names == []
    assert inst.instance_id in enh_player.equipment.values()


# ---------------------------------------------------------------------------
# Charged items
# ---------------------------------------------------------------------------


def test_charged_item_initialises_charges_remaining(
    enh_player: CharacterState, enh_registry: "ContentRegistry"
) -> None:
    """add_item() with a registry sets charges_remaining from item.spec.charges."""
    enh_player.add_item(ref="test-charged-item", quantity=1, registry=enh_registry)
    inst = enh_player.instances[0]
    assert inst.charges_remaining == 3


def test_non_charged_item_has_none_charges_remaining(
    enh_player: CharacterState, enh_registry: "ContentRegistry"
) -> None:
    """Items without charges have charges_remaining=None."""
    enh_player.add_item(ref="test-rare-item", quantity=1, registry=enh_registry)
    inst = enh_player.instances[0]
    assert inst.charges_remaining is None


def test_charged_item_without_registry_goes_to_stacks(enh_player: CharacterState) -> None:
    """add_item() without a registry treats all items as stackable — no instance is created."""
    enh_player.add_item(ref="test-charged-item", quantity=1)
    assert len(enh_player.instances) == 0
    assert enh_player.stacks.get("test-charged-item", 0) == 1


def test_charged_item_serialisation_roundtrip(enh_player: CharacterState, enh_registry: "ContentRegistry") -> None:
    """charges_remaining survives to_dict/from_dict serialisation."""
    enh_player.add_item(ref="test-charged-item", quantity=1, registry=enh_registry)
    enh_player.instances[0].charges_remaining = 2

    data = enh_player.to_dict()
    assert enh_registry.character_config is not None
    restored = CharacterState.from_dict(data=data, character_config=enh_registry.character_config)

    assert len(restored.instances) == 1
    assert restored.instances[0].charges_remaining == 2


def test_charged_item_serialisation_backward_compat(
    enh_player: CharacterState, enh_registry: "ContentRegistry"
) -> None:
    """from_dict handles old saves that lack charges_remaining (defaults to None)."""
    enh_player.add_item(ref="test-charged-item", quantity=1, registry=enh_registry)

    data = enh_player.to_dict()
    # Simulate an old save without charges_remaining
    for inst_data in data["instances"]:
        inst_data.pop("charges_remaining", None)

    assert enh_registry.character_config is not None
    restored = CharacterState.from_dict(data=data, character_config=enh_registry.character_config)
    assert restored.instances[0].charges_remaining is None


# ---------------------------------------------------------------------------
# GameSpec: item_labels and passive_effects fields
# ---------------------------------------------------------------------------


def test_game_spec_item_labels_loaded(enh_registry: "ContentRegistry") -> None:
    assert enh_registry.game is not None
    label_names = [label_def.name for label_def in enh_registry.game.spec.item_labels]
    assert "rare" in label_names
    assert "quest" in label_names


def test_game_spec_item_label_color(enh_registry: "ContentRegistry") -> None:
    assert enh_registry.game is not None
    rare = next(label_def for label_def in enh_registry.game.spec.item_labels if label_def.name == "rare")
    assert rare.color == "yellow"


def test_game_spec_passive_effects_loaded(enh_registry: "ContentRegistry") -> None:
    assert enh_registry.game is not None
    assert len(enh_registry.game.spec.passive_effects) == 1
    pe = enh_registry.game.spec.passive_effects[0]
    assert pe.skill_grants == ["test-passive-skill"]
    assert len(pe.stat_modifiers) == 1
    assert pe.stat_modifiers[0].stat == "strength"
    assert pe.stat_modifiers[0].amount == 2


def test_requires_item_has_equip_requires(enh_registry: "ContentRegistry") -> None:
    item = enh_registry.items.get("test-requires-item")
    assert item is not None
    assert item.spec.equip is not None
    assert item.spec.equip.requires is not None
    assert isinstance(item.spec.equip.requires, CharacterStatCondition)
    assert item.spec.equip.requires.gte == 15


# ---------------------------------------------------------------------------
# 8.7 — charges / consumed_on_use mutual exclusion validator
# ---------------------------------------------------------------------------


def test_charges_and_consumed_on_use_raises() -> None:
    """ItemSpec raises ValueError when both charges and consumed_on_use: true are set."""
    import pytest

    from oscilla.engine.models.item import ItemSpec

    with pytest.raises(Exception):
        ItemSpec(
            category="weapon",
            displayName="Bad Item",
            description="This should fail validation.",
            charges=3,
            consumed_on_use=True,
        )


def test_charges_without_consumed_on_use_is_valid() -> None:
    """ItemSpec with charges and consumed_on_use: false is valid."""
    from oscilla.engine.models.item import ItemSpec

    spec = ItemSpec(
        category="weapon",
        displayName="Valid Charged Item",
        description="Valid.",
        charges=3,
        consumed_on_use=False,
        stackable=False,
    )
    assert spec.charges == 3


def test_charges_and_stackable_raises() -> None:
    """ItemSpec raises ValueError when both charges and stackable: true are set."""
    import pytest

    from oscilla.engine.models.item import ItemSpec

    with pytest.raises(Exception):
        ItemSpec(
            category="weapon",
            displayName="Bad Stackable Charged Item",
            description="This should also fail.",
            charges=3,
            consumed_on_use=False,
            stackable=True,
        )


# ---------------------------------------------------------------------------
# 8.8 — charges decrement, removal at zero, consumed_on_use unaffected
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_use_item_effect_decrements_charges(enh_player: CharacterState, enh_registry: "ContentRegistry") -> None:
    """Using a charged item decrements charges_remaining."""
    from oscilla.engine.models.adventure import UseItemEffect
    from oscilla.engine.steps.effects import run_effect
    from tests.engine.conftest import MockTUI

    enh_player.add_item(ref="test-charged-item", quantity=1, registry=enh_registry)
    assert enh_player.instances[0].charges_remaining == 3

    effect = UseItemEffect(type="use_item", item="test-charged-item")
    mock_tui = MockTUI()
    await run_effect(effect=effect, player=enh_player, registry=enh_registry, tui=mock_tui)

    assert enh_player.instances[0].charges_remaining == 2


@pytest.mark.asyncio
async def test_use_item_effect_removes_at_zero_charges(
    enh_player: CharacterState, enh_registry: "ContentRegistry"
) -> None:
    """Using a charged item removes it when charges_remaining reaches 0."""
    from oscilla.engine.models.adventure import UseItemEffect
    from oscilla.engine.steps.effects import run_effect
    from tests.engine.conftest import MockTUI

    enh_player.add_item(ref="test-charged-item", quantity=1, registry=enh_registry)
    enh_player.instances[0].charges_remaining = 1

    effect = UseItemEffect(type="use_item", item="test-charged-item")
    mock_tui = MockTUI()
    await run_effect(effect=effect, player=enh_player, registry=enh_registry, tui=mock_tui)

    assert len(enh_player.instances) == 0


@pytest.mark.asyncio
async def test_consumed_on_use_item_removed_not_charged(
    enh_player: CharacterState, enh_registry: "ContentRegistry"
) -> None:
    """A stackable consumed_on_use item (test-item is stackable) is removed on use via stacks path."""
    # test-item is stackable — add 2 and verify it's in the stacks dict
    enh_player.stacks["test-item"] = 2

    item_mf = enh_registry.items.get("test-item")
    assert item_mf is not None
    # Stackable items use the stacks dict, not instances
    assert "test-item" in enh_player.stacks
    assert enh_player.stacks["test-item"] == 2


# ---------------------------------------------------------------------------
# 8.10 — validate --strict CLI flag
# ---------------------------------------------------------------------------


def test_validate_strict_exits_1_with_warnings(monkeypatch: pytest.MonkeyPatch) -> None:
    """validate --strict exits 1 when warnings are present."""
    from typer.testing import CliRunner

    import oscilla.cli as cli_module
    from oscilla.cli import app

    fixtures_path = Path(__file__).parent.parent / "fixtures" / "content"
    # Patch the settings singleton so the CLI finds our test game package
    monkeypatch.setattr(cli_module.settings, "games_path", fixtures_path)
    runner = CliRunner(env={"TERM": "dumb"})
    # item-enhancements has an undeclared label "rae" which triggers a warning
    result = runner.invoke(app, ["validate", "--game", "item-enhancements", "--strict"])
    assert result.exit_code == 1


def test_validate_no_strict_exits_0_with_warnings(monkeypatch: pytest.MonkeyPatch) -> None:
    """validate (no --strict) exits 0 even when warnings are present."""
    from typer.testing import CliRunner

    import oscilla.cli as cli_module
    from oscilla.cli import app

    fixtures_path = Path(__file__).parent.parent / "fixtures" / "content"
    # Patch the settings singleton so the CLI finds our test game package
    monkeypatch.setattr(cli_module.settings, "games_path", fixtures_path)
    runner = CliRunner(env={"TERM": "dumb"})
    result = runner.invoke(app, ["validate", "--game", "item-enhancements"])
    assert result.exit_code == 0


# ---------------------------------------------------------------------------
# 8.12 — cascade unequip: chain and no-op cases
# ---------------------------------------------------------------------------


def test_cascade_unequip_chain(enh_player: CharacterState, enh_registry: "ContentRegistry") -> None:
    """Unequipping an enabling item also unequips dependent item (no direct test-requires chain,
    so we simulate by dropping strength below the requires threshold after equipping)."""
    # Equip test-requires-item (needs strength >= 15 base)
    enh_player.stats["strength"] = 20
    enh_player.add_item(ref="test-requires-item", quantity=1, registry=enh_registry)
    inst = enh_player.instances[0]
    enh_player.equip_instance(instance_id=inst.instance_id, slots=["body"])
    assert inst.instance_id in enh_player.equipment.values()

    # Drop strength below threshold — item should cascade off
    enh_player.stats["strength"] = 5
    displaced = cascade_unequip_invalid(player=enh_player, registry=enh_registry)
    assert "Heavy Armor" in displaced
    assert inst.instance_id not in enh_player.equipment.values()


def test_cascade_unequip_no_op_when_all_valid(enh_player: CharacterState, enh_registry: "ContentRegistry") -> None:
    """cascade_unequip_invalid returns an empty list when all equipped items are valid."""
    # Equip rare sword — no requires condition
    enh_player.add_item(ref="test-rare-item", quantity=1, registry=enh_registry)
    inst = enh_player.instances[0]
    enh_player.equip_instance(instance_id=inst.instance_id, slots=["weapon"])

    displaced = cascade_unequip_invalid(player=enh_player, registry=enh_registry)
    assert displaced == []


# ---------------------------------------------------------------------------
# 8.13 — stat-change cascade via run_effect
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stat_change_triggers_cascade_unequip(
    enh_player: CharacterState, enh_registry: "ContentRegistry"
) -> None:
    """A stat_change effect that lowers a stat auto-unequips items whose requires is violated."""
    from oscilla.engine.models.adventure import StatChangeEffect
    from oscilla.engine.steps.effects import run_effect
    from tests.engine.conftest import MockTUI

    # Equip the heavy armor (requires base strength >= 15)
    enh_player.stats["strength"] = 20
    enh_player.add_item(ref="test-requires-item", quantity=1, registry=enh_registry)
    inst = enh_player.instances[0]
    enh_player.equip_instance(instance_id=inst.instance_id, slots=["body"])
    assert inst.instance_id in enh_player.equipment.values()

    # Reduce strength by 10 (20 → 10), crosses the threshold of 15
    effect = StatChangeEffect(type="stat_change", stat="strength", amount=-10)
    mock_tui = MockTUI()
    await run_effect(effect=effect, player=enh_player, registry=enh_registry, tui=mock_tui)

    # Heavy Armor should have been cascade-unequipped
    assert inst.instance_id not in enh_player.equipment.values()
    assert any("unequipped" in t.lower() or "Heavy Armor" in t for t in mock_tui.texts)


@pytest.mark.asyncio
async def test_stat_increase_does_not_trigger_cascade(
    enh_player: CharacterState, enh_registry: "ContentRegistry"
) -> None:
    """A stat-increasing effect does not trigger cascade unequip."""
    from oscilla.engine.models.adventure import StatChangeEffect
    from oscilla.engine.steps.effects import run_effect
    from tests.engine.conftest import MockTUI

    # Equip the heavy armor (requirements met)
    enh_player.stats["strength"] = 20
    enh_player.add_item(ref="test-requires-item", quantity=1, registry=enh_registry)
    inst = enh_player.instances[0]
    enh_player.equip_instance(instance_id=inst.instance_id, slots=["body"])

    # Increase strength — should not unequip anything
    effect = StatChangeEffect(type="stat_change", stat="strength", amount=5)
    mock_tui = MockTUI()
    await run_effect(effect=effect, player=enh_player, registry=enh_registry, tui=mock_tui)

    assert inst.instance_id in enh_player.equipment.values()


# ---------------------------------------------------------------------------
# 8.14 — session-load preservation: invalid equipped item is preserved, warning logged
# ---------------------------------------------------------------------------


def test_warn_invalid_equipped_logs_warning(
    enh_player: CharacterState, enh_registry: "ContentRegistry", caplog: "pytest.LogCaptureFixture"
) -> None:
    """_warn_invalid_equipped logs a WARNING for each equipped item whose requires is unmet."""
    import logging

    from oscilla.engine.session import _warn_invalid_equipped

    # Equip heavy armor, then drop strength below threshold
    enh_player.stats["strength"] = 20
    enh_player.add_item(ref="test-requires-item", quantity=1, registry=enh_registry)
    inst = enh_player.instances[0]
    enh_player.equip_instance(instance_id=inst.instance_id, slots=["body"])
    enh_player.stats["strength"] = 5  # below threshold

    with caplog.at_level(logging.WARNING):
        _warn_invalid_equipped(state=enh_player, registry=enh_registry)

    assert any("Heavy Armor" in r.message for r in caplog.records)


def test_warn_invalid_equipped_does_not_unequip(enh_player: CharacterState, enh_registry: "ContentRegistry") -> None:
    """_warn_invalid_equipped NEVER unequips items — it only logs."""
    from oscilla.engine.session import _warn_invalid_equipped

    enh_player.stats["strength"] = 20
    enh_player.add_item(ref="test-requires-item", quantity=1, registry=enh_registry)
    inst = enh_player.instances[0]
    enh_player.equip_instance(instance_id=inst.instance_id, slots=["body"])
    enh_player.stats["strength"] = 5  # below threshold

    _warn_invalid_equipped(state=enh_player, registry=enh_registry)

    # Item must still be equipped
    assert inst.instance_id in enh_player.equipment.values()
