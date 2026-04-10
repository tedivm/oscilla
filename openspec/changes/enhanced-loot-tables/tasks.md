## 1. Spec Updates

- [x] 1.1 Update `specs/loot-tables/spec.md` to add `EnemySpec.loot` migration requirement (`List[LootEntry]` → `List[LootGroup]`)

## 2. Model Changes

- [x] 2.1 Update `LootEntry` in `oscilla/engine/models/loot_table.py`: rename `quantity` → `amount: int | str = 1`, add `requires: Condition | None = None`, make `weight: int = 1` explicit default
- [x] 2.2 Create `LootGroup` model in `oscilla/engine/models/loot_table.py`: `count: int | str = 1`, `method: Literal["weighted", "unique"] = "weighted"`, `requires: Condition | None = None`, `entries: List[LootEntry]` (min_length=1)
- [x] 2.3 Replace `LootTableSpec.loot: List[LootEntry]` with `groups: List[LootGroup]` (min_length=1)
- [x] 2.4 Change `EnemySpec.loot` type from `List[LootEntry]` to `List[LootGroup]` in `oscilla/engine/models/enemy.py`
- [x] 2.5 Update `ItemDropEffect` in `oscilla/engine/models/adventure.py`: remove `loot` field, remove `count` field, add `groups: List[LootGroup] | None = None`, update `model_validator` to enforce exactly one of `groups` / `loot_ref`

## 3. Loader and Registry

- [x] 3.1 Add `_walk_loot_groups(groups, path)` helper in `oscilla/engine/loader.py` that yields template string locations for `group.count` and `entry.amount`
- [x] 3.2 Wire `_walk_loot_groups` into `_collect_all_template_strings` for all three loot sites: `LootTable` manifests, enemy `spec.loot`, adventure `item_drop` inline `groups`
- [x] 3.3 Extend the semantic validator to traverse `LootGroup.requires` and `LootEntry.requires` at all three loot sites for load-time condition ref validation (milestone, stat, item, archetype refs → `LoadError`)
- [x] 3.4 Update `_validate_loot_refs` (or equivalent) to resolve `loot_ref` only against `registry.loot_tables` — remove the enemy fallback path
- [x] 3.5 Set `creatable=True` on `ManifestKind("loot-table", ...)` in `oscilla/engine/kinds.py`

## 4. Runtime Effects

- [x] 4.1 Rewrite `_resolve_loot_list` → `_resolve_loot_groups(groups, player, registry)` in `oscilla/engine/steps/effects.py` implementing the multi-group algorithm: per-group condition check, per-entry condition filter, graceful empty-pool skip, `render_int` for template `count`, `method: weighted` uses `random.choices` with weights, `method: unique` uses `random.sample` with count clamped to pool size, merge results
- [x] 4.2 Clamp `render_int` results for `count` and `amount` to `max(0, value)` in the resolver
- [x] 4.3 Update `run_effect` dispatch for `ItemDropEffect` to call `_resolve_loot_groups(groups, player, registry)`, passing `player` (already available at the call site)

## 5. CLI Scaffold

- [x] 5.1 Add `loot-table` scaffold template to `oscilla/cli_content.py` with a minimal two-group example demonstrating `count`, `requires`, and `entries`

## 6. Content Migration

- [x] 6.1 Migrate `content/testlandia/regions/quests/loot-tables/test-loot.yaml` from flat `loot:` to `groups:` format
- [x] 6.2 Migrate all ~12 inline `loot:` adventure YAML files in `content/testlandia/regions/items/` to use `groups:` on their `item_drop` effects
- [x] 6.3 Add `loot: [...]` (using `List[LootGroup]`) to at least one testlandia enemy (e.g. `iron-golem`) to exercise enemy loot resolution in QA
- [x] 6.4 Add a new dedicated loot-table QA region in testlandia with adventures that exercise: multi-group drops, conditional groups (`requires`), conditional entries, template `count`, template `amount`, `method: unique` drops

## 7. Tests

- [x] 7.1 Unit: `LootEntry` model — defaults, `amount` template string accepted, `requires` optional
- [x] 7.2 Unit: `LootGroup` model — `entries` required (min 1), `count` defaults to 1, template string accepted, `requires` optional
- [x] 7.3 Unit: `LootTableSpec` — rejects empty `groups`, accepts valid `List[LootGroup]`
- [x] 7.4 Unit: `EnemySpec.loot` accepts `List[LootGroup]`; rejects flat `List[LootEntry]`
- [x] 7.5 Unit: `ItemDropEffect` `model_validator` — exactly one of `groups` / `loot_ref` required; both present raises error; neither present raises error
- [x] 7.6 Unit: `_resolve_loot_groups` — group-level condition skip, entry-level condition filter, empty-pool graceful skip, `method: weighted` with-replacement draw, `method: unique` without-replacement draw with count clamped to pool size, integer `count` and `amount`, template `count` and `amount` resolution
- [x] 7.7 Integration: load fixture `LootTable` manifest (in `tests/fixtures/content/`) with two groups, verify registry registration and group structure
- [x] 7.8 Integration: load fixture adventure with inline `groups:` on `item_drop`, run effect end-to-end, verify items added to inventory
- [x] 7.9 Integration: load fixture enemy with `loot: [{entries: [...]}]`, run combat resolution, verify loot drops
- [x] 7.10 Load-error: fixture with unknown item ref in `LootEntry.requires` condition → `LoadError`
- [x] 7.11 Load-error: fixture with unknown milestone ref in `LootGroup.requires` condition → `LoadError`
- [x] 7.12 Schema: `oscilla content schema loot-table` output includes `groups`, `LootGroup`, and `LootEntry` fields with correct types

## 8. Documentation

- [x] 8.1 Create `docs/authors/loot-tables.md` — canonical author reference covering: `LootTable` manifest anatomy, `groups` + `entries` schema, `count` / `amount` template expressions, `requires` on groups and entries, inline `groups:` in adventures, `loot_ref`, enemy `loot:` with groups, migration from old `loot:` syntax; full worked example with multiple pools and a conditional group
- [x] 8.2 Add `loot-tables.md` entry to `docs/authors/README.md`
- [x] 8.3 Update `docs/authors/enemies.md` — update `loot:` field documentation to reflect `List[LootGroup]`, link to loot-tables
- [x] 8.4 Update `docs/dev/game-engine.md` — update `item_drop` effect and enemy loot sections to reflect the unified group model
