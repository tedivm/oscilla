# Loot Tables

## Purpose

Defines the `LootTable` manifest kind for authoring named, reusable loot definitions that can be referenced from `item_drop` effects and enemy manifests. Establishes a unified `LootEntry` schema used by all loot sources.

---

## Requirements

### Requirement: LootTable manifest kind

A `LootTable` manifest kind SHALL exist with `kind: LootTable` and a `spec` containing:

- `displayName: str` (required)
- `description: str` (optional, defaults to empty string)
- `loot: List[LootEntry]` (required, minimum one entry)

`LootTable` manifests SHALL be loaded and registered in the content registry under `registry.loot_tables`. Names SHALL be unique within the `LootTable` kind.

#### Scenario: Valid LootTable loads successfully

- **WHEN** the content loader reads a valid `LootTable` manifest with at least one loot entry
- **THEN** it is registered in `registry.loot_tables` with no errors

#### Scenario: LootTable with empty loot list is a load error

- **WHEN** a `LootTable` manifest declares `loot: []`
- **THEN** the content loader raises a validation error (Pydantic `min_length=1`)

---

### Requirement: Unified LootEntry schema

All loot sources (LootTable manifests, enemy `loot` fields, and inline `item_drop` loot lists) SHALL use the same `LootEntry` schema with fields:

- `item: str` — manifest name of the item
- `weight: int` (minimum 1) — relative probability weight
- `quantity: int` (minimum 1, default 1) — how many of the item are added when this entry is selected

#### Scenario: LootEntry with quantity grants multiple items

- **WHEN** an item_drop effect resolves a loot entry with `quantity: 3`
- **THEN** the player receives 3 of the specified item in a single selection

#### Scenario: LootEntry with default quantity grants one item

- **WHEN** a loot entry omits `quantity`
- **THEN** the player receives 1 of the specified item (default behavior, backwards compatible)

---

### Requirement: loot_ref on ItemDropEffect

`ItemDropEffect` SHALL accept an optional `loot_ref: str` field as an alternative to the inline `loot` list. Exactly one of `loot` or `loot_ref` SHALL be set; declaring both or neither SHALL be a Pydantic validation error at load time.

When `loot_ref` is specified, the engine SHALL resolve it as follows:

1. Check `registry.loot_tables` for a `LootTable` manifest with that name.
2. If not found, check `registry.enemies` for an enemy manifest with that name and use its `loot` field.
3. If neither resolves, log an error and skip the drop (no crash, no silent success).

#### Scenario: loot_ref resolves to a LootTable manifest

- **WHEN** an `item_drop` effect with `loot_ref: "treasure-hoard"` is executed and `registry.loot_tables` contains a manifest named `"treasure-hoard"`
- **THEN** the loot is drawn from that manifest's `loot` list

#### Scenario: loot_ref resolves to an enemy's loot field

- **WHEN** an `item_drop` effect with `loot_ref: "goblin"` is executed and no `LootTable` named `"goblin"` exists, but an enemy named `"goblin"` does
- **THEN** the loot is drawn from the enemy's `loot` list

#### Scenario: loot_ref not found in either registry

- **WHEN** an `item_drop` effect uses a `loot_ref` that does not resolve to any known LootTable or enemy
- **THEN** an error is logged, the TUI shows no item-found message, and no items are added to inventory

#### Scenario: Both loot and loot_ref declared is a load error

- **WHEN** an `item_drop` effect in a manifest declares both `loot:` and `loot_ref:`
- **THEN** the content loader raises a Pydantic validation error

#### Scenario: Neither loot nor loot_ref declared is a load error

- **WHEN** an `item_drop` effect in a manifest declares neither `loot:` nor `loot_ref:`
- **THEN** the content loader raises a Pydantic validation error

---

### Requirement: Load-time cross-reference validation for loot_ref

The content loader SHALL validate every `loot_ref` in every `ItemDropEffect` across all adventure manifests after the full registry is assembled. Any `loot_ref` that resolves to neither a `LootTable` manifest nor an enemy manifest SHALL produce a `LoadError`.

#### Scenario: Invalid loot_ref produces a load error

- **WHEN** an adventure manifest contains an `item_drop` effect with `loot_ref: "nonexistent"`
- **THEN** the content loader reports a `LoadError` identifying the adventure and the bad ref, and the content package fails to load
