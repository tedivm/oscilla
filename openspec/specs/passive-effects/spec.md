# Passive Effects

## Purpose

A mechanism for declaring stat modifiers and skill grants that are active only while a condition is true, evaluated continuously against the current character state. Passive effects activate and deactivate automatically as state changes — no adventure step or explicit trigger required. They are declared globally in `game.yaml`.

---

## Requirements

### Requirement: GameSpec declares passive effects

`GameSpec` SHALL accept a `passive_effects: List[PassiveEffect]` field (default `[]`). Each `PassiveEffect` SHALL have:

- `name: str` — unique identifier within the package (informational only; used in logging)
- `condition: Condition` — any standard condition; evaluated against base stats (see registry constraint below)
- `stat_modifiers: List[StatModifier]` — flat stat deltas added to `effective_stats()` when condition is true
- `skill_grants: List[str]` — skill refs included in `available_skills()` when condition is true

`passive_effects` is opt-in: packages that do not declare it behave identically to the pre-passive-effects engine.

#### Scenario: passive_effects declared in game.yaml loads correctly

- **WHEN** a `game.yaml` declares a `passive_effects` entry with a condition, stat_modifiers, and skill_grants
- **THEN** the `GameManifest` parses and `registry.game.spec.passive_effects` contains the entry

#### Scenario: Empty passive_effects is valid

- **WHEN** a `game.yaml` omits `passive_effects`
- **THEN** the manifest loads without error and passive effects default to `[]`

---

### Requirement: passive_effects contribute to effective_stats()

`CharacterState.effective_stats(registry)` SHALL loop through `registry.game.spec.passive_effects` after accumulating equipped item modifiers. For each passive effect whose `condition` evaluates true (using `evaluate(condition, player, registry=registry)`), the `stat_modifiers` SHALL be added to the result using the same accumulation logic as equipped item modifiers.

If `registry` is `None` or `registry.game` is `None`, the passive effects loop is skipped.

#### Scenario: Passive effect condition true — stat modifier applied

- **WHEN** a passive effect has condition `item_equipped: rangers-cloak` and the player has the cloak equipped, and the effect adds `dexterity: +5`
- **THEN** `effective_stats(registry)["dexterity"]` equals base dexterity + 5

#### Scenario: Passive effect condition false — stat modifier not applied

- **WHEN** the same passive effect condition is false (cloak not equipped)
- **THEN** `effective_stats(registry)["dexterity"]` equals base dexterity (no bonus)

#### Scenario: No registry — passive effects skipped

- **WHEN** `effective_stats(registry=None)` is called
- **THEN** passive effects are not evaluated and the result equals base stats only

#### Scenario: Multiple passive effects with same stat accumulate additively

- **WHEN** two passive effects both grant `strength: +3` and both conditions are true
- **THEN** `effective_stats(registry)["strength"]` equals base strength + 6

---

### Requirement: passive_effects contribute to available_skills()

`CharacterState.available_skills(registry)` SHALL loop through `registry.game.spec.passive_effects` after accumulating item-granted skills. For each passive effect whose condition evaluates true (using `evaluate(condition, player, registry=registry)`), the `skill_grants` list SHALL be added to the result.

#### Scenario: Passive effect condition true — skill included

- **WHEN** a passive effect has condition `item_equipped: rangers-cloak` and the player has the cloak equipped, and the effect grants `hunters-mark`
- **THEN** `available_skills(registry)` includes `"hunters-mark"`

#### Scenario: Passive effect condition false — skill excluded

- **WHEN** the passive effect condition is false
- **THEN** `available_skills(registry)` does not include `"hunters-mark"` (assuming it is not in `known_skills` or from another item grant)

---

### Requirement: Passive effect conditions are evaluated with the full registry

Inside `effective_stats()` and `available_skills()`, passive effect conditions SHALL be evaluated by calling `evaluate(condition, player, registry=registry)`. This allows all registry-dependent condition types — including `item_held_label`, `any_item_equipped`, `game_calendar_*`, and `type: custom` — to evaluate correctly inside passive effects.

`CharacterStatCondition` with `stat_source: effective` and `SkillCondition` are forbidden in passive effects and are rejected at load time as `ContentLoadError` (see requirements below), preventing infinite recursion via `effective_stats()` and `available_skills()`.

#### Scenario: Passive condition with item_held_label evaluates correctly

- **WHEN** a passive effect's condition is `item_held_label: sword` and the player holds an item with that label
- **THEN** the condition evaluates to `True` inside `effective_stats()` and `available_skills()`

#### Scenario: Passive condition with item_equipped works correctly

- **WHEN** a passive effect's condition is `item_equipped: rangers-cloak`
- **THEN** the condition evaluates correctly inside `effective_stats()` and `available_skills()`

---

### Requirement: Passive effect references are validated at load time

All `stat` names in `stat_modifiers` and all `skill_grants` strings SHALL be validated against defined stats in `CharacterConfig` and loaded Skill manifests respectively. Unknown references SHALL produce a `LoadError`.

#### Scenario: Unknown stat in passive effect stat_modifier is a load error

- **WHEN** a passive effect declares `stat_modifiers: [{stat: nonexistent-stat, amount: 5}]`
- **THEN** the content loader raises a `LoadError`

#### Scenario: Unknown skill in passive effect skill_grants is a load error

- **WHEN** a passive effect declares `skill_grants: [nonexistent-skill]`
- **THEN** the content loader raises a `LoadError`

---

### Requirement: `character_stat (stat_source: effective)` in a passive effect is a load-time `ContentLoadError`

A `LoadError` SHALL be raised for any passive effect whose condition tree contains — directly or transitively through `CustomConditionRef` chains — a `CharacterStatCondition` with `stat_source == "effective"`.

The error message SHALL be:
`"passive_effects[<idx>] condition uses character_stat with stat_source: effective (causes infinite recursion via effective_stats()); this type cannot be used in passive effects"`

#### Scenario: character_stat stat_source: effective in passive effect raises LoadError

- **GIVEN** a `Game` manifest with a passive effect whose condition is `CharacterStatCondition(stat="level", stat_source="effective", gte=5)`
- **WHEN** content validation runs
- **THEN** a `LoadError` is raised
- **AND** its message contains `"passive_effects[0]"` and `"character_stat"` and `"effective"`

#### Scenario: character_stat stat_source: base in passive effect is valid

- **GIVEN** a `Game` manifest with a passive effect whose condition is `CharacterStatCondition(stat="level", stat_source="base", gte=5)`
- **WHEN** content validation runs
- **THEN** no `LoadError` is raised for this passive effect

---

### Requirement: `skill` condition in a passive effect is a load-time `ContentLoadError`

A `LoadError` SHALL be raised for any passive effect whose condition tree contains — directly or transitively — a `SkillCondition`.

The error message SHALL be:
`"passive_effects[<idx>] condition uses skill (causes infinite recursion via available_skills()); this type cannot be used in passive effects"`

#### Scenario: skill condition in passive effect raises LoadError

- **GIVEN** a `Game` manifest with a passive effect whose condition is `SkillCondition(name="fireball")`
- **WHEN** content validation runs
- **THEN** a `LoadError` is raised
- **AND** its message contains `"passive_effects[0]"` and `"skill"`

---

### Requirement: Banned types transitively inside a `type: custom` passive condition also raise `ContentLoadError`

If a passive effect condition tree contains a `CustomConditionRef`, the validator SHALL resolve the body of that `CustomConditionRef` and recursively check it for banned types (`character_stat` with `stat_source: effective` and `skill`).

If a banned type is found anywhere in the resolved chain, a `LoadError` SHALL be raised on the passive effect (not on the `CustomCondition` manifest itself). Previously-seen `CustomConditionRef` names during transitive resolution SHALL be tracked in a `seen` set to prevent infinite loops on cyclic chains.

#### Scenario: type: custom in passive effect whose body contains a banned type raises LoadError

- **GIVEN** a `CustomCondition "has-skill"` whose body is `SkillCondition(name="fireball")`
- **AND** a `Game` manifest with a passive effect whose condition is `CustomConditionRef(name="has-skill")`
- **WHEN** content validation runs
- **THEN** a `LoadError` is raised for the passive effect
- **AND** its message mentions `"passive_effects[0]"` and `"skill"`

#### Scenario: type: custom in passive effect with a safe body does not raise LoadError

- **GIVEN** a `CustomCondition "gate"` whose body is `LevelCondition(value=5)`
- **AND** a `Game` manifest with a passive effect whose condition is `CustomConditionRef(name="gate")`
- **WHEN** content validation runs
- **THEN** no `LoadError` is raised for this passive effect

---

### Requirement: `_validate_passive_effects()` no longer warns about `item_held_label` or `any_item_equipped`

`_validate_passive_effects()` in `oscilla/engine/loader.py` SHALL NOT emit `LoadWarning` entries for `ItemHeldLabelCondition`, `AnyItemEquippedCondition`, or `CharacterStatCondition(stat_source="effective")`, because:

- `item_held_label` and `any_item_equipped` now evaluate correctly in passive effects (registry is passed).
- `character_stat (stat_source: effective)` and `skill` are now hard `LoadError` in validation.

The function SHALL remain as the extension point for future passive effect warnings.

#### Scenario: item_held_label in passive effect produces no LoadWarning

- **GIVEN** a `Game` manifest with a passive effect using `ItemHeldLabelCondition`
- **WHEN** `_validate_passive_effects()` is called
- **THEN** the returned list is empty

---

### Requirement: Archetype passive effects contribute to effective_stats and available_skills

`CharacterState.effective_stats(registry)` and `CharacterState.available_skills(registry)` SHALL loop over `player.archetypes` in addition to the existing global `passive_effects` loop. For each held archetype, the engine SHALL look up the corresponding `ArchetypeManifest` in `registry.archetypes` and evaluate its `passive_effects` entries using the same logic as global passive effects. The archetype being held is the implicit outer condition; no explicit `has_archetype` condition is required on archetype-scoped passive effects.

This evaluation occurs after the global `passive_effects` loop. If the archetype is not in `registry.archetypes` (content drift), it is silently skipped.

#### Scenario: Archetype passive stat modifier applies when archetype is held

- **WHEN** a character holds the `warrior` archetype and its `passive_effects` declare `stat_modifiers: [{stat: strength, amount: 2}]`
- **THEN** `effective_stats(registry)["strength"]` equals base strength + 2

#### Scenario: Archetype passive skill grant applies when archetype is held

- **WHEN** a character holds the `ranger` archetype and its `passive_effects` declare `skill_grants: [tracking]`
- **THEN** `available_skills(registry)` includes `"tracking"`

#### Scenario: Archetype passive effects from two held archetypes accumulate

- **WHEN** a character holds both `warrior` (passive: `strength: +2`) and `berserker` (passive: `strength: +3`)
- **THEN** `effective_stats(registry)["strength"]` equals base strength + 5

#### Scenario: No registry — archetype passive effects are skipped

- **WHEN** `effective_stats(registry=None)` is called
- **THEN** archetype passive effects are not evaluated (same behavior as global passive effects)
