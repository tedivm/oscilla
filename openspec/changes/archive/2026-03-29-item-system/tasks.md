## 0. Update Item Manifest Model

- [x] 0.1 In `oscilla/engine/models/item.py`, add `StatModifier` model with `stat: str` and `amount: int | float`
- [x] 0.2 Add `EquipSpec` model with `slots: List[str]` (min_length=1) and `stat_modifiers: List[StatModifier] = []`
- [x] 0.3 Replace `kind`, `slot`, `stats`, and `effect` on `ItemSpec` with `category: str`, `use_effects: List[Effect] = []`, `consumed_on_use: bool = True`, and `equip: EquipSpec | None = None`
- [x] 0.4 Import the `Effect` union from `oscilla.engine.models.adventure` in `item.py` (watch for circular imports — use `TYPE_CHECKING` guard if needed)
- [x] 0.5 Add a `model_validator(mode="after")` to `ItemSpec` that raises `ValueError` if `stackable: true` and `equip` is set
- [x] 0.6 Update `oscilla/engine/models/__init__.py` to export `StatModifier`, `EquipSpec`, and the updated `ItemSpec`

## 1. Update CharacterConfig Manifest Model

- [x] 1.1 In `oscilla/engine/models/character_config.py`, add `SlotDefinition` model with `name: str`, `displayName: str`, `accepts: List[str] = []`, `requires: Condition | None = None`, and `show_when_locked: bool = False`
- [x] 1.2 Add `equipment_slots: List[SlotDefinition] = []` to `CharacterConfigSpec`
- [x] 1.3 Add a `model_validator` to `CharacterConfigSpec` that raises `ValueError` if any two `SlotDefinition` entries share the same `name`

## 2. Add UseItemEffect to the Adventure Effect Union

- [x] 2.1 Add `UseItemEffect` model in `oscilla/engine/models/adventure.py` with `type: Literal["use_item"]` and `item: str`
- [x] 2.2 Add `UseItemEffect` to the `Effect` `Union` and update the `Field(discriminator="type")` list

## 3. Update CharacterState — Split Inventory and Effective Stats

- [x] 3.1 Add `ItemInstance` dataclass to `oscilla/engine/character.py` with `instance_id: UUID`, `item_ref: str`, and `modifiers: Dict[str, int | float]` (default empty dict)
- [x] 3.2 Rename `inventory` → `stacks` on `CharacterState`; add `instances: List[ItemInstance]` field
- [x] 3.3 Change `equipment: Dict[str, str]` → `equipment: Dict[str, UUID]` on `CharacterState`
- [x] 3.4 Update `add_item(ref, quantity)` to check `stackable` on the registry item manifest and route to `stacks` or `instances` accordingly; raise `ValueError` if `stackable` is False and `quantity != 1`
- [x] 3.5 Update `remove_item(ref, quantity)` to handle both `stacks` and `instances`
- [x] 3.6 Replace the existing `equip(item_ref, slot)` method with `equip_instance(instance_id: UUID, slots: List[str])` that: checks all slots are valid for the item's category, clears displaced instances back to `instances`, writes all slot entries in `equipment`, and raises `ValueError` if the instance is not present
- [x] 3.7 Add `unequip_slot(slot: str)` method that removes all `equipment` entries for the instance occupying that slot and returns the instance to `instances`
- [x] 3.8 Add `check_displacement(instance_id: UUID, slots: List[str]) -> List[str]` method returning human-readable descriptions of items that would be displaced (used by the TUI confirmation dialog)
- [x] 3.9 Add `effective_stats(registry: ContentRegistry) -> Dict[str, int | float | bool | None]` method that starts with a copy of `stats`, then for each distinct instance_id in `equipment.values()`, looks up the instance and its item manifest, and sums all `stat_modifiers` onto the copy
- [x] 3.10 Update `new_character()` classmethod — no change needed (stacks and instances start empty)
- [x] 3.11 Update `to_dict()` to serialize `stacks`, `instances` (each as `{instance_id, item_ref, modifiers}`), and `equipment` (UUIDs as strings)
- [x] 3.12 Update `from_dict()` to deserialize `stacks`, `instances` (reconstructing `ItemInstance` objects), and `equipment` (strings back to UUIDs); drop unknown instance item_refs with a `logger.warning`
- [x] 3.13 Run `uv run pytest tests/engine/test_character.py -x` to confirm existing tests pass; update any tests that reference the old `inventory` field or `equip()` method

## 4. Update the Condition Evaluator

- [x] 4.1 Add `registry: ContentRegistry | None = None` parameter to `evaluate()` in `oscilla/engine/conditions.py`
- [x] 4.2 In the `CharacterStatCondition` case branch, use `player.effective_stats(registry)` if `registry is not None`, else `player.stats`, to get the stat value
- [x] 4.3 Propagate `registry` recursively to all `evaluate()` calls inside `AllCondition`, `AnyCondition`, and `NotCondition` branches
- [x] 4.4 Update all call sites across `oscilla/engine/` that call `evaluate()` to verify they pass `registry` when appropriate (adventure pipeline pool filtering and step conditions should pass registry; content loader validation calls should not)

## 5. Add UseItemEffect Dispatcher

- [x] 5.1 Import `UseItemEffect` in `oscilla/engine/steps/effects.py`
- [x] 5.2 Add `UseItemEffect` case to the `match effect:` block in `run_effect()`: resolve item manifest, check inventory, run `use_effects` recursively, conditionally consume

## 6. Content Loader Validation

- [x] 6.1 In `oscilla/engine/loader.py` (or wherever cross-reference validation runs), add validation that all `equip.slots` values on each `ItemManifest` exist in the game's `CharacterConfig.equipment_slots` names
- [x] 6.2 Add validation that all `stat_modifiers[].stat` values on each `ItemManifest` exist in the `CharacterConfig` stat definitions
- [x] 6.3 Add validation that `UseItemEffect.item` references an item that exists in the item registry (same pattern as existing loot table validation)

## 7. Database Migration

- [x] 7.1 Run `make create_migration MESSAGE="add item instances and update equipment schema"` to scaffold the migration
- [x] 7.2 In the generated migration, add the `character_iteration_item_instances` table: `instance_id TEXT`, `iteration_id INTEGER NOT NULL FK`, `item_ref TEXT NOT NULL`, `modifiers TEXT NOT NULL DEFAULT '{}'`, composite PK `(iteration_id, instance_id)`
- [x] 7.3 In the same migration, drop and recreate `character_iteration_equipment` with `instance_id TEXT NOT NULL` replacing `item_ref TEXT NOT NULL` (one row per slot, multiple rows may share the same `instance_id` for multi-slot items)
- [x] 7.4 Verify the migration runs correctly against SQLite and that both table changes are present
- [x] 7.5 Run `make document_schema` to regenerate `docs/dev/database.md`

## 8. Update Persistence Service

- [x] 8.1 In `oscilla/services/character.py`, update `save_character()` to write `instances` to `character_iteration_item_instances`
- [x] 8.2 Update `save_character()` to write `equipment` as `instance_id` (UUID string) to `character_iteration_equipment`
- [x] 8.3 Update `load_character()` to reconstruct `instances` from `character_iteration_item_instances` rows
- [x] 8.4 Update `load_character()` to reconstruct `equipment` as `Dict[str, UUID]` from `character_iteration_equipment` rows
- [x] 8.5 Update `set_inventory_item()` service function to handle stacks only (instances have separate helpers)
- [x] 8.6 Add `add_item_instance(session, iteration_id, instance: ItemInstance) -> None` service function
- [x] 8.7 Add `remove_item_instance(session, iteration_id, instance_id: UUID) -> None` service function
- [x] 8.8 Update `equip_item()` service function signature from `(slot, item_ref)` to `(slot, instance_id: UUID)`

## 9. Update POC Content — the-example-kingdom

- [x] 9.1 Rename `kind:` → `category:` in all item YAML files under `content/the-example-kingdom/`
- [x] 9.2 Add `equip:` spec with `slots: [main_hand]` and at least one `stat_modifier` to `iron-sword.yaml` and `rusty-dagger.yaml`
- [x] 9.3 Add `equip:` spec to `leather-armour.yaml` and `tough-leather-armour.yaml` with `slots: [armor]` and a defense-related `stat_modifier`
- [x] 9.4 Add `use_effects: [{type: heal, amount: 30}]` and `consumed_on_use: true` to `healing-potion.yaml`
- [x] 9.5 Add stronger `use_effects` to `strong-healing-potion.yaml`
- [x] 9.6 Add `equipment_slots` to `character_config.yaml` in `the-example-kingdom`: define at minimum `head`, `main_hand`, `off_hand`, `armor`; `accepts` should reference the relevant categories
- [x] 9.7 Run `uv run oscilla validate --game the-kingdom` and confirm it exits cleanly
- [x] 9.8 Update `content/testlandia/character_config.yaml` to include `equipment_slots` if any testlandia items have `equip` specs; run `uv run oscilla validate --game testlandia`

## 10. TUI Inventory Screen

- [x] 10.1 Create a new Textual widget/screen `InventoryScreen` in `oscilla/engine/tui.py` (or a new `oscilla/engine/screens/inventory.py`) displaying equipped slots on the left, backpack (stacks + instances) on the right
- [x] 10.2 Render stacks with quantity and a `[Use]` button if the item has `use_effects`
- [x] 10.3 Render instances with `[Equip]` and/or `[Use]` buttons depending on item capabilities
- [x] 10.4 Render equipped slots with `[Unequip]` buttons; show slot `displayName`
- [x] 10.5 Hide slots where `requires` condition is unmet and `show_when_locked: false`; render locked indicator for `show_when_locked: true` slots
- [x] 10.6 Implement `[Use]` action: call `run_effect()` for each `use_effect`, then consume if needed; refresh screen
- [x] 10.7 Implement `[Equip]` action: call `check_displacement()`, show confirmation dialog if displacement list is non-empty, then call `equip_instance()`; hide `[Equip]` buttons inside adventures
- [x] 10.8 Implement `[Unequip]` action: call `unequip_slot()`; refresh screen
- [x] 10.9 Wire `[I] Inventory` button into the main game loop screen (outside adventures)
- [x] 10.10 Wire `[I] Inventory` button into the between-step display inside adventures (in-adventure context suppresses `[Equip]` but shows `[Use]`)
- [x] 10.11 Surface slot reconciliation warnings (slot `requires` condition no longer met) in the TUI status panel

## 11. Tests

- [x] 11.1 Create `tests/engine/test_inventory_split.py` covering add/remove for stacks and instances, serialization round-trip, content-drift on unknown instance refs
- [x] 11.2 Create `tests/engine/test_effective_stats.py` covering empty equipment, single item modifier, overlapping modifiers, multi-slot deduplication, non-mutation of base stats
- [x] 11.3 Create `tests/engine/test_equipment.py` covering equip/unequip single-slot, multi-slot equip displacing gear, category validation, ValueError on missing instance
- [x] 11.4 Create `tests/engine/test_conditions_registry.py` covering base-stats-only path (no registry), effective-stats path (registry), and that other condition types are unaffected
- [x] 11.5 Create `tests/engine/test_consumable_effects.py` covering UseItemEffect dispatch, consumed_on_use true/false, item-not-in-inventory guard, unknown item ref guard
- [x] 11.6 Create `tests/engine/test_item_loader.py` using fixture manifests covering: valid use_effects load, valid equip spec load, stackable+equip rejection, unknown slot rejection, unknown stat in modifier rejection
- [x] 11.7 Create `tests/engine/test_tui_inventory.py` using the `mock_tui` fixture covering: screen render with stacks and instances, use action, equip action with and without displacement confirmation, unequip action, locked slot visibility
- [x] 11.8 Create `tests/engine/test_character_persistence_instances.py` covering: save/load instances round-trip, save/load equipment as instance_id, stacks persisted separately
- [x] 11.9 Add test fixtures under `tests/fixtures/content/item-system/` containing minimal manifests: one stackable consumable item, one non-stackable equippable item, one character config with two equipment slots, one adventure using `UseItemEffect`
- [x] 11.10 Run `make tests` and confirm all checks pass (pytest, ruff, mypy, dapperdata, tomlsort)

## 12. Documentation

- [x] 12.1 Update `docs/authors/content-authoring.md` with the full `ItemSpec` schema reference, `EquipSpec`/`StatModifier` examples, `SlotDefinition` reference, and `UseItemEffect` usage
- [x] 12.2 Update `docs/dev/game-engine.md` with split inventory model, `effective_stats()`, condition evaluator registry param, `UseItemEffect` flow, slot reconciliation behavior
- [x] 12.3 Confirm `docs/dev/database.md` was regenerated by `make document_schema` in task 7.5 and is accurate
