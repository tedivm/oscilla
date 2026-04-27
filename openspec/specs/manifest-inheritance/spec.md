# Manifest Inheritance

## Purpose

Enables content authors to declare base manifests and have child manifests inherit unspecified `spec` fields, reducing repetition across variant entity families (enemy variants, weapon tiers, location clusters).

## Requirements

### Requirement: metadata.base declares inheritance from a same-kind manifest

Any manifest MAY declare `metadata.base: <name>` to inherit all unspecified `spec` fields from another manifest of the same `kind`. The child's own `spec` fields replace the base's fields. The base manifest MUST be of the same `kind` as the child.

#### Scenario: Child inherits missing required fields from base

- **WHEN** an `Enemy` manifest with `metadata.base: goblin-base` omits `stats` but the base `goblin-base` defines `stats`
- **THEN** the merged result includes the base's `stats` and Pydantic validation passes

#### Scenario: Child overrides base field values

- **WHEN** a child manifest declares `metadata.base: goblin-base` and provides its own `displayName`
- **THEN** the child's `displayName` replaces the base's `displayName` in the merged result

#### Scenario: Kind mismatch is a hard load error

- **WHEN** an `Enemy` manifest declares `metadata.base: iron-sword` where `iron-sword` is an `Item`
- **THEN** the loader raises a `ContentLoadError` identifying the kind mismatch

---

### Requirement: metadata.abstract marks a manifest as template-only

Any manifest MAY declare `metadata.abstract: true` to mark itself as a template-only base. Abstract manifests SHALL NOT be registered in the `ContentRegistry`. Abstract manifests MAY omit required `spec` fields that their children will supply.

#### Scenario: Abstract manifest is not in the registry

- **WHEN** a manifest with `metadata.abstract: true` is loaded
- **THEN** it does not appear in the `ContentRegistry` under its kind's namespace

#### Scenario: Abstract manifest can omit required fields

- **WHEN** an abstract `Enemy` manifest omits `displayName` (a required field)
- **THEN** the loader does not raise a validation error for the abstract manifest itself

#### Scenario: Abstract manifest serves as base for concrete children

- **WHEN** an abstract `Enemy` named `goblin-base` is referenced as `metadata.base` by a concrete `Enemy` named `goblin-scout`
- **THEN** `goblin-scout` inherits all `spec` fields from `goblin-base` and is registered in the `ContentRegistry`

---

### Requirement: Chained inheritance is resolved via topological sort

A manifest that declares `metadata.base` may itself serve as a base for another manifest. The loader SHALL resolve inheritance chains in dependency order (bases before children) using topological sort.

#### Scenario: Three-level chain resolves correctly

- **WHEN** `goblin-king` inherits from `goblin-chief`, which inherits from `goblin-base`
- **THEN** `goblin-king` receives all fields from both `goblin-chief` and `goblin-base`, with `goblin-king`'s own fields taking final precedence

#### Scenario: Concrete manifest can serve as a base

- **WHEN** a non-abstract `Enemy` named `base-enemy` is referenced as `metadata.base` by another `Enemy`
- **THEN** `base-enemy` is both registered in the `ContentRegistry` and available as a base for inheritance

---

### Requirement: Circular inheritance chains are detected and produce a hard error

The loader SHALL detect circular inheritance chains during topological sort. The error SHALL include the full cycle path.

#### Scenario: Two-manifest cycle is detected

- **WHEN** `enemy-a` has `metadata.base: enemy-b` and `enemy-b` has `metadata.base: enemy-a`
- **THEN** the loader raises a `ContentLoadError` with a message containing `a → b → a`

#### Scenario: Three-manifest cycle is detected

- **WHEN** `a` inherits from `b`, `b` inherits from `c`, and `c` inherits from `a`
- **THEN** the loader raises a `ContentLoadError` with a message containing the full cycle path

---

### Requirement: Missing base references produce a hard error

If a manifest declares `metadata.base: <name>` and no manifest with that name exists (of the same kind), the loader SHALL raise a `ContentLoadError`.

#### Scenario: Unknown base name is a hard error

- **WHEN** an `Enemy` declares `metadata.base: nonexistent` and no `Enemy` named `nonexistent` exists
- **THEN** the loader raises a `ContentLoadError` identifying the child manifest and the missing base name

#### Scenario: Base name exists under wrong kind produces precise error

- **WHEN** an `Enemy` declares `metadata.base: iron-sword` and `iron-sword` exists as an `Item`
- **THEN** the loader raises a `ContentLoadError` indicating the name exists but is not an `Enemy`

---

### Requirement: Field extension with + suffix extends lists and dicts

Child manifests MAY use a `+` suffix on field names (e.g., `grants_skills_equipped+:`) to extend the base's list or dict rather than replacing it. The `+` is stripped from the key in the final merged result.

#### Scenario: List extension appends to base list

- **WHEN** a base `Item` has `grants_skills_equipped: [parry]` and a child declares `grants_skills_equipped+: [riposte]`
- **THEN** the merged result has `grants_skills_equipped: [parry, riposte]`

#### Scenario: Dict extension merges child dict onto base dict

- **WHEN** a base `Item` has `equip: {slots: [main_hand]}` and a child declares `equip+: {combat_damage_formulas: [...]}`
- **THEN** the merged `equip` dict contains both `slots` and `combat_damage_formulas`

#### Scenario: Nested + keys recurse into dict values

- **WHEN** a child declares `equip+: {stat_modifiers+: [{stat: hp, amount: 2}]}` and the base has `equip: {stat_modifiers: [{stat: attack, amount: 1}]}`
- **THEN** the merged `equip.stat_modifiers` is `[{stat: attack, amount: 1}, {stat: hp, amount: 2}]`

#### Scenario: + key with no corresponding base value uses child value as-is

- **WHEN** a child declares `foo+: [bar]` and the base has no `foo` field
- **THEN** the merged result has `foo: [bar]` (the `+` is stripped)

#### Scenario: + key type mismatch falls back to child value

- **WHEN** a base has `foo: [a]` and a child declares `foo+: {key: value}` (dict instead of list)
- **THEN** the merged result has `foo: {key: value}` (the child value replaces the base value, and the `+` is stripped)

---

### Requirement: Abstract and concrete name collisions are hard errors

An abstract manifest and a concrete manifest SHALL NOT share the same `name` within the same `kind`. Two abstract manifests SHALL NOT share the same `name` within the same `kind`.

#### Scenario: Abstract and concrete with same name is a load error

- **WHEN** two manifests of kind `Enemy` both have `metadata.name: goblin-base`, one with `abstract: true` and one without
- **THEN** the loader raises a `ContentLoadError` identifying the name collision

#### Scenario: Two abstract manifests with same name is a load error

- **WHEN** two manifests of kind `Enemy` both have `metadata.name: goblin-base` and both have `abstract: true`
- **THEN** the loader raises a `ContentLoadError` identifying the duplicate abstract name

---

### Requirement: Unused abstract manifests produce a load warning

Abstract manifests that are never referenced as `metadata.base` by any other manifest SHALL produce a `LoadWarning`. The warning SHALL include the manifest's kind and name.

#### Scenario: Unused abstract produces warning

- **WHEN** an abstract `Enemy` named `unused-base` is loaded and no other manifest references it as `metadata.base`
- **THEN** a `LoadWarning` is emitted identifying the unused abstract manifest

---

### Requirement: JSON Schema includes abstract permissive arm

The generated JSON Schema SHALL include a permissive arm that matches when `metadata.abstract` is `true`. This arm SHALL allow incomplete `spec` content without requiring all normally-required fields.

#### Scenario: Abstract manifest passes JSON Schema validation

- **WHEN** an abstract manifest with an incomplete `spec` is validated against the generated JSON Schema
- **THEN** validation passes without errors for the missing required fields

---

### Requirement: JSON Schema includes + field variants

The generated JSON Schema SHALL include `<fieldname>+` sibling properties for every list and dict field in each spec type. The description SHALL indicate that the field extends the inherited value.

#### Scenario: grants_skills_equipped+ is in the schema

- **WHEN** the JSON Schema for `Item` is generated
- **THEN** it contains a `grants_skills_equipped+` property with the same type as `grants_skills_equipped`
