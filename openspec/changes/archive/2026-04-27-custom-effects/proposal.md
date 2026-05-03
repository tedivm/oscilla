## Why

Content packages frequently repeat the same effect sequences across multiple manifests. A "heal to 50%" pattern might appear in five different items, three skills, and two archetypes — each with the same template expression, the same `stat_change` effect, and the same boilerplate. When the healing logic changes, every copy must be found and updated. Custom Conditions solved this problem for condition trees; effects need the same macro layer.

There is no mechanism for an author to name a sequence of effects once, parameterize it, and reference it by name from any manifest that accepts effects.

## What Changes

### Engine: Custom Effects

- **New manifest kind `CustomEffect`** — authors declare a named, reusable effect body in a `kind: CustomEffect` manifest. The manifest name is the reference key used at all call sites. A parameter schema declares typed parameters with optional defaults (`int`, `float`, `str`, `bool`).
- **New effect leaf `type: custom`** — any manifest field that accepts an `Effect` can now specify `type: custom` with a `name:` field pointing to a declared `CustomEffect`. A `params:` dict supplies per-call parameter overrides that merge with the manifest's defaults.
- **Parameter resolution in templates** — body effects with template-string fields (e.g., `amount: "{{ params.percent / 100 * player.stats['max_hp'] }}"`) resolve `params` from the merged parameter dict. The `params` variable is injected into the `ExpressionContext` for the duration of body effect execution.
- **Custom effects can compose custom effects** — a `CustomEffect` body may contain `type: custom` effects that reference other `CustomEffect` manifests, with their own `params:` dicts. Parameter resolution is scoped per-call-site.
- **Load-time validation** — `validate_references()` gains a new `_validate_custom_effect_refs()` sub-validator that checks (1) all `type: custom` effect references point to a declared `CustomEffect` manifest, (2) no `CustomEffect` body forms a circular reference chain, (3) all parameter names in call-site `params:` dicts are declared in the target `CustomEffect`'s parameter schema, and (4) parameter types match (e.g., passing an `int` where a `str` is declared). Dangling references, cycles, and type mismatches all raise `ContentLoadError`.
- **`ContentRegistry`** — gains a `custom_effects: KindRegistry[CustomEffectManifest]` field populated during `build()`.

### Testlandia

A new `effects/` directory is added to the testlandia content package with `CustomEffect` manifests demonstrating: a parameterized heal effect (`heal_percentage`), a composed effect that calls another custom effect (`reward_and_milestone`), and a chained composition chain (A → B → C). Testlandia items and skills are updated to use `type: custom` instead of inline effects, making the feature immediately QA-able.

## Capabilities

### New Capabilities

- `custom-effects`: The `CustomEffect` manifest kind, `type: custom` effect leaf, parameter schema with type checking, `params` template context injection, composition support, and full load-time validation (dangling refs, cycles, unknown params, type mismatches).

### Modified Capabilities

- **`custom-condition-validation`**: The existing `_validate_custom_condition_refs()` pattern in `loader.py` is extended with a parallel `_validate_custom_effect_refs()` function. Same validation philosophy (dangling ref check, DFS cycle detection) applied to the effect domain.

## Impact

- **`oscilla/engine/models/custom_effect.py`** — new file: `CustomEffectParameter`, `CustomEffectSpec`, `CustomEffectManifest` Pydantic models.
- **`oscilla/engine/models/base.py`** — add `CustomEffectRef` class to the `Effect` union.
- **`oscilla/engine/models/__init__.py`** — import `CustomEffectManifest`; add `"CustomEffect"` to `MANIFEST_REGISTRY`.
- **`oscilla/engine/registry.py`** — add `custom_effects: KindRegistry[CustomEffectManifest]` field to `ContentRegistry.__init__`; add `"CustomEffect"` arm to `ContentRegistry.build()`.
- **`oscilla/engine/steps/effects.py`** — import `CustomEffectRef`; add `case CustomEffectRef(...)` arm to `run_effect()` that resolves params, injects into `ExpressionContext`, and iterates body effects.
- **`oscilla/engine/templates.py`** — `ExpressionContext` gains `params: Dict[str, int | float | str | bool]` field (default empty dict).
- **`oscilla/engine/loader.py`** — add `_collect_custom_effect_refs_in_effects()`, `_collect_custom_effect_refs_from_manifest()`, and `_validate_custom_effect_refs()` helpers; call the validator from `validate_references()`.
- **`oscilla/engine/schema_export.py`** — JSON schema post-processing for `CustomEffect` manifest kind.
- **`tests/engine/test_custom_effects.py`** — new test file covering: model parsing, valid resolution, param override merge, template resolution with params, dangling-ref error, circular-ref error, unknown-param error, type-mismatch error, nested composition.
- **`content/testlandia/effects/`** — new directory with testlandia `CustomEffect` manifests; existing testlandia items/skills updated to use `type: custom`.
- **`docs/authors/effects.md`** — updated to document `CustomEffect` manifest format, `type: custom` usage, parameter schema, and composition patterns.
