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

`CharacterState.effective_stats(registry)` SHALL loop through `registry.game.spec.passive_effects` after accumulating equipped item modifiers. For each passive effect whose `condition` evaluates true (using `evaluate(condition, player, registry=None)`), the `stat_modifiers` SHALL be added to the result using the same accumulation logic as equipped item modifiers.

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

`CharacterState.available_skills(registry)` SHALL loop through `registry.game.spec.passive_effects` after accumulating item-granted skills. For each passive effect whose condition evaluates true (using `evaluate(condition, player, registry=None)`), the `skill_grants` list SHALL be added to the result.

#### Scenario: Passive effect condition true — skill included

- **WHEN** a passive effect has condition `item_equipped: rangers-cloak` and the player has the cloak equipped, and the effect grants `hunters-mark`
- **THEN** `available_skills(registry)` includes `"hunters-mark"`

#### Scenario: Passive effect condition false — skill excluded

- **WHEN** the passive effect condition is false
- **THEN** `available_skills(registry)` does not include `"hunters-mark"` (assuming it is not in `known_skills` or from another item grant)

---

### Requirement: Passive effect conditions are evaluated against base stats only

Inside `effective_stats()` and `available_skills()`, passive effect conditions SHALL be evaluated by calling `evaluate(condition, player, registry=None)`. This ensures:

- `CharacterStatCondition` evaluates against base stats (not effective stats), preventing infinite recursion.
- `item_held_label` and `any_item_equipped` conditions inside passive effects always return false (they require a registry); authors using label-based passive conditions SHALL be warned at load time.

A `LoadWarning` SHALL be emitted at content load time if a passive effect's condition tree contains an `item_held_label` or `any_item_equipped` node, because these conditions can never evaluate to true when used inside passive effects.

#### Scenario: Passive condition with item_held_label emits a load warning

- **WHEN** a passive effect's condition is `item_held_label: cursed`
- **THEN** the content loader emits a `LoadWarning` indicating the condition will never activate inside a passive effect, and suggesting `item_equipped` as an alternative

#### Scenario: Passive condition with item_equipped works correctly

- **WHEN** a passive effect's condition is `item_equipped: rangers-cloak`
- **THEN** the condition evaluates correctly inside `effective_stats()` and `available_skills()` because `item_equipped` does not require a registry

---

### Requirement: Passive effect references are validated at load time

All `stat` names in `stat_modifiers` and all `skill_grants` strings SHALL be validated against defined stats in `CharacterConfig` and loaded Skill manifests respectively. Unknown references SHALL produce a `LoadError`.

#### Scenario: Unknown stat in passive effect stat_modifier is a load error

- **WHEN** a passive effect declares `stat_modifiers: [{stat: nonexistent-stat, amount: 5}]`
- **THEN** the content loader raises a `LoadError`

#### Scenario: Unknown skill in passive effect skill_grants is a load error

- **WHEN** a passive effect declares `skill_grants: [nonexistent-skill]`
- **THEN** the content loader raises a `LoadError`
