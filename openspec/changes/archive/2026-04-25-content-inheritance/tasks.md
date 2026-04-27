## 1. Metadata and BaseSpec model changes

- [x] 1.1 Add `abstract` and `base` fields to `Metadata` in `oscilla/engine/models/base.py`
- [x] 1.2 Create `BaseSpec(BaseModel)` class with `properties` field in `oscilla/engine/models/base.py`
- [x] 1.3 Change all spec classes to inherit from `BaseSpec` instead of `BaseModel` (enemy, item, adventure, archetype, buff, skill, location, region, quest, recipe, loot_table, game, character_config, combat_system, custom_condition)
- [x] 1.4 Update `oscilla/engine/models/__init__.py` to export `BaseSpec`

## 2. Template context changes — `this` variable

- [x] 2.1 Add `this` field to `CombatFormulaContext` in `oscilla/engine/templates.py`
- [x] 2.2 Add `this` field to `ExpressionContext` in `oscilla/engine/templates.py`
- [x] 2.3 Expose `this` in `render_formula()` Jinja2 render context
- [x] 2.4 Expose `this` in `GameTemplateEngine.render()` Jinja2 render context
- [x] 2.5 Add `manifest_properties` parameter to `build_mock_context()` and populate `ctx["this"]`
- [x] 2.6 Update all callers of `build_mock_context()` to pass `manifest_properties` where applicable (template validation in loader.py)

## 3. Loader inheritance pre-pass

- [x] 3.1 Add `_RawManifest` dataclass to `oscilla/engine/loader.py`
- [x] 3.2 Implement `_merge_spec_dicts()` with recursive `+` support
- [x] 3.3 Implement `_topo_sort_inheritance()` with cycle detection and kind-mismatch errors
- [x] 3.4 Implement `_resolve_inheritance()` with abstract routing and unused-abstract warnings
- [x] 3.5 Refactor `_parse_text()` to categorize manifests (immediate / deferred / abstract) and return 4-tuple
- [x] 3.6 Update `parse()` to call `_resolve_inheritance()` and return 3-tuple (manifests, errors, warnings)
- [x] 3.7 Update `load_from_text()` to stitch-and-resolve with warning threading
- [x] 3.8 Update `load_from_disk()` to thread parse warnings through to pipeline warnings

## 4. JSON Schema post-processing

- [x] 4.1 Add abstract permissive arm to `export_union_schema()` in `oscilla/engine/schema_export.py`
- [x] 4.2 Implement `+` field injection for all list and dict properties in generated schemas

## 5. Unit tests — merge and loader logic

- [x] 5.1 Test `_merge_spec_dicts()`: replace semantics, `+` list extend, `+` dict recursive merge, `+` type mismatch, `+` with no base value, `properties+:` extend
- [x] 5.2 Test `_topo_sort_inheritance()`: correct ordering, circular chain error, missing base ref error, kind mismatch error
- [x] 5.3 Test `_resolve_inheritance()`: abstract child of abstract base, abstract not registered, unused abstract warning
- [x] 5.4 Test `load_from_text()`: single-level inheritance, chained inheritance (depth 3), abstract base with concrete child, concrete base with child

## 6. Unit tests — template context

- [x] 6.1 Test `this` in `render_formula()` with `CombatFormulaContext`
- [x] 6.2 Test `this` in `GameTemplateEngine.render()` with `ExpressionContext`
- [x] 6.3 Test `build_mock_context()` with `manifest_properties` populates `this`
- [x] 6.4 Test load-time template validation with `this` in adventure step templates

## 7. Integration tests — full pipeline

- [x] 7.1 Test full `load_from_disk()` with inherited manifests (using temp directory with YAML files)
- [x] 7.2 Test `parse()` return type change doesn't break existing callers
- [x] 7.3 Test `load_from_text()` multi-document YAML with inheritance (doc-level error labeling)
- [x] 7.4 Test JSON Schema export includes `+` fields and abstract arm

## 8. Testlandia content — goblin enemy family

- [x] 8.1 Create `content/testlandia/enemies/goblins.yaml` with goblin-base (abstract), goblin-scout, goblin-chief, goblin-king
- [x] 8.2 Verify testlandia content validates with `oscilla content validate`

## 9. Testlandia content — sword item family

- [x] 9.1 Create `content/testlandia/items/weapons/swords.yaml` with sword-base (abstract), iron-sword, steel-sword, silver-sword
- [x] 9.2 Ensure `basic-slash` and `silver-strike` skills exist in testlandia (create if needed)
- [x] 9.3 Verify testlandia content validates with `oscilla content validate`

## 10. Testlandia content — QA adventure

- [x] 10.1 Create or update a testlandia adventure that grants iron-sword, encounters goblin variants, and offers sword upgrades
- [x] 10.2 Verify adventure is playable in both TUI and web

## 11. Documentation

- [x] 11.1 Create `docs/authors/manifest-inheritance.md` with full author guide
- [x] 11.2 Update `docs/authors/README.md` table of contents
