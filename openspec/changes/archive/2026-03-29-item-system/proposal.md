## Why

Items exist in the manifest registry but have no active mechanics. A healing potion cannot be drunk, an iron sword grants no stat bonus when equipped, and there is no way to open an inventory screen at all. The `ItemSpec` model already carries placeholder `effect` and `stats` dict fields, but they are untyped blobs that nothing reads. This change gives items behavioral teeth — consumables apply real effects when used, equippable items contribute flat stat modifiers while worn, and players interact with their inventory both inside and outside of adventures.

The design also future-proofs for Terraria-style unique item modifiers (e.g., "Legendary Iron Sword") by introducing a split inventory model now — non-stackable items become `ItemInstance` objects tracked by UUID — without implementing the modifier rolling system itself.

## What Changes

- Replace `kind` on `ItemSpec` with `category` (a display-only UI hint for inventory sorting), and remove the untyped `slot`, `stats: Dict`, and `effect: Dict` fields
- Add `use_effects: List[Effect]` and `consumed_on_use: bool = True` to `ItemSpec` so any item can carry a typed effect payload using the same grammar as adventure effects
- Add `equip: EquipSpec | None` to `ItemSpec`; `EquipSpec` declares `slots: List[str]` (supports multi-slot items like a two-handed sword) and `stat_modifiers: List[StatModifier]` in list form to allow future per-condition modifiers
- Add `equipment_slots: List[SlotDefinition]` to `CharacterConfigSpec`; each slot has a `name`, `displayName`, an `accepts` list of item categories, an optional `requires: Condition` for conditional slots, and `show_when_locked: bool = False`
- Split `CharacterState.inventory` into `stacks: Dict[str, int]` (stackable items) and `instances: List[ItemInstance]` (non-stackable items tracked by UUID); add `ItemInstance` dataclass with `instance_id`, `item_ref`, and `modifiers: Dict` placeholder
- Change `CharacterState.equipment` from `Dict[str, str]` (slot → item_ref) to `Dict[str, UUID]` (slot → instance_id) to feed the future modifier system without a schema break
- Add `CharacterState.effective_stats(registry)` that sums equipped item `stat_modifiers` on top of base stats; returns the same shape as `stats`
- Add an optional `registry` parameter to `conditions.evaluate()`; `CharacterStatCondition` evaluates against effective stats when the registry is supplied, base stats when it is not
- Add `UseItemEffect` to the adventure effect union and the `run_effect()` dispatcher; it looks up an item by ref in the player's inventory, runs its `use_effects`, and respects `consumed_on_use`
- Add a new Alembic migration adding a `character_iteration_item_instances` table and updating `character_iteration_equipment` to store `instance_id` instead of `item_ref`
- Add a TUI inventory screen accessible both inside and outside of adventures showing stacks (with Use button for consumables), instances (with Equip/Unequip), and equipped slots; equipping a multi-slot item that displaces already-equipped items requires a confirmation dialog before proceeding
- When a slot's `requires` condition is no longer satisfied by the player's state, keep the equipped item in place, log a warning, and surface the inconsistency in the TUI status panel
- Update POC content (`the-example-kingdom`) to use `category`, add `use_effects` to healing potions, and add `equip` specs to weapons and armor with real `stat_modifiers`

## Capabilities

### New Capabilities

- `item-system`: Typed item behaviors — consumables with full effect payloads, equippable items with stat modifier computation, and a split inventory model separating fungible stacks from unique instances.

### Modified Capabilities

- `player-state`: `CharacterState` gains `stacks`/`instances` inventory split, `equipment` keyed by `instance_id`, and `effective_stats()` method. Serialization and deserialization updated accordingly.
- `condition-evaluator`: `evaluate()` gains an optional `registry` argument; `CharacterStatCondition` uses effective stats when the registry is provided.
- `adventure-pipeline`: Gains `UseItemEffect` in the effect union; item use (but not equipping) is available inside adventure steps.
- `manifest-system`: `ItemSpec` is restructured; `CharacterConfigSpec` gains `equipment_slots`.
- `poc-content`: POC item manifests updated to the new schema with real consumable and equip specs.
- `textual-tui`: Gains a full inventory management screen.

## Impact

- **`oscilla/engine/models/item.py`**: `ItemSpec` restructured; new `EquipSpec`, `StatModifier` models added
- **`oscilla/engine/models/character_config.py`**: `CharacterConfigSpec` gains `equipment_slots`; new `SlotDefinition` model added
- **`oscilla/engine/models/adventure.py`**: `UseItemEffect` added to the `Effect` union
- **`oscilla/engine/character.py`**: `CharacterState` gains split inventory, `ItemInstance` dataclass, `effective_stats()` method; serialization updated
- **`oscilla/engine/conditions.py`**: `evaluate()` signature gains optional `registry` parameter
- **`oscilla/engine/steps/effects.py`**: `UseItemEffect` handler added to `run_effect()`
- **`oscilla/engine/tui.py`** / **`oscilla/engine/session.py`**: Inventory screen wired in
- **`oscilla/services/character.py`**: Save/load updated for split inventory and instance-keyed equipment
- **`db/versions/`**: New Alembic migration for `character_iteration_item_instances` table and updated `character_iteration_equipment`
- **`content/the-example-kingdom/`**: All item manifests updated to `category`, consumable and equip specs added
- **`tests/engine/`**: New test modules for consumable effects, equipment, effective stats, inventory split, condition evaluator with registry, and TUI inventory screen
