## 1. Schema Changes

- [x] 1.1 Add `derived: str | None` field to `StatDefinition` in `oscilla/engine/models/character_config.py` with validators: no `default` on derived stats, no `bool` derived stats
- [x] 1.2 Remove `HpFormula` class and `xp_thresholds: List[int]` field from `oscilla/engine/models/game.py`; remove `hp_formula` field from `GameSpec`
- [x] 1.3 Add `fire_mode: Literal["each", "highest"]` field (default `"each"`) to `StatThresholdTrigger` in `oscilla/engine/models/game.py`
- [x] 1.4 Add `stat_context: Literal["stored", "effective"]` field (default `"stored"`) to `StatDefinition` in `oscilla/engine/models/character_config.py`; add model validator rejecting `stat_context: effective` on non-derived stats
- [x] 1.5 Remove `XpGrantEffect` class from `oscilla/engine/models/adventure.py` and remove it from the `Effect` union

## 2. CharacterState Changes

- [x] 2.1 Remove `level`, `xp`, `hp`, `max_hp` as top-level fields from `CharacterState` dataclass in `oscilla/engine/character.py`
- [x] 2.2 Add `_derived_shadows: Dict[str, int | None]` field to `CharacterState` (ephemeral, default empty dict)
- [x] 2.3 Update `new_character()` to remove `hp_formula` reads and exclude derived stats from initial `stats` dict
- [x] 2.4 Update `to_dict()` to remove `level`, `xp`, `hp`, `max_hp` keys and exclude `_derived_shadows`
- [x] 2.5 Update `from_dict()` to not read `level`, `xp`, `hp`, `max_hp` as top-level keys
- [x] 2.6 Delete `add_xp()` method entirely

## 3. Derived Stat Runtime Engine

- [x] 3.1 Implement `_recompute_derived_stats(player, registry, template_engine, tui)` in `oscilla/engine/steps/effects.py`; iterates in topological order; for each stat selects stat context (`player.stats` or `effective_stats(registry)`) based on `stat_context` field; merges already-computed derived values for cross-derived chaining; updates `_derived_shadows`, calls `_fire_threshold_triggers()` for changed stats
- [x] 3.2 Implement `_fire_threshold_triggers(stat_name, old_value, new_value, player, registry)` in `oscilla/engine/steps/effects.py`; partitions crossed entries by `fire_mode`: `each` entries all enqueue in ascending threshold order; `highest` entries enqueue only the single highest crossed; both groups operate independently
- [x] 3.3 Add `_recompute_derived_stats()` call to TUI equip/unequip code paths (`oscilla/engine/tui.py`) when the registry contains any `stat_context: effective` derived stats
- [x] 3.4 Add `_recompute_derived_stats()` call after every `StatChangeEffect` dispatch in `run_effect()`
- [x] 3.5 Add `_recompute_derived_stats()` call after every `StatSetEffect` dispatch in `run_effect()`
- [x] 3.6 Remove `XpGrantEffect` case from `run_effect()`

## 4. Template Engine Changes

- [x] 4.1 Remove `level`, `hp`, `max_hp` fields from `PlayerContext` dataclass in `oscilla/engine/templates.py`
- [x] 4.2 Update `PlayerContext.from_character()` to merge `_derived_shadows` into `stats` dict so derived stats are accessible via `player.stats["name"]`
- [x] 4.3 Implement `_safe_roll_pool`, `_safe_keep_highest`, `_safe_keep_lowest`, `_safe_count_successes`, `_safe_explode`, `_safe_roll_fudge`, `_safe_weighted_roll` in `oscilla/engine/templates.py`
- [x] 4.4 Implement die shorthand aliases `_d4`, `_d6`, `_d8`, `_d10`, `_d12`, `_d20`, `_d100` in `oscilla/engine/templates.py`
- [x] 4.5 Implement `_ordinal`, `_signed`, `_stat_mod` in `oscilla/engine/templates.py`
- [x] 4.6 Register all new functions in `SAFE_GLOBALS` dict

## 5. Loader Validation Changes

- [x] 5.1 Remove `"on_level_up"` from the allowed built-in trigger keys in `oscilla/engine/loader.py`
- [x] 5.2 Implement `_validate_no_derived_stat_writes()` in loader: walk all adventure manifests and raise `ContentLoadError` for any `stat_change`/`stat_set` targeting a derived stat name
- [x] 5.3 Implement `_build_derived_eval_order()` in loader: build a directed dependency graph over derived stat formulas, perform DFS topological sort, raise `ContentLoadError` for any circular dependency (including self-reference), and store the sorted result in `ContentRegistry.derived_eval_order`
- [x] 5.4 Add derived stat formula precompile and mock-render pass in content load (same pipeline as adventure templates); mock context includes all stored stat names
- [x] 5.5 Update `on_stat_threshold` loader validation to accept both stored and derived stat names; emit load warning for unknown stat names
- [x] 5.6 Emit load warning when `trigger_adventures` contains `on_level_up` as a key

## 6. Database Migration

- [x] 6.1 Generate Alembic migration with `make create_migration MESSAGE="remove hardcoded progression fields"` and implement `upgrade()` to drop `level`, `xp`, `hp`, `max_hp` columns from `character_iterations`
- [x] 6.2 Implement `downgrade()` in the migration to re-add the four columns as nullable integers

## 7. TUI Changes

- [x] 7.1 Remove hardcoded reads of `player.level`, `player.xp`, `player.hp`, `player.max_hp` from `oscilla/engine/tui.py`; replace with reads from `player.stats` using publicly declared stats in `CharacterConfig`
- [x] 7.2 Remove XP progress bar display logic that read from `game.spec.xp_thresholds`; replace with a flat `<name>: <value>` list of public stats

## 8. Testlandia Content — character_config.yaml

- [x] 8.1 Add `xp` stat (`type: int`, `default: 0`, `bounds.min: 0`) to `content/testlandia/character_config.yaml` public_stats
- [x] 8.2 Add `level` as a derived stat with formula `{{ 1 + sum([1 for t in [100, 300, 600, 1000, 1500] if player.stats["xp"] >= t]) }}` to public_stats
  - **Note (deviation from spec):** Jinja2's `SandboxedEnvironment` forbids Python-style list comprehensions at runtime, so the actual implementation uses a chained ternary expression: `{{ 1 + (1 if player.stats['xp'] >= 100 else 0) + (1 if player.stats['xp'] >= 300 else 0) + ... }}`. The result is functionally equivalent. Authors should be aware that list comprehensions do not work in Jinja2 derived stat formulas.
- [x] 8.3 Add `hp` stat (`type: int`, `default: 0`, `bounds.min: 0`) and `max_hp` stat (`type: int`, `default: 0`) to public_stats
- [x] 8.4 Add `constitution` stat (`type: int`, `default: 10`) to public_stats
- [x] 8.5 Add `constitution_bonus` as a derived stat with formula `{{ floor((player.stats["constitution"] - 10) / 2) }}` to public_stats
- [x] 8.6 Remove any existing `title`, `hp`, `max_hp`, `level`, `xp` stat declarations that conflict with the new declarations

## 9. Testlandia Content — game.yaml

- [x] 9.1 Remove `hp_formula` and `xp_thresholds` keys from `content/testlandia/game.yaml`
- [x] 9.2 Add `triggers.on_stat_threshold` entries for `xp` thresholds at 100, 300, 600, 1000, 1500 with trigger names `level-2-reached` through `level-6-reached`
- [x] 9.3 Wire `on_character_create: [testlandia-character-creation]` in `trigger_adventures`
- [x] 9.4 Wire all five level-up trigger names to `[testlandia-level-up]` in `trigger_adventures`

## 10. Testlandia Content — Adventures

- [x] 10.1 Create or update `content/testlandia/adventures/testlandia-character-creation.yaml` with effects: `stat_set hp 10`, `stat_set max_hp 10`; acceptance criteria: adventure loads without errors and sets initial HP for new characters
- [x] 10.2 Create `content/testlandia/adventures/testlandia-level-up.yaml` that uses `roll_pool(1, 8)`, `signed()`, and `ordinal()` in its narrative, and applies `stat_change` to `max_hp` and `hp` using `d8() + player.stats["constitution_bonus"]`; acceptance criteria: adventure compiles, loads, and narrative text includes the die roll result and the character's new level
- [x] 10.3 Create `content/testlandia/adventures/testlandia-stat-formula-showcase.yaml` that demonstrates every new template function (dice pools, die aliases, display helpers) in a single narrative step with readable output; acceptance criteria: adventure loads and runs without errors, output displays all function results legibly
- [x] 10.4 Wire `testlandia-stat-formula-showcase` into a testlandia region so it is accessible from the world map; acceptance criteria: the adventure appears in the region's adventure pool

## 11. Tests

- [x] 11.1 Write unit tests in `tests/engine/test_derived_stats.py` covering: initial shadow computation, shadow update on stored stat change, no threshold fire on first initialization, shadow not in `to_dict()`, derived stat accessible via `player.stats` in `PlayerContext`, `stat_context: effective` sees equipment bonus, `stat_context: stored` does not see equipment bonus, derived-from-derived chain works in both stat_context modes
- [x] 11.2 Write integration tests in `tests/engine/test_stat_threshold_multicross.py` using a minimal fixture at `tests/fixtures/content/multicross/` covering: `fire_mode: each` multi-cross enqueues all thresholds ascending, `fire_mode: highest` multi-cross enqueues only the highest, mixed modes on same stat, `fire_mode` defaults to `each`, single threshold crossing, downward crossing does not fire
- [x] 11.3 Write load validation tests in `tests/engine/test_derived_stat_validation.py` using fixtures at `tests/fixtures/content/bad-derived-write/` and `tests/fixtures/content/circular-derived/` covering: stat_change targeting derived stat is a load error, stat_set targeting derived stat is a load error, cross-derived reference is a load error, derived stat with default value is a load error, bool derived stat is a load error
- [x] 11.4 Write unit tests in `tests/engine/test_template_functions.py` covering all new SAFE_GLOBALS functions: `roll_pool`, `keep_highest`, `keep_lowest`, `count_successes`, `explode`, `roll_fudge`, `weighted_roll`, `d4`–`d100`, `ordinal` (including teen edge cases), `signed`, `stat_mod`
- [x] 11.5 Write unit tests for `CharacterState` changes in `tests/engine/test_character_state.py` (or update existing): `new_character()` does not set level/xp/hp/max_hp fields, `to_dict()` has no top-level progression keys, `from_dict()` does not fail without those keys, derived stats absent from `stats` dict
- [x] 11.6 Update any existing tests that reference `player.level`, `player.xp`, `player.hp`, `player.max_hp`, `xp_grant`, `add_xp()`, `hp_formula`, or `xp_thresholds` to use the new stat-based approach
- [x] 11.7 Run full test suite with `make tests` and verify zero errors

## 12. Documentation

- [x] 12.1 Update `docs/authors/game-configuration.md`: remove `hp_formula` and `xp_thresholds` docs; add `on_stat_threshold` examples for XP-based level advancement; add derived stat pattern in `character_config.yaml`; add `on_character_create` for HP initialization with a complete worked example
- [x] 12.2 Update `docs/authors/conditions.md` (and any other doc referencing `player.level`, `player.hp`, `player.max_hp`): change all examples to use `player.stats["level"]` etc.
- [x] 12.3 Update `docs/authors/effects.md` or equivalent: remove `xp_grant` documentation; add section on `stat_change` as XP replacement; add full authoring walkthrough showing XP + derived level + threshold trigger
- [x] 12.4 Update `docs/authors/templates.md`: add full reference table for all new template functions with examples; add a D20-style HP-on-level-up example using `roll_pool`
- [x] 12.5 Update `docs/dev/game-engine.md`: remove references to `level/xp/hp/max_hp` as special engine fields; document derived stat shadow mechanism and `_recompute_derived_stats()` / `_fire_threshold_triggers()` call points

## 13. ROADMAP Update

- [x] 13.1 Remove the "Stat Formula Templates" item from `ROADMAP.md` (it is superseded by this change)
- [x] 13.2 Add "Extended Template Primitives" as a new deferred roadmap item covering: `lerp`, `average`, `percent`, `scale`, additional pool manipulation functions, and any other numeric utility functions not included in this change
