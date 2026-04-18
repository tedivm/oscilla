## Why

Content packages frequently need the same condition cluster in multiple places. A Halloween event window might gate dozens of adventures, locations, and passive effects. An archetype-plus-milestone prerequisite might appear across an entire quest chain. Today, every one of those sites must repeat the full YAML block verbatim — a maintenance hazard and an authoring friction point.

There is no mechanism for an author to name a condition once and reference it by name everywhere it is needed. This is a gap in the authoring surface that grows more costly as content packages grow.

## What Changes

### Engine

- **New manifest kind `CustomCondition`** — authors declare a named, reusable condition body in a `kind: CustomCondition` manifest. The manifest name is the reference key used at all call sites.
- **New condition leaf `type: custom`** — any manifest field that accepts a `Condition` can now specify `type: custom` with a `name:` field pointing to a declared `CustomCondition`. The evaluator resolves the name at evaluation time against the registry.
- **Load-time validation** — `validate_references()` gains a new `_validate_custom_condition_refs()` sub-validator that checks (1) all `type: custom` references point to a declared `CustomCondition` manifest, and (2) no `CustomCondition` body forms a circular reference chain. Dangling references and cycles both raise `ContentLoadError`.
- **`ContentRegistry`** — gains a `custom_conditions: KindRegistry[CustomConditionManifest]` field populated during `build()`.
- **Passive effect condition support expanded** — `character.py` is updated to pass `registry` through to passive condition evaluation (previously `registry=None` was used as a blanket recursion guard). The two genuinely re-entrant types (`character_stat` with `stat_source: effective` and `skill`) are promoted from `LoadWarning` to hard `LoadError` in the passive effect validator, eliminating the recursion risk entirely. Previously broken types — `item_held_label`, `any_item_equipped`, all `game_calendar_*` conditions, and `type: custom` (with a safe body) — become fully functional in passive effects as a result.

### Testlandia

A `conditions/` directory is added to the testlandia content package with at least two `CustomCondition` manifests demonstrating: a standalone reusable condition, and a composed condition that references the first. An adventure in testlandia uses `type: custom` to gate a step, making the feature immediately QA-able.

## Capabilities

### New Capabilities

- `custom-conditions`: The `CustomCondition` manifest kind and `type: custom` condition leaf that enable named, reusable, composable condition definitions within a content package.

### Modified Capabilities

- **`passive-effects`**: The set of condition types permitted in passive effect guards is expanded. Previously, `item_held_label`, `any_item_equipped`, and all `game_calendar_*` types silently evaluated `False` in passive context. They now work correctly. The two conditions that caused re-entrant evaluation (`character_stat` with `stat_source: effective`, `skill`) become hard load-time errors rather than warnings.

## Impact

- **`oscilla/engine/models/custom_condition.py`** — new file: `CustomConditionSpec` and `CustomConditionManifest` Pydantic models.
- **`oscilla/engine/models/base.py`** — add `CustomConditionRef` class to the `Condition` union.
- **`oscilla/engine/models/__init__.py`** — import `CustomConditionManifest`; add `"CustomCondition"` to `MANIFEST_REGISTRY`.
- **`oscilla/engine/registry.py`** — add `custom_conditions: KindRegistry[CustomConditionManifest]` field to `ContentRegistry.__init__`; add `"CustomCondition"` arm to `ContentRegistry.build()`.
- **`oscilla/engine/conditions.py`** — import `CustomConditionRef`; add `case CustomConditionRef(name=n):` arm to `evaluate()`.
- **`oscilla/engine/character.py`** — four call sites in `effective_stats()` and `available_skills()` changed from `registry=None` to `registry=registry` when evaluating passive effect conditions.
- **`oscilla/engine/loader.py`** — add `_collect_custom_condition_refs_in_condition()`, `_collect_custom_condition_refs_from_manifest()`, and `_validate_custom_condition_refs()` helpers; call the validator from `validate_references()`. Update `_validate_passive_effects()`: remove now-unnecessary `LoadWarning`s for `item_held_label` and `any_item_equipped`; promote `character_stat(stat_source=effective)` and `skill` from `LoadWarning` to `LoadError` via a new `_validate_passive_effect_conditions()` helper called from `validate_references()`.
- **`tests/engine/test_custom_conditions.py`** — new test file covering: model parsing, valid resolution, dangling-ref error, circular-ref error, composed conditions.
- **`content/testlandia/conditions/`** — new directory with testlandia `CustomCondition` manifests; an existing testlandia adventure updated to use `type: custom`.
- **`docs/authors/conditions.md`** — updated to document `CustomCondition` manifest format, `type: custom` usage, and composition patterns.
