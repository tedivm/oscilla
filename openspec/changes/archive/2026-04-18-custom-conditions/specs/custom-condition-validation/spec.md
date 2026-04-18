## NEW Requirements

### Requirement: Dangling `type: custom` references raise `ContentLoadError`

`oscilla/engine/loader.py` SHALL add `_validate_custom_condition_refs()` called from `validate_references()`.

For every manifest in the content package, every `CustomConditionRef.name` referenced anywhere in a condition field SHALL be verified to match the `metadata.name` of a declared `CustomCondition` manifest in the same package.

A `LoadError` SHALL be raised for each dangling reference with the message:
`"type: custom condition references unknown CustomCondition: '<name>'"` where `<name>` is the missing manifest name.

The following manifest kinds and their condition fields are covered by this check:

- `CustomCondition` — `spec.condition` (the body itself may reference other custom conditions)
- `Location` — `spec.unlock`, `spec.effective_unlock`, and per-adventure-entry `requires`
- `Region` — `spec.unlock`, `spec.effective_unlock`
- `Adventure` — `spec.requires`, per-step `requires` (choice step options), per-step `bypass` (passive steps), per-step `condition` (stat-check steps)
- `Item` — `spec.equip.requires` (when `equip` is present)
- `Skill` — `spec.requires`
- `Game` — per-passive-effect `condition`

#### Scenario: dangling ref in Adventure requires produces one LoadError

- **GIVEN** a content package containing an `Adventure` whose `spec.requires` is `CustomConditionRef(name="missing")`
- **AND** no `CustomCondition` manifest named `"missing"` is present
- **WHEN** `validate_references()` is called
- **THEN** exactly one `LoadError` is returned
- **AND** its `message` contains `"missing"` and `"unknown CustomCondition"`

#### Scenario: valid ref produces no errors

- **GIVEN** a content package containing a `CustomCondition` named `"gate"` and an `Adventure` whose `spec.requires` is `CustomConditionRef(name="gate")`
- **WHEN** `validate_references()` is called
- **THEN** no `LoadError` related to `"gate"` is returned

#### Scenario: dangling ref in CustomCondition body produces a LoadError

- **GIVEN** a `CustomCondition` manifest whose body is `CustomConditionRef(name="also-missing")`
- **AND** no `CustomCondition` named `"also-missing"` exists
- **WHEN** `validate_references()` is called
- **THEN** a `LoadError` is returned mentioning `"also-missing"`

---

### Requirement: Circular `CustomCondition` dependency chains raise `ContentLoadError`

`_validate_custom_condition_refs()` SHALL perform a depth-first search over the `CustomCondition` dependency graph (edges are `CustomConditionRef` references within `CustomCondition` bodies only — non-`CustomCondition` manifests are not graph nodes).

Any back-edge — a reference to a node currently on the active DFS path — SHALL produce a `LoadError` with the message:
`"circular reference in CustomCondition '<node>': <path>"` where `<path>` is the full cycle rendered as `a → b → a`.

Dangling references (reported in the dangling check) are excluded from cycle detection to avoid false positives.

#### Scenario: direct self-reference produces a LoadError

- **GIVEN** a single `CustomCondition` named `"self-ref"` whose body is `CustomConditionRef(name="self-ref")`
- **WHEN** `validate_references()` is called
- **THEN** a `LoadError` is returned
- **AND** its `message` contains `"circular reference"` and `"self-ref"`

#### Scenario: indirect cycle A→B→A produces a LoadError with full path

- **GIVEN** `CustomCondition "a"` whose body is `CustomConditionRef(name="b")`
- **AND** `CustomCondition "b"` whose body is `CustomConditionRef(name="a")`
- **WHEN** `validate_references()` is called
- **THEN** at least one `LoadError` is returned
- **AND** its `message` contains `"a → b → a"` or `"b → a → b"`

#### Scenario: valid linear chain A→B produces no cycle errors

- **GIVEN** `CustomCondition "a"` whose body is `CustomConditionRef(name="b")`
- **AND** `CustomCondition "b"` whose body is `LevelCondition(value=5)` (no further refs)
- **WHEN** `validate_references()` is called
- **THEN** no cycle `LoadError` is returned

#### Scenario: `validate_references()` wires both new validators

- **GIVEN** a content package with a dangling ref and a cycle in different custom conditions
- **WHEN** `validate_references()` is called
- **THEN** both a dangling-ref `LoadError` and a cycle `LoadError` are present in the returned list
