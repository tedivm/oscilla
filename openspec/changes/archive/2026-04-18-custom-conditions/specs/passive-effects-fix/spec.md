## MODIFIED Requirements

### Requirement: Passive effects receive the full registry during condition evaluation

`oscilla/engine/character.py` SHALL pass `registry=registry` (not `registry=None`) to all `evaluate()` calls made within passive effect loops.

The affected call sites are:

- Two occurrences in `effective_stats()`: the loop over `registry.game.spec.passive_effects` and the loop over archetype passive effects.
- Two occurrences in `available_skills()`: the loop over `registry.game.spec.passive_effects` and the loop over archetype passive effects.

The runtime behavior change is that `item_held_label`, `any_item_equipped`, `game_calendar_*`, and `type: custom` (with a safe body) will now evaluate correctly in passive effects instead of silently returning `False`.

#### Scenario: item_held_label condition in a passive effect now evaluates correctly

- **GIVEN** a `Game` manifest with a passive effect whose condition is `ItemHeldLabelCondition(label="sword")`
- **AND** a player who holds an item with label `"sword"`
- **WHEN** `player.effective_stats(registry)` is called
- **THEN** the passive effect's stat modifiers are applied (condition evaluated `True`)

#### Scenario: type: custom condition in a passive effect resolves and evaluates

- **GIVEN** a registry with `CustomCondition "gate-level-5"` whose body is `LevelCondition(value=5)`
- **AND** a `Game` manifest with a passive effect whose condition is `CustomConditionRef(name="gate-level-5")`
- **AND** a player at level 7
- **WHEN** `player.effective_stats(registry)` is called
- **THEN** the passive effect's stat modifiers are applied

---

### Requirement: `character_stat (stat_source: effective)` in a passive effect is a load-time `ContentLoadError`

`oscilla/engine/loader.py` SHALL add `_validate_passive_effect_conditions()` called from `validate_references()`.

A `LoadError` SHALL be raised for any passive effect whose condition tree contains — directly or transitively through `CustomConditionRef` chains — a `CharacterStatCondition` with `stat_source == "effective"`.

The error message SHALL be:
`"passive_effects[<idx>] condition uses character_stat with stat_source: effective (causes infinite recursion via effective_stats()); this type cannot be used in passive effects"`

#### Scenario: character_stat stat_source: effective in passive effect raises LoadError

- **GIVEN** a `Game` manifest with a passive effect whose condition is `CharacterStatCondition(stat="level", stat_source="effective", gte=5)`
- **WHEN** `validate_references()` is called
- **THEN** a `LoadError` is returned
- **AND** its `message` contains `"passive_effects[0]"` and `"character_stat"` and `"effective"`

#### Scenario: character_stat stat_source: base in passive effect is valid

- **GIVEN** a `Game` manifest with a passive effect whose condition is `CharacterStatCondition(stat="level", stat_source="base", gte=5)`
- **WHEN** `validate_references()` is called
- **THEN** no `LoadError` is returned for this passive effect

---

### Requirement: `skill` condition in a passive effect is a load-time `ContentLoadError`

A `LoadError` SHALL be raised for any passive effect whose condition tree contains — directly or transitively — a `SkillCondition`.

The error message SHALL be:
`"passive_effects[<idx>] condition uses skill (causes infinite recursion via available_skills()); this type cannot be used in passive effects"`

#### Scenario: skill condition in passive effect raises LoadError

- **GIVEN** a `Game` manifest with a passive effect whose condition is `SkillCondition(name="fireball")`
- **WHEN** `validate_references()` is called
- **THEN** a `LoadError` is returned
- **AND** its `message` contains `"passive_effects[0]"` and `"skill"`

---

### Requirement: Banned types transitively inside a `type: custom` passive condition also raise `ContentLoadError`

If a passive effect condition tree contains a `CustomConditionRef`, `_validate_passive_effect_conditions()` SHALL resolve the body of that `CustomConditionRef` and recursively check it for banned types.

If a banned type is found anywhere in the resolved chain, a `LoadError` SHALL be raised on the passive effect (not on the `CustomCondition` manifest itself), since the passive effect is the context that makes the type forbidden.

Previously-seen `CustomConditionRef` names during transitive resolution SHALL be tracked in a `seen` set to prevent infinite loops on cyclic chains (cycles are already reported separately by `_validate_custom_condition_refs()`).

#### Scenario: type: custom in passive effect whose body contains a banned type raises LoadError

- **GIVEN** a `CustomCondition "has-skill"` whose body is `SkillCondition(name="fireball")`
- **AND** a `Game` manifest with a passive effect whose condition is `CustomConditionRef(name="has-skill")`
- **WHEN** `validate_references()` is called
- **THEN** a `LoadError` is returned for the passive effect
- **AND** its `message` mentions `"passive_effects[0]"` and `"skill"`

#### Scenario: type: custom in passive effect with a safe body does not raise LoadError

- **GIVEN** a `CustomCondition "gate"` whose body is `LevelCondition(value=5)`
- **AND** a `Game` manifest with a passive effect whose condition is `CustomConditionRef(name="gate")`
- **WHEN** `validate_references()` is called
- **THEN** no `LoadError` is returned for this passive effect

---

### Requirement: `_validate_passive_effects()` no longer warns about `item_held_label` or `any_item_equipped`

`_validate_passive_effects()` in `oscilla/engine/loader.py` SHALL be updated to remove the `LoadWarning` branches for `ItemHeldLabelCondition`, `AnyItemEquippedCondition`, and `CharacterStatCondition(stat_source="effective")`, as:

- `item_held_label` and `any_item_equipped` now work correctly in passive effects.
- `character_stat (stat_source: effective)` and `skill` are now hard errors in `validate_references()`.

The function SHALL return an empty list after this change (or retain any unrelated warnings if added in future work). It SHALL NOT be deleted — it remains the extension point for future passive effect warnings.

#### Scenario: item_held_label in passive effect produces no LoadWarning

- **GIVEN** a `Game` manifest with a passive effect using `ItemHeldLabelCondition`
- **WHEN** `_validate_passive_effects()` is called
- **THEN** the returned list is empty
