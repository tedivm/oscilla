# Item Charges

## Purpose

A per-instance use counter for non-stackable consumable items that have multiple uses before being fully consumed. Distinct from stackable items (multiple copies) — charges are uses remaining on a single `ItemInstance`. Distinct from `consumed_on_use` — the two systems are mutually exclusive.

---

## Requirements

### Requirement: ItemSpec declares optional charges count

`ItemSpec` SHALL accept a `charges: int | None` field (default `None`, minimum value 1 when set). A `None` value means the item does not use charge tracking. When `charges` is set, each `ItemInstance` created from this item spec SHALL have `charges_remaining` populated from the spec's `charges` value at grant time.

The following combinations are invalid and SHALL be rejected at load time:

- `charges` + `consumed_on_use: true` — mutually exclusive consumption systems
- `charges` + `stackable: true` — charges require per-instance state; stackable items have no individual instances

#### Scenario: Item with charges field parses correctly

- **WHEN** an Item manifest declares `charges: 5`, `stackable: false`, and `consumed_on_use: false`
- **THEN** `item.spec.charges` equals 5

#### Scenario: charges + consumed_on_use is a load error

- **WHEN** an Item manifest declares both `charges: 3` and `consumed_on_use: true`
- **THEN** the content loader raises a validation error

#### Scenario: charges + stackable is a load error

- **WHEN** an Item manifest declares both `charges: 3` and `stackable: true`
- **THEN** the content loader raises a validation error

---

### Requirement: ItemInstance tracks charges_remaining

`ItemInstance` SHALL carry `charges_remaining: int | None` (default `None`). When an item with `charges` set is added to inventory via `add_instance()`, `charges_remaining` SHALL be set to `item.spec.charges`. For items without `charges`, `charges_remaining` SHALL remain `None`. `charges_remaining` is persisted through `to_dict()` / `from_dict()` serialization.

#### Scenario: Granting a charged item populates charges_remaining

- **WHEN** an item with `charges: 3` is granted to the player
- **THEN** the new `ItemInstance` has `charges_remaining: 3`

#### Scenario: Granting an uncharged item leaves charges_remaining None

- **WHEN** an item without `charges` is granted to the player
- **THEN** the new `ItemInstance` has `charges_remaining: None`

#### Scenario: charges_remaining persists through serialization

- **WHEN** a `CharacterState` containing an `ItemInstance` with `charges_remaining: 2` is serialized via `to_dict()` and deserialized via `from_dict()`
- **THEN** `charges_remaining` is preserved as 2

#### Scenario: Existing instances without charges_remaining deserialize correctly

- **WHEN** a previously serialized `ItemInstance` dict without the `charges_remaining` key is deserialized
- **THEN** the instance loads with `charges_remaining=None` (backward compatible)

---

### Requirement: UseItemEffect decrements charges and removes instance at zero

When `UseItemEffect` is dispatched for a non-stackable item with `charges_remaining` set, it SHALL:

1. Apply `use_effects` as normal.
2. Decrement `charges_remaining` by 1.
3. If `charges_remaining` reaches 0 or below, remove the instance from the player's inventory.

The `consumed_on_use` path SHALL NOT be taken for charged items. Because the load-time validator ensures `charges` and `consumed_on_use: true` cannot coexist, only one consumption path will execute per item.

#### Scenario: Using a charged item with multiple charges remaining

- **WHEN** a player uses a charged item with `charges_remaining: 3`
- **THEN** `use_effects` fire and `charges_remaining` becomes 2; the instance remains in inventory

#### Scenario: Using a charged item on the last charge

- **WHEN** a player uses a charged item with `charges_remaining: 1`
- **THEN** `use_effects` fire, `charges_remaining` reaches 0, and the instance is removed from `player.instances`

#### Scenario: Uncharged item follows consumed_on_use path

- **WHEN** a player uses a non-stackable item with `charges_remaining: None` and `consumed_on_use: true`
- **THEN** the existing `consumed_on_use` behavior applies (instance removed after use)
