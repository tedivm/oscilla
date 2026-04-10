## ADDED Requirements

### Requirement: Archetype manifest kind

The engine SHALL support a manifest kind `Archetype`. Each `Archetype` manifest SHALL contain a `spec` block with the following fields:

- `displayName` (string, required): human-readable name for display.
- `description` (string, optional, default `""`): flavor or rules text.
- `gain_effects` (list of Effect, optional, default `[]`): effects dispatched immediately when `archetype_add` fires for this archetype.
- `lose_effects` (list of Effect, optional, default `[]`): effects dispatched immediately when `archetype_remove` fires for this archetype.
- `passive_effects` (list of PassiveEffect, optional, default `[]`): evaluated continuously in `effective_stats()` and `available_skills()` while the archetype is held; the archetype being held is the implicit outer condition; each entry may carry an additional `condition` to refine within that baseline.

#### Scenario: Archetype manifest loads correctly

- **WHEN** a YAML file with `kind: Archetype` and a valid `spec` block is loaded
- **THEN** the manifest is registered in `ContentRegistry.archetypes` under its `name`

#### Scenario: Archetype manifest with empty optional fields is valid

- **WHEN** an `Archetype` manifest declares only `displayName` and omits `gain_effects`, `lose_effects`, and `passive_effects`
- **THEN** the manifest loads without error and all omitted fields default to empty lists

#### Scenario: Multiple archetype manifests load independently

- **WHEN** a content package declares three `Archetype` manifests in separate YAML files across different subdirectories
- **THEN** all three are registered in `ContentRegistry.archetypes` and accessible by name

---

### Requirement: CharacterState tracks held archetypes

`CharacterState` SHALL have an `archetypes: Dict[str, GrantRecord]` field (default empty dict) mapping held archetype names to the tick and timestamp they were granted — the same `GrantRecord` model used by milestones. This field SHALL be:

- Initialized to an empty dict for new characters.
- Persisted in `to_dict()` as a nested dict under the key `"archetypes"` in the form `{name: {"tick": N, "timestamp": N}}`.
- Restored in `from_dict()` supporting two formats for backward compatibility: a legacy list (`["warrior"]`) migrates to `GrantRecord(tick=0, timestamp=0)`; the current nested-dict format is read directly.
- Resilient to content drift: archetype names present in serialized state but absent from the current registry are silently dropped during deserialization.

#### Scenario: New character has empty archetypes dict

- **WHEN** a new character is created
- **THEN** `character.archetypes` is an empty dict

#### Scenario: Archetypes round-trip through serialization

- **WHEN** a character holds archetypes `{"warrior": GrantRecord(tick=5, timestamp=1744000000), "guild_member": GrantRecord(tick=12, timestamp=1744001000)}` and `to_dict()` is called
- **THEN** the result contains `"archetypes": {"warrior": {"tick": 5, "timestamp": 1744000000}, "guild_member": {"tick": 12, "timestamp": 1744001000}}`
- **AND WHEN** `from_dict()` is called with this data
- **THEN** the restored character has `archetypes["warrior"].tick == 5` and `archetypes["guild_member"].tick == 12`

#### Scenario: Legacy list format migrates on deserialization

- **WHEN** serialized character state contains `"archetypes": ["warrior", "guild_member"]` (legacy list format)
- **THEN** the restored character has `archetypes["warrior"] == GrantRecord(tick=0, timestamp=0)` and no error is raised

#### Scenario: Unknown archetype name in serialized state is silently dropped

- **WHEN** serialized character state contains `"archetypes": {"warrior": {"tick": 5, "timestamp": 0}, "deleted-archetype": {"tick": 1, "timestamp": 0}}` but the current registry has no `"deleted-archetype"` manifest
- **THEN** the restored character has `"warrior" in archetypes` and `"deleted-archetype" not in archetypes`

---

### Requirement: Archetype passive effects contribute to effective_stats and available_skills

`CharacterState.effective_stats(registry)` and `CharacterState.available_skills(registry)` SHALL loop over `player.archetypes`. For each held archetype, they SHALL look up the `ArchetypeManifest` in `registry.archetypes` and evaluate its `passive_effects` entries. The archetype being held is the implicit outer condition (no explicit condition needed). Each passive effect entry's optional `condition` field is evaluated as an additional refinement.

If `registry` is `None` or the archetype name is not in `registry.archetypes`, that archetype's passive effects are skipped silently.

#### Scenario: Held archetype passive effect applies stat modifier

- **WHEN** a character holds the `warrior` archetype and `warrior` has a passive effect granting `strength: +5`
- **THEN** `effective_stats(registry)["strength"]` equals base strength + 5

#### Scenario: Not-held archetype passive effect does not apply

- **WHEN** a character does not hold the `mage` archetype and `mage` has a passive effect granting `intelligence: +3`
- **THEN** `effective_stats(registry)["intelligence"]` equals base intelligence (no bonus)

#### Scenario: Held archetype passive effect with additional condition applies when condition is true

- **WHEN** a character holds the `warrior` archetype and the passive effect has a condition `character_stat: {name: level, gte: 5}` and the character's level is 7
- **THEN** the passive effect's stat modifier is applied

#### Scenario: Held archetype passive effect with additional condition does not apply when condition is false

- **WHEN** a character holds the `warrior` archetype and the passive effect has a condition `character_stat: {name: level, gte: 5}` and the character's level is 3
- **THEN** the passive effect's stat modifier is not applied

#### Scenario: Held archetype passive effect contributes skill grant to available_skills

- **WHEN** a character holds the `ranger` archetype and `ranger` has a passive effect with `skill_grants: [tracking]`
- **THEN** `available_skills(registry)` includes `"tracking"`

---

### Requirement: Archetype cross-references are hard load errors

Any condition predicate or effect that references an archetype name not present in the loaded set of `Archetype` manifests SHALL produce a `LoadError`. The content package SHALL fail to load. This applies to: `has_archetype.name`, each entry in `has_all_archetypes.names`, each entry in `has_any_archetype.names`, `archetype_add.name`, and `archetype_remove.name`.

#### Scenario: has_archetype condition referencing unknown archetype is a load error

- **WHEN** a manifest contains a condition `type: has_archetype, name: unknown-class` and no `Archetype` manifest named `unknown-class` is loaded
- **THEN** the loader raises a `LoadError` naming the manifest and the unknown archetype reference

#### Scenario: archetype_add effect referencing unknown archetype is a load error

- **WHEN** a manifest contains an `archetype_add: {name: phantom-guild}` effect and no `Archetype` manifest named `phantom-guild` is loaded
- **THEN** the loader raises a `LoadError`

#### Scenario: All known archetypes pass validation

- **WHEN** all archetype references in conditions and effects match loaded `Archetype` manifest names
- **THEN** no `LoadError` is raised for archetype references

---

### Requirement: Archetypes are exposed in the template surface

The `PlayerContext` used in template rendering SHALL expose `player.archetypes` as the set of held archetype names. This allows templates to display archetype membership, list classes, or branch on archetype state.

#### Scenario: Template can reference player archetypes

- **WHEN** a narrative template contains `{% if 'warrior' in player.archetypes %}You are a Warrior.{% endif %}`
- **THEN** the rendered text includes `"You are a Warrior."` when the character holds the `warrior` archetype and omits it otherwise
