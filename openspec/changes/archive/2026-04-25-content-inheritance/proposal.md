## Why

Content packages with related manifests — enemy variant families, weapon tiers, location clusters — repeat the same YAML blocks verbatim across every member. When shared data changes, every copy must be found and updated individually. There is no mechanism to declare a base manifest once and have variants inherit from it, which makes large content packages fragile and repetitive.

## What Changes

### Engine: Manifest Inheritance

- **`metadata.base`** — any manifest may declare `metadata.base: <name>` to inherit all unspecified `spec` fields from another manifest of the same `kind`. The child's own fields replace the base's fields; list and dict fields may optionally extend rather than replace using a `+` suffix on the field name (e.g., `grants_skills_equipped+:`).
- **`metadata.abstract: true`** — marks a manifest as a template-only base. Abstract manifests are never registered in the `ContentRegistry` and are invisible to the game at runtime. Pydantic required-field validation is relaxed for abstract manifests — they may omit fields their children will supply.
- **`spec.properties`** (on `BaseSpec`) — a free-form `Dict[str, int | float | str | bool]` available on every manifest kind. Properties are static, author-defined values that parameterize a manifest's formulas and templates.
- **`this` template variable** — inside formula and template expressions, `this` exposes the current manifest's `properties` dict. Enables a base weapon manifest to define a damage formula that reads `this.get('damage_die', 4)`, while each child sets a different `damage_die` in its `properties`.
- **Chained inheritance** — a child may itself be a base for another manifest. The engine resolves chains at load time via topological sort; circular chains raise a `ContentLoadError`.
- **Load-time validation** — dangling `metadata.base` references (no same-kind manifest with that name) raise a `ContentLoadError`. Circular chains produce a clear error naming the full cycle.

### Manifest System

- **`Metadata` model** — gains `base: str | None = None` and `abstract: bool = False`.
- **`BaseSpec` parent class** — introduced as the new parent for all spec models (previously `BaseModel`). Carries `properties: Dict[str, int | float | str | bool]`.
- **Loader pipeline** — a new `resolve_inheritance()` pre-pass runs before Pydantic validation. Abstract manifests are stored as raw dicts; inheriting manifests are raw-dict-merged with their resolved base before Pydantic validates the combined result.
- **JSON Schema** — the union schema gains a permissive abstract arm (any spec content allowed when `metadata.abstract: true`). The per-kind schemas are post-processed to inject `foo+` sibling fields alongside every list and dict field, so editors understand the extend syntax without false validation errors.

### Template Context

- **`CombatFormulaContext`** — gains `this: Dict[str, int | float | str | bool]` populated with the triggering manifest's (item, skill, or enemy's) `properties` dict.
- **`ExpressionContext`** — gains `this: Dict[str, int | float | str | bool]` populated with the current adventure's `properties` dict in adventure step templates.

### Testlandia

A new `enemies/` goblin family demonstrates enemy variant inheritance: a `goblin-base` abstract enemy shares description and loot, with `goblin-scout`, `goblin-chief`, and `goblin-king` as concrete variants. A new `items/weapons/` subtree demonstrates item inheritance: a `sword-base` abstract item carries the combat formula and `grants_skills_equipped`, with `iron-sword`, `steel-sword`, and `silver-sword` as concrete variants differing only in `properties.damage_die`, `value`, and `displayName`. An adventure uses the goblin family and the sword family to make both features manually playable.

## Capabilities

### New Capabilities

- `manifest-inheritance`: The `metadata.base` and `metadata.abstract` fields, the inheritance resolver, circular-dep detection, and load-time validation for the base reference system.
- `manifest-properties`: The `BaseSpec` parent class, the `properties` field on all spec models, and the `this` variable in formula and template contexts.

### Modified Capabilities

- `manifest-system`: `Metadata` model gains `base` and `abstract` fields; loader pipeline gains the inheritance pre-pass; JSON Schema export gains abstract arm and `+` field variants.
- `dynamic-content-templates`: `ExpressionContext` gains `this`; mock context for load-time validation gains a mock `this`.
- `combat-system`: `CombatFormulaContext` gains `this`; formula rendering exposes `this`; mock formula context gains a mock `this`.

## Impact

- **`oscilla/engine/models/base.py`** — `Metadata` gains `base` and `abstract`; new `BaseSpec` class introduced.
- **`oscilla/engine/models/enemy.py`**, **`item.py`**, **`adventure.py`**, **`archetype.py`**, **`buff.py`**, **`skill.py`**, **`location.py`**, **`region.py`**, **`quest.py`**, **`recipe.py`**, **`loot_table.py`**, **`game.py`**, **`character_config.py`**, **`combat_system.py`**, **`custom_condition.py`** — each spec class's parent changed from `BaseModel` to `BaseSpec`.
- **`oscilla/engine/loader.py`** — new `resolve_inheritance()` function and supporting helpers (`_topo_sort_inheritance()`, `_merge_spec_dicts()`, `_validate_base_refs()`); `_run_pipeline()` updated to call the resolver before Pydantic validation.
- **`oscilla/engine/templates.py`** — `CombatFormulaContext` and `ExpressionContext` gain `this` field; `build_mock_context()` and mock formula context updated.
- **`oscilla/engine/schema_export.py`** — `export_union_schema()` gains abstract permissive arm; `export_schema()` post-processing injects `foo+` sibling fields.
- **`tests/engine/test_inheritance.py`** — new test file covering: basic field inheritance, chained chains, `+` extend, `this` in formula rendering, abstract manifest not registered, dangling-base error, circular-chain error.
- **`content/testlandia/enemies/`** — new goblin family with abstract base.
- **`content/testlandia/items/weapons/`** — new sword family with abstract base and `this.damage_die` formula.
- **`docs/authors/manifest-inheritance.md`** — new author guide for the inheritance system.
- **`docs/authors/README.md`** — table of contents updated.
