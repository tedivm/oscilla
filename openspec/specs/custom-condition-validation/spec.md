# Custom Condition Validation

## Purpose

Defines load-time validation rules that catch dangling `CustomConditionRef` references and circular dependency chains among `CustomCondition` manifests, raising `ContentLoadError` before any game state is created.

---

## Requirements

### Requirement: Dangling `type: custom` references raise `ContentLoadError`

At content load time, every `CustomConditionRef` that appears anywhere in the content package — in `Location`, `Region`, `Adventure`, `Item`, `Skill`, `Game`, or `CustomCondition` manifests — SHALL be checked against `registry.custom_conditions`. If the referenced `name` is not registered, the loader SHALL raise a `ContentLoadError` identifying the dangling reference and the manifest in which it was found.

#### Scenario: location unlock condition references an unknown CustomCondition

- **GIVEN** a `Location` manifest with `unlock_condition: { type: custom, name: nonexistent }`
- **WHEN** content is loaded
- **THEN** the loader raises a `ContentLoadError` naming `"nonexistent"` and the location manifest

#### Scenario: item condition references an unknown CustomCondition

- **GIVEN** an `Item` manifest with a condition that contains `{ type: custom, name: ghost-gate }`
- **WHEN** content is loaded and `"ghost-gate"` is not in `registry.custom_conditions`
- **THEN** the loader raises a `ContentLoadError`

#### Scenario: all references present — no error

- **GIVEN** every `CustomConditionRef` in the package resolves to a registered `CustomCondition` manifest
- **WHEN** content is loaded
- **THEN** no `ContentLoadError` is raised for dangling references

---

### Requirement: Circular `CustomCondition` dependency chains raise `ContentLoadError`

At content load time, the dependency graph among `CustomCondition` manifests SHALL be inspected for cycles using depth-first search back-edge detection. If any cycle is found, the loader SHALL raise a `ContentLoadError` naming the cycle participants.

#### Scenario: direct self-reference raises ContentLoadError

- **GIVEN** a `CustomCondition` manifest with `metadata.name: self-ref` whose condition is `{ type: custom, name: self-ref }`
- **WHEN** content is loaded
- **THEN** the loader raises a `ContentLoadError` identifying the cycle

#### Scenario: two-node cycle raises ContentLoadError

- **GIVEN** `CustomCondition` `"a"` references `"b"` and `"b"` references `"a"`
- **WHEN** content is loaded
- **THEN** the loader raises a `ContentLoadError` identifying the `a → b → a` cycle

#### Scenario: valid shared diamond dependency does not raise

- **GIVEN** both `"c"` and `"d"` reference `"e"`, and no back-edges exist
- **WHEN** content is loaded
- **THEN** no cycle error is raised
