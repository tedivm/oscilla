## 1. Model: CustomEffect manifest and CustomEffectRef

- [x] 1.1 Create `oscilla/engine/models/custom_effect.py` with `CustomEffectParameter`, `CustomEffectSpec`, `CustomEffectManifest` Pydantic models
- [x] 1.2 Add `CustomEffectRef` class to `oscilla/engine/models/adventure.py` (import from `custom_effect.py` with `TYPE_CHECKING` guard)
- [x] 1.3 Add `CustomEffectRef` to the `Effect` discriminated union in `oscilla/engine/models/adventure.py`
- [x] 1.4 Register `CustomEffectManifest` in `oscilla/engine/models/__init__.py` (`MANIFEST_REGISTRY` and `__all__`)

## 2. Registry: custom_effects store

- [x] 2.1 Add `custom_effects: KindRegistry[CustomEffectManifest]` field to `ContentRegistry.__init__` in `oscilla/engine/registry.py`
- [x] 2.2 Add `"CustomEffect"` case arm to `ContentRegistry.build()` to register `CustomEffect` manifests

## 3. Template context: params field

- [x] 3.1 Add `params: Dict[str, int | float | str | bool]` field to `ExpressionContext` in `oscilla/engine/templates.py` (default empty dict)
- [x] 3.2 Add `render_ctx["params"] = ctx.params` in `GameTemplateEngine.render()` in `oscilla/engine/templates.py`
- [x] 3.3 Update `build_mock_context()` to accept optional `params` and populate `ctx["params"]`

## 4. Runtime: CustomEffectRef dispatch in run_effect()

- [x] 4.1 Import `CustomEffectRef` in `oscilla/engine/steps/effects.py`
- [x] 4.2 Add `case CustomEffectRef(...)` arm to `run_effect()` that: looks up manifest, merges defaults with call-site params, injects `params` into `ExpressionContext`, iterates body effects sequentially

## 5. Load-time validation: custom effect cross-reference checks

- [x] 5.1 Implement `_collect_custom_effect_refs_in_effect()` in `oscilla/engine/loader.py` — recursively collects `CustomEffectRef` (name, params) pairs from an effect
- [x] 5.2 Implement `_collect_custom_effect_refs_from_effects()` — iterates a list of effects
- [x] 5.3 Implement `_collect_custom_effect_refs_from_manifest()` — covers all manifest kinds with effect fields (Adventure steps, Item, Skill, Archetype, Buff, CustomEffect)
- [x] 5.4 Implement `_validate_custom_effect_refs()` with three passes: (1) dangling reference check, (2) DFS cycle detection, (3) parameter validation (unknown keys, type mismatch, missing required params)
- [x] 5.5 Call `_validate_custom_effect_refs()` from `validate_references()` in the loader pipeline

## 6. Unit tests — model and validation

- [x] 6.1 Test `CustomEffectParameter`, `CustomEffectSpec`, `CustomEffectManifest` model parsing: valid manifest, duplicate param names, empty effects list
- [x] 6.2 Test `_validate_custom_effect_refs()`: dangling ref error, circular chain error (A → B → A), diamond dependency (no error), unknown param error, type mismatch (bool as int, str as int), missing required param, int accepted as float

## 7. Unit tests — runtime dispatch

- [x] 7.1 Test `run_effect()` with `CustomEffectRef`: basic execution with param override, all-defaults execution, sequential body effects with shared state
- [x] 7.2 Test nested custom effects: params isolation between levels, A → B → C chain
- [x] 7.3 Test `end_adventure` in custom effect body propagates `_EndSignal`

## 8. Integration tests — full loader

- [x] 8.1 Test `load_from_text()` with custom effect in item `use_effects`
- [x] 8.2 Test `load_from_text()` with custom effect in skill `use_effects`
- [x] 8.3 Test `load_from_text()` with custom effect in archetype `gain_effects`
- [x] 8.4 Test `load_from_text()` with template expression referencing `params` in body effect fields
- [x] 8.5 Test `load_from_text()` with nested custom effect composition

## 9. Testlandia content — custom effects

- [x] 9.1 Create `content/testlandia/effects/heal_percentage.yaml` with `percent` parameter (default 25) and `stat_change` body using `params.percent`
- [x] 9.2 Create `content/testlandia/effects/reward_and_milestone.yaml` with `stat`, `amount`, `milestone` params and composed body
- [x] 9.3 Create `content/testlandia/effects/chain_demo.yaml` that calls both `heal_percentage` and `reward_and_milestone`, demonstrating nested composition
- [x] 9.4 Update an existing testlandia healing item to use `type: custom_effect` instead of inline `stat_change`
- [x] 9.5 Update or create a testlandia adventure with a choice step that triggers `chain_demo`, making the feature manually QA-able
- [x] 9.6 Verify testlandia content validates with `oscilla content validate`

## 10. JSON Schema and documentation

- [x] 10.1 Update JSON schema export in `oscilla/engine/schema_export.py` to include `CustomEffect` kind and `CustomEffectRef` in the Effect union
- [x] 10.2 Update `docs/authors/effects.md` with `CustomEffect` manifest format, parameter schema, `type: custom_effect` call site syntax, composition patterns, and load-time errors
- [x] 10.3 Update `docs/authors/README.md` table of contents
