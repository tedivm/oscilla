# Tasks

## 1. Models — new `CustomConditionRef` and manifest models

- [x] 1.1 Create `oscilla/engine/models/custom_condition.py` with `CustomConditionSpec` (fields: `display_name: str | None = None`, `condition: "Condition"`) and `CustomConditionManifest` (extends `ManifestEnvelope`, `kind: Literal["CustomCondition"]`, `spec: CustomConditionSpec`). Use `TYPE_CHECKING` guard for the `Condition` import to avoid a circular import.
- [x] 1.2 Add `CustomConditionRef` to `oscilla/engine/models/base.py` as a new leaf model with `type: Literal["custom"]` and `name: str`. Place it just before the `Condition` union definition.
- [x] 1.3 Append `CustomConditionRef` to the `Condition` union member list in `base.py` (last entry before the closing bracket, after `TimeBetweenCondition`).
- [x] 1.4 Add `from oscilla.engine.models.custom_condition import CustomConditionManifest` import to `oscilla/engine/models/__init__.py`.
- [x] 1.5 Add `"CustomCondition": CustomConditionManifest` to `MANIFEST_REGISTRY` in `oscilla/engine/models/__init__.py`.
- [x] 1.6 Add `"CustomConditionManifest"` to `__all__` in `oscilla/engine/models/__init__.py`.

## 2. Registry — `custom_conditions` field and `build()` arm

- [x] 2.1 Add `from oscilla.engine.models.custom_condition import CustomConditionManifest` to the imports in `oscilla/engine/registry.py`.
- [x] 2.2 Add `self.custom_conditions: KindRegistry[CustomConditionManifest] = KindRegistry()` to `ContentRegistry.__init__()` alongside the other `KindRegistry` fields.
- [x] 2.3 Add a `case "CustomCondition":` arm to the `build()` match block: `registry.custom_conditions.register(cast(CustomConditionManifest, m))`.

## 3. Condition evaluator — `CustomConditionRef` case arm

- [x] 3.1 Add `CustomConditionRef` to the import block from `oscilla.engine.models.base` in `oscilla/engine/conditions.py`.
- [x] 3.2 Add the `case CustomConditionRef(name=n):` arm to `evaluate()` in `conditions.py`. The arm must: (a) return `False` + log warning if `registry is None`; (b) look up `registry.custom_conditions.get(n)` and return `False` + log warning if not found; (c) otherwise return `evaluate(defn.spec.condition, player, registry, exclude_item)`. Insert the arm before the wildcard `case _:` arm.

## 4. Passive effects fix — `character.py` call sites

- [x] 4.1 In `effective_stats()` in `oscilla/engine/character.py`, change `registry=None` to `registry=registry` in the `evaluate()` call inside the game passive effects loop.
- [x] 4.2 In `effective_stats()`, change `registry=None` to `registry=registry` in the `evaluate()` call inside the archetype passive effects loop.
- [x] 4.3 In `available_skills()` in `oscilla/engine/character.py`, change `registry=None` to `registry=registry` in the `evaluate()` call inside the game passive effects loop.
- [x] 4.4 In `available_skills()`, change `registry=None` to `registry=registry` in the `evaluate()` call inside the archetype passive effects loop.

## 5. Loader — custom condition validation helpers

- [x] 5.1 Add `_collect_custom_condition_refs_in_condition(condition: Condition) -> Set[str]` to `oscilla/engine/loader.py`. Recursively walks `AllCondition`, `AnyCondition`, `NotCondition`, and `CustomConditionRef` nodes; returns the set of all `CustomConditionRef.name` strings found.
- [x] 5.2 Add `_collect_custom_condition_refs_from_manifest(m: ManifestEnvelope) -> Set[str]` to `loader.py`. Match on `m.kind` and call `_collect_custom_condition_refs_in_condition()` on every condition-bearing field for: `CustomCondition`, `Location`, `Region`, `Adventure` (requires, option requires, bypass, stat-check condition), `Item` (equip.requires), `Skill` (requires), `Game` (passive effect conditions).
- [x] 5.3 Add `_validate_custom_condition_refs(manifests: List[ManifestEnvelope]) -> List[LoadError]` to `loader.py`. Pass 1: for each manifest, call `_collect_custom_condition_refs_from_manifest()` and emit a `LoadError` for every name not in `known_names` (the set of declared `CustomCondition` manifest names). Pass 2: build a `CustomCondition`-only adjacency dict (edges restricted to `known_names`) and run iterative DFS cycle detection; emit a `LoadError` with the full cycle path string (`"a → b → a"`) for each back-edge found.
- [x] 5.4 Wire `errors.extend(_validate_custom_condition_refs(manifests))` into `validate_references()` after `_validate_loot_condition_refs`.

## 6. Loader — passive effect condition validation

- [x] 6.1 Add `_validate_passive_effect_conditions(manifests: List[ManifestEnvelope]) -> List[LoadError]` to `loader.py`. Extracts the `Game` manifest, builds a `custom_condition_bodies` name→condition dict, then for each passive effect calls a nested `_contains_banned_type(condition, seen_custom)` helper that returns a description string if `CharacterStatCondition(stat_source="effective")` or `SkillCondition` is found (directly or transitively through `CustomConditionRef` chains). Emits one `LoadError` per matching passive effect.
- [x] 6.2 Wire `errors.extend(_validate_passive_effect_conditions(manifests))` into `validate_references()` after `_validate_custom_condition_refs`.
- [x] 6.3 Update `_validate_passive_effects()` in `loader.py`: remove the `ItemHeldLabelCondition`, `AnyItemEquippedCondition`, and `CharacterStatCondition(stat_source="effective")` warning branches entirely. The function body becomes a stub that returns `[]` (or retains unrelated warnings if any exist). Keep the function signature and docstring.

## 7. Testlandia — new `CustomCondition` manifests

- [x] 7.1 Create `content/testlandia/conditions/` directory (the `conditions/` subdirectory is new).
- [x] 7.2 Create `content/testlandia/conditions/test-high-level.yaml` — a `CustomCondition` named `test-high-level` whose body is `CharacterStatCondition(stat="level", gte=10)`. Set `displayName: "High Level (10+)"`.
- [x] 7.3 Create `content/testlandia/conditions/test-high-level-warrior.yaml` — a `CustomCondition` named `test-high-level-warrior` whose body is an `AllCondition` combining `CustomConditionRef(name="test-high-level")` and `HasArchetypeCondition(name="warrior")`. Set `displayName: "High Level Warrior"`.
- [x] 7.4 Add a `requires` block to an existing testlandia adventure (the Grant Title adventure is the preferred target) using `type: custom` with `name: test-high-level`, so the gate is observable during a manual QA play-through at level < 10 and level ≥ 10.

## 8. Tests — unit tests for the condition evaluator

- [x] 8.1 Create `tests/engine/test_custom_conditions.py`. Add a `make_character_state(level=1, **kwargs)` factory helper that constructs a minimal `CharacterState` with configurable stat values.
- [x] 8.2 Add `test_evaluate_custom_condition_resolves_body()` — builds a `ContentRegistry` in Python with one `CustomConditionManifest` whose body is `LevelCondition(value=5)`, asserts `evaluate(CustomConditionRef(...), low_player, registry)` is `False` and `evaluate(..., high_player, registry)` is `True`.
- [x] 8.3 Add `test_evaluate_custom_condition_missing_registry_returns_false()` — calls `evaluate(CustomConditionRef(...), player, registry=None)` and asserts `False`.
- [x] 8.4 Add `test_evaluate_custom_condition_unknown_name_returns_false()` — calls `evaluate(CustomConditionRef(name="no-such")`, player, empty registry)`and asserts`False`.
- [x] 8.5 Add `test_evaluate_custom_condition_composition()` — builds a registry with `"inner"` (level gate) and `"outer"` (references `"inner"`) and asserts transitive resolution works correctly.

## 9. Tests — unit tests for `_validate_custom_condition_refs()`

- [x] 9.1 Add `test_validate_dangling_ref_produces_error()` — builds a minimal `AdventureManifest` (or similar) whose condition field is `CustomConditionRef(name="missing")` with no matching `CustomCondition` manifest; asserts one `LoadError` with message containing `"missing"` and `"unknown CustomCondition"`.
- [x] 9.2 Add `test_validate_direct_circular_ref_produces_error()` — builds `CustomCondition "self-ref"` whose body is `CustomConditionRef(name="self-ref")`; asserts a `LoadError` with message containing `"circular reference"`.
- [x] 9.3 Add `test_validate_indirect_cycle_produces_error()` — builds `"a"` → `"b"` → `"a"`; asserts a `LoadError` whose message contains the full cycle path.
- [x] 9.4 Add `test_validate_valid_composition_produces_no_errors()` — builds `"a"` → `"b"` (no cycle, both declared); asserts no errors.

## 10. Tests — unit tests for `_validate_passive_effect_conditions()`

- [x] 10.1 Add `test_passive_effect_stat_source_effective_raises_error()` — builds a `GameManifest` with a passive effect using `CharacterStatCondition(stat_source="effective")`; asserts a `LoadError` mentioning `"passive_effects[0]"` and `"character_stat"`.
- [x] 10.2 Add `test_passive_effect_skill_condition_raises_error()` — same pattern with `SkillCondition`; asserts error mentioning `"skill"`.
- [x] 10.3 Add `test_passive_effect_stat_source_base_no_error()` — `CharacterStatCondition(stat_source="base")` in passive effect; asserts no errors.
- [x] 10.4 Add `test_passive_effect_custom_ref_with_banned_body_raises_error()` — builds `CustomCondition "has-skill"` wrapping `SkillCondition`, passive effect uses `CustomConditionRef(name="has-skill")`; asserts error on the passive effect.
- [x] 10.5 Add `test_passive_effect_custom_ref_with_safe_body_no_error()` — builds `CustomCondition "gate"` wrapping `LevelCondition`, passive effect uses `CustomConditionRef(name="gate")`; asserts no errors.
- [x] 10.6 Add `test_validate_passive_effects_no_longer_warns_item_held_label()` — builds a `GameManifest` with a passive effect using `ItemHeldLabelCondition`; asserts `_validate_passive_effects()` returns `[]`.

## 11. Tests — loader integration fixtures and tests

- [x] 11.1 Create `tests/fixtures/content/custom-conditions-cycle/` with a minimal `game.yaml`, `character_config.yaml`, and two `CustomCondition` manifests forming a cycle (`a` → `b` → `a`).
- [x] 11.2 Create `tests/fixtures/content/custom-conditions-dangling/` with a minimal `game.yaml`, `character_config.yaml`, and one `Adventure` manifest whose `requires` references a non-existent `CustomCondition`.
- [x] 11.3 Add `test_loader_rejects_circular_custom_condition()` to `tests/engine/test_custom_conditions.py` — calls `load_content(Path("tests/fixtures/content/custom-conditions-cycle/"))` and asserts `ContentLoadError` with message matching `"circular reference"`.
- [x] 11.4 Add `test_loader_rejects_dangling_custom_condition_ref()` — calls `load_content(Path("tests/fixtures/content/custom-conditions-dangling/"))` and asserts `ContentLoadError` with message matching `"unknown CustomCondition"`.

## 12. Documentation

- [x] 12.1 Add a **Custom Conditions** section to `docs/authors/conditions.md` covering: manifest format (`kind: CustomCondition`, `spec.condition`, optional `displayName`), `type: custom` usage example, composition example (A references B), validation error messages for dangling refs and cycles, and the recommended `conditions/` subdirectory convention.
- [x] 12.2 Add `custom` to the **Leaf Conditions** list in `docs/dev/game-engine.md` with description: _"References a named `CustomCondition` manifest; resolved at evaluation time via the registry."_ Add a **Custom Conditions** paragraph after the Logical Operators subsection describing the implementation hook points.
- [x] 12.3 Add `custom` to the condition categories table in `docs/system-overview.md` as a new **Reuse** row. Add a one-sentence note after the table pointing to `docs/authors/conditions.md#custom-conditions`.
- [x] 12.4 Update `docs/authors/passive-effects.md`: remove `item_held_label` and `any_item_equipped` from the restricted list; change `character_stat (stat_source: effective)` and `skill` entries to hard-error descriptions; add `type: custom` to the supported section with the note about transitive body checking.
- [x] 12.5 Append `custom-conditions` to the hardcoded kind slug list on line 46 of `docs/authors/cli.md`.
- [x] 12.6 Append `"and reusable named conditions (\`type: custom\`)"`to the Conditions row in the **Authoring Model** table in`docs/authors/README.md`.
