# Loot Tables

## Purpose

Defines the `LootTable` manifest kind for authoring named, reusable loot definitions that can be referenced from `item_drop` effects and enemy manifests. Establishes the `groups`-based schema used by all loot sources.

---

## Requirements

### Requirement: LootTable manifest kind

A `LootTable` manifest kind SHALL exist with `kind: LootTable` and a `spec` containing:

- `displayName: str` (required)
- `description: str` (optional, defaults to empty string)
- `groups: List[LootGroup]` (required, minimum one group)

The previous `loot: List[LootEntry]` field is removed and replaced by `groups`. `LootTable` manifests SHALL be loaded and registered in `registry.loot_tables`. Names SHALL be unique within the `LootTable` kind. `LootTable` SHALL be a creatable kind (`oscilla content create loot-table` SHALL be supported).

#### Scenario: Valid LootTable with groups loads successfully

- **WHEN** the content loader reads a valid `LootTable` manifest with at least one group
- **THEN** it is registered in `registry.loot_tables` with no errors

#### Scenario: LootTable with empty groups list is a load error

- **WHEN** a `LootTable` manifest declares `groups: []`
- **THEN** the content loader raises a Pydantic validation error

#### Scenario: LootTable is creatable via CLI

- **WHEN** an author runs `oscilla content create loot-table <name>`
- **THEN** a valid scaffolded LootTable YAML file is generated at the appropriate path

---

### Requirement: Load-time cross-reference validation for loot_ref

The content loader SHALL validate every `loot_ref` in every `ItemDropEffect` across all adventure manifests after the full registry is assembled. Any `loot_ref` that does not resolve to a `LootTable` manifest SHALL produce a `LoadError`.

#### Scenario: Invalid loot_ref produces a load error

- **WHEN** an adventure manifest contains an `item_drop` effect with `loot_ref: "nonexistent"`
- **THEN** the content loader reports a `LoadError` identifying the adventure and the bad ref, and the content package fails to load

---

### Requirement: ItemDropEffect uses groups exclusively

`ItemDropEffect` SHALL accept exactly one of:

- `groups: List[LootGroup]` — inline group definitions (minimum one group)
- `loot_ref: str` — reference to a named `LootTable` manifest

Declaring both or neither SHALL be a Pydantic `model_validator` error at load time. The `loot` (flat list) and `count` (top-level roll count) fields are removed entirely.

When `loot_ref` is specified, the engine SHALL resolve it against `registry.loot_tables`. If the reference does not resolve, a `LoadError` is produced at load time (same validation as before). The fallback to enemy loot via `resolve_loot_entries` is removed.

#### Scenario: ItemDropEffect with inline groups is valid

- **WHEN** an `item_drop` effect declares `groups:` with at least one group
- **THEN** the manifest loads successfully

#### Scenario: ItemDropEffect with loot_ref is valid

- **WHEN** an `item_drop` effect declares `loot_ref: "treasure-hoard"` and a `LootTable` named `"treasure-hoard"` exists
- **THEN** the manifest loads successfully and resolves to that table's groups at runtime

#### Scenario: ItemDropEffect with both groups and loot_ref is a load error

- **WHEN** an `item_drop` effect declares both `groups:` and `loot_ref:`
- **THEN** the content loader raises a Pydantic validation error

#### Scenario: ItemDropEffect with neither groups nor loot_ref is a load error

- **WHEN** an `item_drop` effect declares neither `groups:` nor `loot_ref:`
- **THEN** the content loader raises a Pydantic validation error

#### Scenario: loot_ref not found in loot_tables is a load error

- **WHEN** an `item_drop` effect uses `loot_ref: "nonexistent"`
- **THEN** the content loader reports a `LoadError`; the content package fails to load

---

### Requirement: EnemySpec.loot uses List[LootGroup]

`EnemySpec.loot` SHALL accept `List[LootGroup]` (not `List[LootEntry]`). Enemies with simple single-pool drops use a single group with no `requires`. The field name `loot` is retained on the enemy manifest for semantic clarity.

#### Scenario: Enemy with groups-based loot loads and drops items

- **WHEN** an enemy manifest declares `loot: [{entries: [{item: sword}]}]`
- **THEN** it loads successfully and the loot resolves to the group model at runtime

#### Scenario: Enemy with empty loot list is valid

- **WHEN** an enemy manifest omits `loot:` or declares `loot: []`
- **THEN** it loads successfully and no loot drops occur in combat
