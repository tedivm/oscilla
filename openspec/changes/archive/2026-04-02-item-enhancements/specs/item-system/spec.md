## MODIFIED Requirements

### Requirement: Consumable items carry typed use effects

An `ItemSpec` MAY declare a `use_effects` list. Each entry SHALL be a valid `Effect` from the same discriminated union used by adventure steps (heal, xp_grant, stat_change, stat_set, milestone_grant, item_drop, use_item, end_adventure). When a player uses an item, every effect in `use_effects` SHALL be dispatched through the same `run_effect()` function used by adventures.

The `consumed_on_use: bool` field (defaulting to `True`) controls whether the item is removed from inventory after use when the item has no `charges`. Items with an empty `use_effects` list are not "usable" and SHALL NOT present a Use action in the TUI. When both `charges` and `consumed_on_use: true` are declared on the same item, the content loader SHALL raise a validation error.

#### Scenario: Healing potion restores HP and is consumed

- **WHEN** a player uses a healing-potion with `use_effects: [{type: heal, amount: 30}]` and `consumed_on_use: true`
- **THEN** the player's HP increases by up to 30 (capped at max_hp), and the potion quantity decreases by 1

#### Scenario: Reusable item is not consumed

- **WHEN** a player uses an item with `consumed_on_use: false`
- **THEN** the item's effects fire but the item remains in inventory at the same quantity

#### Scenario: Stackable + equip spec is a load error

- **WHEN** an Item manifest declares both `stackable: true` and an `equip` spec
- **THEN** the content loader raises a validation error

#### Scenario: charges + consumed_on_use is a load error

- **WHEN** an Item manifest declares both `charges: 3` and `consumed_on_use: true`
- **THEN** the content loader raises a validation error

---

### Requirement: Equippable items declare slots and stat modifiers

An `ItemSpec` MAY declare an `equip` spec. The `equip` spec SHALL contain:

- `slots: List[str]` (at least one entry) — the equipment slot names this item occupies
- `stat_modifiers: List[StatModifier]` — flat stat deltas applied while the item is equipped
- `requires: Condition | None` — optional equip prerequisite condition, evaluated against base stats only

Each `StatModifier` SHALL have a `stat` name and an `amount` (int or float, positive or negative). All `slots` values SHALL reference slot names defined in the game's `CharacterConfig.equipment_slots`. All `stat` values SHALL reference stat names defined in `CharacterConfig`. These SHALL be validated at content load time.

The `requires` condition, when present, SHALL be evaluated using `evaluate(condition, player, registry=None)` — passing `None` for the registry so that `CharacterStatCondition` evaluates against base stats, not `effective_stats()`. This prevents circular reasoning (equipping an item that requires a stat bonus provided by that same item).

#### Scenario: Sword with stat modifier loads correctly

- **WHEN** an Item manifest declares `equip: {slots: [main_hand], stat_modifiers: [{stat: strength, amount: 2}]}`
- **THEN** the manifest is parsed into an `EquipSpec` with one slot and one `StatModifier`

#### Scenario: Unknown slot is a load error

- **WHEN** an Item manifest declares an `equip.slots` value not present in `CharacterConfig.equipment_slots`
- **THEN** the content loader raises a `LoadError` identifying the item and the unknown slot

#### Scenario: Unknown stat in modifier is a load error

- **WHEN** an Item manifest declares a `stat_modifiers[].stat` name not in `CharacterConfig`
- **THEN** the content loader raises a `LoadError` identifying the item and the unknown stat name

#### Scenario: Equip requirement blocks equip when not met

- **WHEN** an item has `requires: {character_stat: {name: strength, gte: 15}}` and the player's base strength is 12
- **THEN** the TUI equip action is blocked and a message explains the unmet requirement

#### Scenario: Equip requirement uses base stats only

- **WHEN** an item has `requires: {character_stat: {name: strength, gte: 15}}`, the player's base strength is 12, and a passive effect would bring effective strength to 16
- **THEN** the equip action is still blocked (base stats used, not effective stats)

#### Scenario: Equip requirement with milestone

- **WHEN** an item has `requires: {milestone: unlocked-magic}` and the player has that milestone
- **THEN** the item can be equipped normally

---

## ADDED Requirements

### Requirement: Items carry author-defined labels

`ItemSpec` SHALL accept a `labels: List[str]` field (default `[]`). Each string is a label name declared in `GameSpec.item_labels`. Labels are display metadata and have no direct engine behavioral effect. They are accessible via the condition system (`item_held_label`, `any_item_equipped`), the template system (exposed in inventory context), and the loader warning system.

#### Scenario: Item with declared label loads correctly

- **WHEN** an Item manifest declares `labels: [legendary]` and `legendary` is declared in `GameSpec.item_labels`
- **THEN** the manifest loads without error or warning, and `item.spec.labels` contains `"legendary"`

#### Scenario: Item with undeclared label produces a warning

- **WHEN** an Item manifest declares `labels: [legendery]` and `legendery` is not declared in `GameSpec.item_labels`
- **THEN** the content loader emits a `LoadWarning` identifying the item and the undeclared label with a `suggestion` hint

#### Scenario: Item with no labels loads correctly (opt-in)

- **WHEN** an Item manifest omits `labels`
- **THEN** the manifest loads without any error or warning regardless of `GameSpec.item_labels`

---

### Requirement: Item charges track per-instance remaining uses

`ItemSpec` SHALL accept a `charges: int | None` field (default `None`, minimum value 1). When `charges` is set, the item represents a multi-use consumable that tracks uses per instance. `ItemInstance` SHALL carry `charges_remaining: int | None` — populated from `item.spec.charges` at item grant time, `None` for items without charges.

Each time the item is used, `charges_remaining` SHALL decrement by 1. When `charges_remaining` reaches 0, the instance SHALL be removed from the player's inventory automatically. The `consumed_on_use` path is bypassed entirely when `charges` is set on the item.

`charges` SHALL only be valid on non-stackable, non-`consumed_on_use` items. The content loader SHALL reject:

- `charges` + `consumed_on_use: true` on the same item (validation error)
- `charges` + `stackable: true` on the same item (validation error)

#### Scenario: Charged item use decrements charges_remaining

- **WHEN** a player uses an item with `charges: 5` and the instance has `charges_remaining: 5`
- **THEN** `charges_remaining` is now 4 and the instance remains in inventory

#### Scenario: Last charge removes instance

- **WHEN** a player uses an item with `charges_remaining: 1`
- **THEN** `charges_remaining` reaches 0 and the instance is removed from `player.instances`

#### Scenario: Charges populated at grant time

- **WHEN** an item with `charges: 3` is granted via `item_grant` or `item_drop` effect
- **THEN** the new `ItemInstance` has `charges_remaining: 3`

#### Scenario: charges + consumed_on_use is a load error

- **WHEN** an Item manifest declares both `charges: 3` and `consumed_on_use: true`
- **THEN** the content loader raises a validation error

#### Scenario: charges + stackable is a load error

- **WHEN** an Item manifest declares both `charges: 3` and `stackable: true`
- **THEN** the content loader raises a validation error

#### Scenario: Charges roundtrip through serialization

- **WHEN** a `CharacterState` containing an `ItemInstance` with `charges_remaining: 2` is serialized and deserialized
- **THEN** `charges_remaining` is preserved as 2
