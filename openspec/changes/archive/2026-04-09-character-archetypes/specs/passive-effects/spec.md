## ADDED Requirements

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
