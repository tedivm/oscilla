# Item System

## Purpose

The item system defines the behavioral mechanics for items: typed consumable effects using the adventure effect grammar, equippable items with flat stat modifiers, conditional equipment slot definitions in CharacterConfig, a split inventory model separating fungible stacks from unique instances, and effective stat computation from equipped items.

---

## Requirements

### Requirement: Item category is a display-only field

The `category` field on `ItemSpec` SHALL be a required string used solely as a UI hint for inventory grouping and loot table filtering. No engine behavior SHALL branch on `category`. The old `kind` field is replaced by `category`.

#### Scenario: Category used for inventory grouping

- **WHEN** the inventory screen renders the player's items
- **THEN** items are grouped by their `category` value in the display

#### Scenario: Category missing is a load error

- **WHEN** an Item manifest omits `category`
- **THEN** the content loader raises a validation error

---

### Requirement: Consumable items carry typed use effects

An `ItemSpec` MAY declare a `use_effects` list. Each entry SHALL be a valid `Effect` from the same discriminated union used by adventure steps (heal, xp_grant, stat_change, stat_set, milestone_grant, item_drop, use_item, end_adventure). When a player uses an item, every effect in `use_effects` SHALL be dispatched through the same `run_effect()` function used by adventures.

The `consumed_on_use: bool` field (defaulting to `True`) controls whether the item is removed from inventory after use. Items with an empty `use_effects` list are not "usable" and SHALL NOT present a Use action in the TUI.

#### Scenario: Healing potion restores HP and is consumed

- **WHEN** a player uses a healing-potion with `use_effects: [{type: heal, amount: 30}]` and `consumed_on_use: true`
- **THEN** the player's HP increases by up to 30 (capped at max_hp), and the potion quantity decreases by 1

#### Scenario: Reusable item is not consumed

- **WHEN** a player uses an item with `consumed_on_use: false`
- **THEN** the item's effects fire but the item remains in inventory at the same quantity

#### Scenario: Stackable + equip spec is a load error

- **WHEN** an Item manifest declares both `stackable: true` and an `equip` spec
- **THEN** the content loader raises a validation error

---

### Requirement: Equippable items declare slots and stat modifiers

An `ItemSpec` MAY declare an `equip` spec. The `equip` spec SHALL contain:

- `slots: List[str]` (at least one entry) — the equipment slot names this item occupies
- `stat_modifiers: List[StatModifier]` — flat stat deltas applied while the item is equipped

Each `StatModifier` SHALL have a `stat` name and an `amount` (int or float, positive or negative). All `slots` values SHALL reference slot names defined in the game's `CharacterConfig.equipment_slots`. All `stat` values SHALL reference stat names defined in `CharacterConfig`. These SHALL be validated at content load time.

#### Scenario: Sword with stat modifier loads correctly

- **WHEN** an Item manifest declares `equip: {slots: [main_hand], stat_modifiers: [{stat: strength, amount: 2}]}`
- **THEN** the manifest is parsed into an `EquipSpec` with one slot and one `StatModifier`

#### Scenario: Unknown slot is a load error

- **WHEN** an Item manifest declares an `equip.slots` value not present in `CharacterConfig.equipment_slots`
- **THEN** the content loader raises a `LoadError` identifying the item and the unknown slot

#### Scenario: Unknown stat in modifier is a load error

- **WHEN** an Item manifest declares a `stat_modifiers[].stat` name not in `CharacterConfig`
- **THEN** the content loader raises a `LoadError` identifying the item and the unknown stat name

---

### Requirement: Equipment slots are defined in CharacterConfig

`CharacterConfigSpec` SHALL support an `equipment_slots: List[SlotDefinition]` field. Each `SlotDefinition` SHALL contain:

- `name: str` — unique slot identifier
- `displayName: str` — human-readable label shown in the TUI
- `accepts: List[str]` — item categories the slot accepts; empty means accept all
- `requires: Condition | None` — optional condition gate; evaluated against base stats only
- `show_when_locked: bool = False` — whether a locked slot renders in the TUI

Slot names within a single `CharacterConfig` SHALL be unique. The `requires` condition SHALL be evaluated against the player's base stats (not effective stats) to prevent circular reasoning.

#### Scenario: Conditional slot is hidden when locked

- **WHEN** a slot defines `requires: {type: milestone, name: owns-horse}` and `show_when_locked: false`, and the player does not have that milestone
- **THEN** the slot does not appear in the inventory screen at all

#### Scenario: Conditional slot shows locked indicator

- **WHEN** a slot defines `requires` condition unmet by the player and `show_when_locked: true`
- **THEN** the slot renders with a locked visual indicator and its `displayName`

#### Scenario: Duplicate slot names are a load error

- **WHEN** a `CharacterConfig` manifest declares two `equipment_slots` entries with the same `name`
- **THEN** the content loader raises a validation error

---

### Requirement: Inventory is split between stacks and instances

`CharacterState` SHALL maintain two separate inventory collections:

- `stacks: Dict[str, int]` — stackable items (item_ref → quantity)
- `instances: List[ItemInstance]` — non-stackable items, each tracked by a unique `instance_id: UUID`

`ItemInstance` SHALL carry `instance_id: UUID`, `item_ref: str`, and `modifiers: Dict[str, int | float]` (an empty dict in v1, reserved for the future modifier system). Items with `stackable: true` go into `stacks`; items with `stackable: false` go into `instances`. The `equipment` mapping SHALL key by `instance_id: UUID` pointing to slot names.

#### Scenario: Adding a stackable item increments stacks

- **WHEN** `add_item("healing-potion", 1)` is called and `healing-potion` has `stackable: true`
- **THEN** `stacks["healing-potion"]` increases by 1

#### Scenario: Adding a non-stackable item creates an instance

- **WHEN** `add_item("iron-sword", 1)` is called and `iron-sword` has `stackable: false`
- **THEN** a new `ItemInstance` with a fresh UUID is appended to `instances`

#### Scenario: Serialization roundtrip preserves both collections

- **WHEN** a `CharacterState` with both stacks and instances is serialized via `to_dict()` and deserialized via `from_dict()`
- **THEN** all stack quantities and all instance records (instance_id, item_ref, modifiers) are preserved exactly

---

### Requirement: Effective stats are computed on the fly from equipped items

`CharacterState.effective_stats(registry: ContentRegistry)` SHALL return a stat dict equal to base `stats` plus the sum of all `stat_modifiers` from the currently equipped items. The base `stats` dict SHALL never be mutated. If the same `instance_id` occupies multiple slots (multi-slot item), its modifiers SHALL be counted only once.

#### Scenario: No equipment — effective stats equal base stats

- **WHEN** `effective_stats()` is called with an empty `equipment` dict
- **THEN** the returned dict equals `stats` exactly

#### Scenario: Equipped sword adds strength

- **WHEN** an iron-sword with `stat_modifiers: [{stat: strength, amount: 2}]` is equipped and the player's base `strength` is 10
- **THEN** `effective_stats()["strength"]` equals 12

#### Scenario: Multi-slot item counted once

- **WHEN** a broadsword with `slots: [main_hand, off_hand]` and `stat_modifiers: [{stat: strength, amount: 5}]` is equipped in both slots
- **THEN** `effective_stats()["strength"]` equals base strength + 5, not base strength + 10

---

### Requirement: CharacterStatCondition evaluates effective stats when registry is provided

The `evaluate()` function SHALL accept an optional `registry: ContentRegistry | None = None` parameter. When `registry` is `None`, `CharacterStatCondition` evaluates against `player.stats` (base). When `registry` is provided, it evaluates against `player.effective_stats(registry)`. All other condition types are unaffected by the presence or absence of `registry`.

#### Scenario: Condition passes via equipment bonus

- **WHEN** a condition requires `strength >= 12`, the player's base strength is 10, and an iron-sword (+2 strength) is equipped
- **AND** `evaluate()` is called with `registry` provided
- **THEN** the condition evaluates to `True`

#### Scenario: Condition uses base stats without registry

- **WHEN** the same condition and player state, but `evaluate()` called with `registry=None`
- **THEN** the condition evaluates to `False`

---

### Requirement: UseItemEffect enables in-adventure item consumption

The `Effect` union SHALL include `UseItemEffect` with an `item: str` field referencing an item by manifest name. When dispatched, it SHALL locate the item in the player's inventory, execute all `use_effects` from the item's manifest, and remove the item if `consumed_on_use: true`. If the item is not in the player's inventory, a TUI error message SHALL be shown and no mutation occurs. If the item ref is unknown in the registry, a warning SHALL be logged. Equipping items via adventure effects is NOT supported.

#### Scenario: In-adventure potion use

- **WHEN** an adventure step fires `UseItemEffect(item: "healing-potion")` and the player holds one
- **THEN** the potion's `use_effects` are dispatched and the potion is removed from inventory

#### Scenario: Item not in inventory is a no-op with error

- **WHEN** `UseItemEffect` fires for an item not in the player's inventory
- **THEN** a TUI error is shown, no mutation occurs, and the adventure continues

---

### Requirement: Slot reconciliation keeps items in place with a visible warning

If the player's state is loaded and an equipped item occupies a slot whose `requires` condition is no longer satisfied, the equipped item SHALL remain in the slot (no silent inventory mutation). A `WARNING` SHALL be logged. The TUI status panel SHALL surface the inconsistency visibly to the player.

#### Scenario: Locked slot with equipped item shows warning

- **WHEN** a character is loaded with an item in a conditional slot whose condition is no longer met
- **THEN** the item remains equipped, a logger warning is emitted, and the TUI status panel shows a notification about the slot inconsistency

---

### Requirement: Multi-slot equip requires confirmation when displacing gear

When equipping an item whose `slots` list includes any slot already occupied by a different item, the TUI SHALL present a confirmation dialog listing the items that will be returned to inventory. If the player confirms, the displacement proceeds. If the player cancels, no state changes occur. This confirmation requirement applies only to the TUI inventory screen; `UseItemEffect` in adventures does not equip items.

#### Scenario: Two-handed sword displaces off-hand item with confirmation

- **WHEN** the player equips a broadsword with `slots: [main_hand, off_hand]` and a dagger is in `off_hand`
- **THEN** the TUI shows "Equipping Broadsword will unequip: Rusty Dagger. Continue?" before proceeding

---

### Requirement: ItemSpec declares skill grants for equipped items

`ItemSpec` SHALL accept `grants_skills_equipped: List[str]` (default `[]`). Each entry is a Skill manifest name. Grants are ephemeral: the skills enter `available_skills()` only while the item occupies an equipment slot. These are NOT added to `known_skills`.

#### Scenario: Equipped item contributes to available_skills

- **WHEN** a player equips an item with `grants_skills_equipped: ["power-strike"]`
- **THEN** `available_skills(registry)` includes `"power-strike"`

#### Scenario: Unequipped item no longer contributes

- **WHEN** a player removes an equipped item from its slot
- **THEN** skills from `grants_skills_equipped` are no longer in `available_skills()`

---

### Requirement: ItemSpec declares skill grants for held items

`ItemSpec` SHALL accept `grants_skills_held: List[str]` (default `[]`). Each entry is a Skill manifest name. Grants are active when the item is present anywhere in the player's inventory (stacks quantity ≥ 1 or any instance), whether equipped or not. Consuming or dropping the last copy removes the grant.

#### Scenario: Held scroll adds skill without equipping

- **WHEN** a player holds a scroll in their stacks with `grants_skills_held: ["fireball"]`
- **THEN** `available_skills(registry)` includes `"fireball"` without equipping it

#### Scenario: Consuming last scroll removes skill from available_skills

- **WHEN** a player uses and consumes the last instance of a scroll that was granting a skill
- **THEN** the skill is no longer in `available_skills()`

---

### Requirement: Skill refs in items are validated at load time

All skill refs in `grants_skills_equipped` and `grants_skills_held` SHALL be validated against loaded Skill manifest names at content load time. Unknown refs SHALL cause a load-time error.

#### Scenario: Unknown skill ref is rejected

- **WHEN** an Item manifest references a skill ref that has no corresponding Skill manifest
- **THEN** the content loader raises a validation error identifying the item and ref

#### Scenario: Valid skill refs load cleanly

- **WHEN** all skill refs in an item manifest correspond to loaded Skill manifests
- **THEN** the item loads without error
