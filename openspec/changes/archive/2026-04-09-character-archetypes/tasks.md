## 1. Remove Class Placeholder System

- [x] 1.1 Delete `oscilla/engine/models/game_class.py` (removes `ClassSpec` and `ClassManifest`); update `oscilla/engine/models/__init__.py` to remove the `game_class` import and the `ClassManifest` entry from `MANIFEST_REGISTRY`
- [x] 1.2 Remove `ClassCondition` from `oscilla/engine/models/base.py`: delete the model definition and remove it from the `Condition` discriminated union
- [x] 1.3 Remove the `case ClassCondition()` branch from `evaluate()` in `oscilla/engine/conditions.py` and remove the `ClassCondition` import
- [x] 1.4 Remove `self.classes: KindRegistry[ClassManifest]` and its population branch from `oscilla/engine/registry.py`; remove the `ClassManifest` import
- [x] 1.5 Remove the `ManifestKind("class", ...)` entry from `oscilla/engine/kinds.py`; remove the `ClassManifest` import
- [x] 1.6 Replace `ClassManifest` with a placeholder import comment in `oscilla/engine/schema_export.py` (`AnyManifest` union update deferred to task 6.4); remove the `ClassManifest` member from `AnyManifest`
- [x] 1.7 Remove the `"Class"` branch from `register_manifests` (or equivalent class-registration path) in `oscilla/engine/loader.py`

## 2. New Archetype Model

- [x] 2.1 Create `oscilla/engine/models/archetype.py` with `ArchetypeSpec` (fields: `displayName: str`, `description: str = ""`, `gain_effects: List[Effect] = []`, `lose_effects: List[Effect] = []`, `passive_effects: List[PassiveEffect] = []`) and `ArchetypeManifest(ManifestEnvelope)` (`kind: Literal["Archetype"]`, `spec: ArchetypeSpec`); use `TYPE_CHECKING` deferred imports for `Effect` and `PassiveEffect` to avoid circular imports, following the existing pattern in `game.py`
- [x] 2.2 Add `ArchetypeManifest` to `MANIFEST_REGISTRY` in `oscilla/engine/models/__init__.py` and add the `archetype` import

## 3. New Condition Predicates

- [x] 3.1 Add `HasArchetypeCondition` to `oscilla/engine/models/base.py` with `type: Literal["has_archetype"]` and `name: str`; add `has_archetype` to `_LEAF_MAPPINGS`
- [x] 3.2 Add `HasAllArchetypesCondition` to `oscilla/engine/models/base.py` with `type: Literal["has_all_archetypes"]` and `names: List[str]`; add `has_all_archetypes` to `_LEAF_MAPPINGS`
- [x] 3.3 Add `HasAnyArchetypeCondition` to `oscilla/engine/models/base.py` with `type: Literal["has_any_archetypes"]` and `names: List[str]`; add `has_any_archetypes` to `_LEAF_MAPPINGS`
- [x] 3.4 Add `ArchetypeCountCondition` to `oscilla/engine/models/base.py` with `type: Literal["archetype_count"]` and `gte: int | None = None`, `lte: int | None = None`, `eq: int | None = None` (same pattern as `PrestigeCountCondition`); add `archetype_count` to `_LEAF_MAPPINGS`
- [x] 3.5 Add `ArchetypeTicksElapsedCondition` to `oscilla/engine/models/base.py` with `type: Literal["archetype_ticks_elapsed"]`, `name: str`, `gte: int | None = None`, `lte: int | None = None`; add a `@model_validator` that raises `ValueError` when both `gte` and `lte` are `None` (same pattern as `MilestoneTicksElapsedCondition`); add `archetype_ticks_elapsed` to `_LEAF_MAPPINGS`
- [x] 3.6 Add all five new condition types to the `Condition` discriminated union in `oscilla/engine/models/base.py`
- [x] 3.7 Add `case HasArchetypeCondition(name=n): return n in player.archetypes` to `evaluate()` in `oscilla/engine/conditions.py`
- [x] 3.8 Add `case HasAllArchetypesCondition(names=ns): return all(n in player.archetypes for n in ns)` to `evaluate()` in `oscilla/engine/conditions.py`
- [x] 3.9 Add `case HasAnyArchetypeCondition(names=ns): return any(n in player.archetypes for n in ns)` to `evaluate()` in `oscilla/engine/conditions.py`
- [x] 3.10 Add `case ArchetypeCountCondition() as c: return _numeric_compare(len(player.archetypes), c)` to `evaluate()` in `oscilla/engine/conditions.py` (reuse the existing `_numeric_compare` helper)
- [x] 3.11 Add `case ArchetypeTicksElapsedCondition() as c` to `evaluate()` in `oscilla/engine/conditions.py`: look up `record = player.archetypes.get(c.name)`; return `False` if `None`; compute `elapsed = player.internal_ticks - record.tick`; return `False` if `c.gte is not None and elapsed < c.gte`; return `False` if `c.lte is not None and elapsed > c.lte`; return `True`

## 4. New Effect Types

- [x] 4.1 Add `ArchetypeAddEffect` to `oscilla/engine/models/adventure.py` with `type: Literal["archetype_add"]`, `name: str`, and `force: bool = False`; add it to the `Effect` union
- [x] 4.2 Add `ArchetypeRemoveEffect` to `oscilla/engine/models/adventure.py` with `type: Literal["archetype_remove"]`, `name: str`, and `force: bool = False`; add it to the `Effect` union
- [x] 4.3 Add `SkillRevokeEffect` to `oscilla/engine/models/adventure.py` with `type: Literal["skill_revoke"]` and `skill: str`; add it to the `Effect` union
- [x] 4.4 Add `case ArchetypeAddEffect` to `oscilla/engine/steps/effects.py`: if archetype not held (or `force=True`), look up manifest in registry, dispatch `gain_effects` recursively, then set `player.archetypes[name] = GrantRecord(tick=player.internal_ticks, timestamp=int(time.time()))`
- [x] 4.5 Add `case ArchetypeRemoveEffect` to `oscilla/engine/steps/effects.py`: if archetype is held (or `force=True`), look up manifest in registry, dispatch `lose_effects` recursively, then call `player.archetypes.pop(name, None)`
- [x] 4.6 Add `case SkillRevokeEffect` to `oscilla/engine/steps/effects.py`: call `player.known_skills.discard(effect.skill)` (no-op when not present)

## 5. CharacterState Changes

- [x] 5.0 Rename `MilestoneRecord` → `GrantRecord` in `oscilla/engine/models/base.py`; update all references in `oscilla/engine/character.py`, `tests/engine/test_character.py`, and `docs/dev/game-engine.md`
- [x] 5.1 Add `archetypes: Dict[str, GrantRecord] = field(default_factory=dict)` to `CharacterState` in `oscilla/engine/character.py`; import `GrantRecord` from `oscilla.engine.models.base`
- [x] 5.2 Update `CharacterState.to_dict()` to include `"archetypes": {name: {"tick": r.tick, "timestamp": r.timestamp} for name, r in self.archetypes.items()}`
- [x] 5.3 Update `CharacterState.from_dict()` to deserialize archetypes using the same two-format migration as milestones: legacy list (`["warrior"]`) → `GrantRecord(tick=0, timestamp=0)` per entry; nested-dict (`{"warrior": {"tick": N, "timestamp": N}}`) → `GrantRecord` directly; silently drop any name absent from `registry.archetypes` when registry is provided (content-drift resilience)
- [x] 5.4 Update `effective_stats()` in `oscilla/engine/character.py`: after the global `passive_effects` loop, add a loop over `self.archetypes` — look up each `ArchetypeManifest` in registry, evaluate each `passive_effect.condition` (implicit gate is `has_archetype`), apply `stat_modifiers`
- [x] 5.5 Update `available_skills()` in `oscilla/engine/character.py`: same looping pattern as 5.4 but yield `skill_grants` from each satisfied passive effect

## 6. Registry and Manifest System

- [x] 6.1 Add `self.archetypes: KindRegistry[ArchetypeManifest]` to `ContentRegistry` in `oscilla/engine/registry.py` and add the `ArchetypeManifest` registration branch
- [x] 6.2 Add `ManifestKind("archetype", "archetypes", "archetypes", "Archetype", ArchetypeManifest, creatable=True)` to `ALL_KINDS` in `oscilla/engine/kinds.py`; add the `ArchetypeManifest` import
- [x] 6.3 Add `ArchetypeManifest` to the `MANIFEST_REGISTRY` dict in `oscilla/engine/models/__init__.py` (if not already done in 2.2)
- [x] 6.4 Replace `ClassManifest` with `ArchetypeManifest` in the `AnyManifest` union in `oscilla/engine/schema_export.py`

## 7. Loader Validation

- [x] 7.1 Implement `_collect_archetype_refs_in_condition(condition: Condition) -> Set[str]` in `oscilla/engine/loader.py`: recursive tree walker collecting archetype name strings from `HasArchetypeCondition`, `HasAllArchetypesCondition`, `HasAnyArchetypeCondition`, and `ArchetypeTicksElapsedCondition` leaves; recurse into `AllCondition`, `AnyCondition`, `NotCondition`
- [x] 7.2 Implement `_collect_archetype_refs_in_effects(effects: List[Effect]) -> Set[str]` in `oscilla/engine/loader.py`: collects `name` from `ArchetypeAddEffect` and `ArchetypeRemoveEffect` instances
- [x] 7.3 Implement `_collect_archetype_refs_from_manifest(manifest: AnyManifest) -> Set[str]` in `oscilla/engine/loader.py`: covers all condition and effect sites — adventure step conditions and effects, region/location unlock conditions, skill `use_effects`, item `use_effects` and equip `requires`, archetype `gain_effects`/`lose_effects`/`passive_effects[*].condition`, and game `passive_effects[*].condition`
- [x] 7.4 Implement `_validate_archetype_refs(manifests: List[AnyManifest]) -> List[LoadError]` in `oscilla/engine/loader.py`: build `archetype_names = {m.metadata.name for m in manifests if m.kind == "Archetype"}`, collect refs from all manifests via 7.3, emit `LoadError` for each ref not in `archetype_names`
- [x] 7.5 Call `_validate_archetype_refs()` from the main `load()` function alongside existing validation calls; raise or accumulate `LoadError` results consistently with the existing error-handling pattern

## 8. Tests

- [x] 8.1 Add tests for `ArchetypeSpec` and `ArchetypeManifest` model construction: verify all fields parse from dict, `gain_effects`/`lose_effects`/`passive_effects` default to empty lists, `displayName` is required
- [x] 8.2 Add tests for `CharacterState.archetypes` serialization: `archetype_add` records the correct `internal_ticks` and a positive `timestamp` in a `GrantRecord`; `to_dict()` emits a nested dict `{name: {"tick": N, "timestamp": N}}`; `from_dict()` round-trips correctly; legacy list format migrates to `GrantRecord(tick=0, timestamp=0)`; `from_dict()` with an unknown archetype name silently drops it when a registry is provided; `from_dict()` without a registry accepts all names
- [x] 8.3 Add tests for `has_archetype` condition: returns `True` when archetype is in `player.archetypes`; `False` when absent
- [x] 8.4 Add tests for `has_all_archetypes` condition: `True` only when all listed names are held; `False` when any is missing
- [x] 8.5 Add tests for `has_any_archetypes` condition: `True` when at least one name is held; `False` when none are held
- [x] 8.6 Add tests for `archetype_count` condition: `gte`, `lte`, and `eq` comparisons against `len(player.archetypes)` using constructed `CharacterState` and no registry
- [x] 8.6b Add tests for `archetype_ticks_elapsed` condition: returns false when archetype not held; `gte` passes and fails correctly; `lte` passes and fails correctly; combined `gte`+`lte` window passes inside and fails outside; Pydantic validation error raised when neither comparator is provided
- [x] 8.7 Add tests for `archetype_add` effect: adds archetype to `player.archetypes` and dispatches `gain_effects`; second application is a no-op without `force`; `force=True` re-dispatches `gain_effects` even when already held
- [x] 8.8 Add tests for `archetype_remove` effect: removes archetype and dispatches `lose_effects`; removing an absent archetype is a no-op without `force`; `force=True` re-dispatches `lose_effects` even when not held
- [x] 8.9 Add tests for `skill_revoke` effect: removes a held skill from `known_skills`; no-op (no error) when the skill is not present
- [x] 8.10 Add tests for archetype passive effects in `effective_stats()`: stat modifiers from a held archetype's `passive_effects` are applied; passive effects from an archetype not held are not applied; conditional passive effects within an archetype fire only when the inner condition is met
- [x] 8.11 Add tests for archetype passive effects in `available_skills()`: `skill_grants` from held archetype passive effects are included; grants from unheld archetypes are excluded
- [x] 8.12 Add tests for load-time archetype ref validation: a `has_archetype` pointing to an undeclared archetype raises `LoadError`; `archetype_add` pointing to an undeclared name raises `LoadError`; all four condition types and both effect types each trigger the error appropriately; valid refs produce no error
- [x] 8.13 Add tests confirming `ClassCondition`, `ClassManifest`, and `ClassSpec` are fully absent from all imports and the condition evaluator (import-time checks; ensures the removal did not leave dead code)

## 9. Documentation

- [x] 9.1 Create `docs/authors/archetypes.md`: cover what an archetype is and its role as a primitive; the `ArchetypeManifest` YAML structure with annotated examples; `gain_effects` and `lose_effects` lifecycle; `passive_effects` as continuous stat and skill grants; `archetype_add`/`archetype_remove` effect syntax including the `force` flag; `skill_revoke` effect; all four condition predicates with YAML examples; cross-reference to conditions.md, effects.md, and skills.md
- [x] 9.2 Add `archetypes.md` to the table of contents in `docs/authors/README.md`
- [x] 9.3 Update `docs/dev/game-engine.md`: add an Archetype section describing the manifest kind, `CharacterState.archetypes`, passive effects evaluation order (global → archetype), and the load-time validation pattern; note removal of the Class placeholder
- [x] 9.4 Update `docs/authors/conditions.md`: add entries for `has_archetype`, `has_all_archetypes`, `has_any_archetypes`, `archetype_count`, and `archetype_ticks_elapsed`
- [x] 9.5 Update `docs/authors/effects.md` (or equivalent effects reference): add entries for `archetype_add`, `archetype_remove`, and `skill_revoke`

## 10. Testlandia Content

- [x] 10.1 Create at least two archetype manifests in `content/testlandia/archetypes/` (e.g., `test-warrior.yaml` and `test-mage.yaml`) with non-trivial `gain_effects`, `lose_effects`, and `passive_effects` exercising stat modifiers and skill grants
- [x] 10.2 Add a testlandia adventure that uses `archetype_add` and `archetype_remove`; include one step that uses `force: true` to demonstrate re-trigger behavior
- [x] 10.3 Add a testlandia adventure step that uses `skill_revoke` in a `lose_effects` context, confirming the skill disappears from the character on archetype removal
- [x] 10.4 Add adventure steps or conditions that exercise all four archetype condition predicates (`has_archetype`, `has_all_archetypes`, `has_any_archetypes`, `archetype_count`) so they can be manually verified in the TUI
- [x] 10.5 Run `oscilla content test testlandia` to confirm the testlandia package validates cleanly with the new archetype manifests
