## 1. Project Setup

- [x] 1.1 Add `rich` and `ruamel.yaml` dependencies to `pyproject.toml`
- [x] 1.2 Create the `oscilla/engine/` package with `__init__.py`
- [x] 1.3 Create the `oscilla/engine/models/` package with `__init__.py`
- [x] 1.4 Create the `content/` directory at the project root with a `.gitkeep` placeholder
- [x] 1.5 Add `CONTENT_PATH` setting to `oscilla/conf/settings.py` pointing to the default content directory
- [x] 1.6 Update `pyproject.toml` to include `content/` in package data so it ships with the library

## 2. Manifest Schema Models

- [x] 2.1 Create `oscilla/engine/models/base.py` with `ManifestEnvelope`, `Metadata`, and shared field types (condition tree nodes)
- [x] 2.2 Create the `Condition` discriminated union model in `base.py` covering `all`, `any`, `not`, `level`, `milestone`, `item`, `character_stat`, `class`, `prestige_count`, `enemies_defeated`, `locations_visited`, and `adventures_completed` leaf types
- [x] 2.3 Create `oscilla/engine/models/region.py` with `RegionSpec` and `RegionManifest`
- [x] 2.4 Create `oscilla/engine/models/location.py` with weighted adventure pool entries and `LocationManifest`
- [x] 2.5 Create `oscilla/engine/models/adventure.py` with event step models (narrative, combat, choice, stat_check) and effect models (xp_grant, item_drop, milestone_grant, end_adventure) as separate discriminated unions (`Step` and `Effect`), along with `OutcomeBranch`, `ChoiceOption`, `AdventureSpec`, and `AdventureManifest`; validate that no `label` string is duplicated across top-level steps and that all `goto` targets resolve to a declared label
- [x] 2.6 Create `oscilla/engine/models/enemy.py` with loot table entries and `EnemyManifest`
- [x] 2.7 Create `oscilla/engine/models/item.py` with item kind enum and `ItemManifest`
- [x] 2.8 Create `oscilla/engine/models/recipe.py` with ingredient list and `RecipeManifest`
- [x] 2.9 Create `oscilla/engine/models/quest.py` with stage list and `QuestManifest`
- [x] 2.10 Create `oscilla/engine/models/game_class.py` with placeholder `ClassManifest`
- [x] 2.11 Create `oscilla/engine/models/game.py` with `GameManifest` for global game settings (XP thresholds, level formula)
- [x] 2.12 Create `oscilla/engine/models/character_config.py` with `StatDefinition` (name, type, default) and `CharacterConfigManifest` containing `public_stats` and `hidden_stats` lists; validate that no stat name appears in both lists and that each default value is type-compatible

## 3. Content Loader and Registry

- [x] 3.1 Create `oscilla/engine/registry.py` with `ContentRegistry` — a typed in-memory store keyed by kind and name
- [x] 3.2 Create `oscilla/engine/loader.py` with `ContentLoader.scan()` — recursively finds all `.yaml`/`.yml` files in a directory
- [x] 3.3 Implement `ContentLoader.parse()` — reads each file with `ruamel.yaml` in safe mode, validates the envelope, dispatches to the correct Pydantic model, and collects parse errors
- [x] 3.4 Implement `ContentLoader.validate_references()` — resolves all cross-references (location→region, adventure→enemy, adventure steps→items, recipe→items, stat conditions/steps→CharacterConfig stat names) and collects broken ref errors
- [x] 3.5 Implement `ContentLoader.build_effective_conditions()` — walks the region tree and attaches the aggregated `all` condition chain to each location
- [x] 3.6 Implement `ContentLoader.load()` — orchestrates scan → parse → validate_references → build_effective_conditions, raises `ContentLoadError` with all collected errors on failure
- [x] 3.7 Write tests for `ContentLoader` covering: valid load, unknown kind error, missing envelope field, broken cross-reference, region inheritance chain

## 4. Condition Evaluator

- [x] 4.1 Create `oscilla/engine/conditions.py` with `evaluate(condition, player_state) -> bool`
- [x] 4.2 Implement `all` / `any` / `not` recursive evaluation
- [x] 4.3 Implement `level` leaf — `player.level >= value`
- [x] 4.4 Implement `milestone` leaf — `name in player.milestones`
- [x] 4.5 Implement `item` leaf — `item_ref in player.inventory and quantity > 0`
- [x] 4.6 Implement `character_stat` leaf — evaluate `gte`, `lte`, `eq` comparisons against `player.stats[name]` where the stat name is defined in `CharacterConfig`
- [x] 4.7 Implement `class` leaf — no-op, always returns `True`
- [x] 4.8 Implement `prestige_count` leaf — evaluate comparison against `player.prestige_count`
- [x] 4.9 Handle `None` / missing condition — always returns `True`
- [x] 4.10 Write tests for each leaf type and logical operator, including nested compound conditions and statistics predicates
- [x] 4.11 Implement `enemies_defeated` leaf — evaluate comparison against `player.statistics.enemies_defeated[name]`, treating missing keys as 0
- [x] 4.12 Implement `locations_visited` leaf — evaluate comparison against `player.statistics.locations_visited[name]`, treating missing keys as 0
- [x] 4.13 Implement `adventures_completed` leaf — evaluate comparison against `player.statistics.adventures_completed[name]`, treating missing keys as 0

## 5. Player State

- [x] 5.1 Create `oscilla/engine/player.py` with `PlayerStatistics` dataclass (three `Dict[str, int]` counter fields: `enemies_defeated`, `locations_visited`, `adventures_completed`) and `PlayerState` dataclass covering all fixed fields from the spec, plus a `stats: Dict[str, int | float | str | bool | None]` mapping populated dynamically from `CharacterConfig` at character creation; do not use `Any` — the narrow type keeps Phase 3 JSON column serialization unambiguous
- [x] 5.2 Implement `PlayerState.add_item(ref, quantity)` and `remove_item(ref, quantity)` with error on underflow
- [x] 5.3 Implement `PlayerState.grant_milestone(name)` (no-op if already present) and `has_milestone(name)`
- [x] 5.4 Implement `PlayerState.add_xp(amount, xp_thresholds, hp_per_level)` — increments XP, loops through level-up thresholds, increments `self.level` and `self.max_hp += hp_per_level` for each level gained; returns the list of new level numbers (empty if none)
- [x] 5.5 Implement `PlayerState.equip(item_ref, slot)` — moves from inventory to slot, returns displaced item to inventory
- [x] 5.6 Implement `PlayerState.new_player(name, game_manifest, character_config) -> PlayerState` factory: initialise `stats` from all `public_stats` and `hidden_stats` in `CharacterConfig`; set `hp` and `max_hp` from `game_manifest.spec.hp_formula.base_hp`; all collection fields start empty
- [x] 5.7 Implement statistics counter helpers: `record_enemy_defeated(enemy_ref)`, `record_location_visited(location_ref)`, `record_adventure_completed(adventure_ref)` — each increments the appropriate counter by 1
- [x] 5.8 Write tests for inventory management, milestone management, XP/levelling, equipment, and statistics counter methods

## 6. Adventure Pipeline

- [x] 6.1 Create `oscilla/engine/pipeline.py` with the `TUICallbacks` protocol and `AdventurePipeline` class; the pipeline constructor accepts `registry: ContentRegistry`, `player: PlayerState`, and `tui: TUICallbacks`; `ConditionEvaluator` is instantiated internally by the pipeline and does not appear in its public interface
- [x] 6.2 Implement the step dispatcher — iterates steps in order, calls the appropriate handler by step type
- [x] 6.3 Create `oscilla/engine/steps/narrative.py` — displays text, waits for acknowledgement via TUI callback
- [x] 6.4 Create `oscilla/engine/steps/combat.py` — implements the turn loop: player attacks, enemy attacks, repeat; handles win/defeat/flee outcomes; updates player HP, calls `player.record_enemy_defeated(enemy_ref)` on win, and grants XP on win
- [x] 6.5 Create `oscilla/engine/steps/choice.py` — filters options by condition, presents menu via TUI callback, executes selected branch's steps recursively
- [x] 6.6 Create `oscilla/engine/steps/effects.py` with `run_effect(effect, player, registry)` dispatcher: `XpGrantEffect` calls `player.add_xp()` with game manifest thresholds; `ItemDropEffect` performs weighted random selection for `count` rolls and calls `player.add_item()`; `MilestoneGrantEffect` calls `player.grant_milestone()`; `EndAdventureEffect` raises `_EndSignal(outcome)` from `engine/signals.py`
- [x] 6.7 Create `oscilla/engine/steps/stat_check.py` — evaluates condition, executes `on_pass` or `on_fail` branch recursively
- [x] 6.8 Write tests for the pipeline covering: step ordering, combat win/loss/flee outcomes, statistics counter increments, choice filtering, item drop distribution, xp grant levelling, `end_adventure` signal termination, and `goto`/`label` jumps

## 7. TUI Game Loop

- [x] 7.1 Create `oscilla/engine/tui.py` with the `RichTUI` class (concrete `TUICallbacks` implementation: `show_text`, `show_menu`, `show_combat_round`, `wait_for_ack`), the standalone `show_status(player, registry)` function (renders level/HP/XP/public-stats panel, dynamically reads `CharacterConfig.public_stats`), and a module-level `console = Console()` instance; `tui.py` is the only module in the codebase that imports `rich` directly
- [x] 7.2 Add character creation to `oscilla/cli.py` — prompt for name with `rich.prompt.Prompt`, call `PlayerState.new_player(name=name, game_manifest=registry.game, character_config=registry.character_config)` to build initial player state with stat defaults from `CharacterConfig` and base HP from `GameManifest`
- [x] 7.3 Implement `_select_region(player, registry, evaluator, tui)` in `oscilla/cli.py` — filter accessible regions via condition evaluator, present a numbered menu via `tui.show_menu()`, return the chosen region ref or `None` on Quit; call `raise SystemExit(1)` if no regions are accessible
- [x] 7.4 Implement `_select_location(player, registry, evaluator, region_ref, tui)` in `oscilla/cli.py` — filter accessible locations within the chosen region, render a region header via `tui.show_text()`, present a numbered menu with Back option via `tui.show_menu()`; do NOT record the location visit here — the counter is incremented in the game loop only after `_pick_adventure()` confirms a non-`None` result
- [x] 7.5 Implement `_pick_adventure(player, registry, evaluator, location_ref)` in `oscilla/cli.py` — filter the location's adventure pool to entries whose `requires` condition passes, draw with `random.choices()` using declared weights, return `None` on an empty pool; `record_adventure_completed` is called by `AdventurePipeline.run()` internally and must NOT be called in the game loop
- [x] 7.6 Implement `_show_outcome(outcome, tui)` in `oscilla/cli.py` — look up a plain-text message for the `AdventureOutcome` and display it via `tui.show_text()`; wire the adventure pipeline to the TUI by passing the shared `tui` instance to `AdventurePipeline(tui=tui)`
- [x] 7.7 Add the `game` command to `oscilla/cli.py`: call `_load_content()`, instantiate `ConditionEvaluator()` and `RichTUI()`, build player with `new_player()`, then run the `while True` loop — `show_status` → `_select_region(tui=tui)` → `_select_location(tui=tui)` → `_pick_adventure` → `player.record_location_visited` → `AdventurePipeline(tui=tui).run()` → `_show_outcome(tui=tui)`; the same `tui` instance is passed to all helpers and the pipeline; `show_status` is called at the top of each loop iteration (before region selection) and again after `_show_outcome` so the player always sees up-to-date stats after an adventure
- [ ] 7.8 Write game loop tests in `tests/test_cli.py`: (a) test `_select_region` returns `None` on Quit; (b) test `_select_location` returns `None` on Back; (c) test `_pick_adventure` returns `None` for a fully-gated pool; (d) test visit counter is NOT incremented on empty pool; (e) test `_show_outcome` messages via `MockTUI.texts`; (f) test the `game` command end-to-end with `typer.testing.CliRunner`, `MockTUI` injected via `patch("oscilla.cli.RichTUI")`, and Quit selection exits with code 0

## 8. Validate CLI Command

- [x] 8.1 Add the `validate` command to `oscilla/cli.py` that invokes `ContentLoader.load()` and prints success or all errors with source file paths
- [x] 8.2 Ensure the command exits with code 0 on success and non-zero on any validation failure
- [x] 8.3 Write tests for the validate command using valid and invalid content fixtures

## 9. POC Content Package

- [x] 9.1 Create `content/game.yaml` — global settings including XP thresholds per level (levels 1–10), base HP formula, game title
- [x] 9.2 Create `content/classes/warrior.yaml` — placeholder class manifest
- [x] 9.3 Create three region manifests: `content/regions/kingdom.yaml` (root, always accessible), `content/regions/wilderness.yaml` (child of kingdom, requires level 3), `content/regions/dungeon.yaml` (child of wilderness, requires level 7 + milestone)
- [x] 9.4 Create ten location manifests distributed across the three regions, with at least two having their own `unlock` conditions
- [x] 9.5 Create at least twelve enemy manifests with a range of difficulty levels; at least three SHALL have multi-entry loot tables
- [x] 9.6 Create at least twenty-five item manifests covering consumable, weapon, armor, quest, material, and prestige-tagged kinds
- [x] 9.7 Create at least five recipe manifests that reference existing items
- [x] 9.8 Create at least fifteen adventure manifests: at minimum eight combat, three narrative/choice (non-combat), two with `requires` conditions; ensure every step type appears in at least one adventure
- [x] 9.9 Create at least two quest manifests with at least two stages each, advancement tied to milestones
- [x] 9.10 Run `oscilla validate` against the completed POC content and confirm zero errors

## 10. Tests and Quality

- [x] 10.1 Ensure test file structure mirrors `oscilla/engine/` layout under `tests/engine/`
- [x] 10.2 Create `tests/engine/conftest.py` with `base_player`, `minimal_registry`, and `mock_tui` fixtures; the `MockTUI` class definition and fixture implementation are fully specified in the design (TUI Game Loop → MockTUI section); also add a `minimal_content_dir: Path` fixture returning the path to `tests/fixtures/content/minimal/` for `game` command end-to-end tests
- [x] 10.3 Confirm all new code passes `mypy` type checking
- [x] 10.4 Confirm all new code passes `ruff` linting and `black` formatting
- [x] 10.5 Confirm `make tests` passes with coverage across the new engine modules
- [x] 10.6 Create `tests/fixtures/content/minimal/` — the smallest valid content set (one Game, one CharacterConfig, one Region, one Location, one Adventure, one Enemy, one Item) used as the default integration fixture
- [x] 10.7 Create `tests/fixtures/content/broken_refs/` — manifests with known broken cross-references for loader error-accumulation tests
- [x] 10.8 Create `tests/fixtures/content/region_chain/` — a three-deep region parent chain with unlock conditions, for effective-condition compilation tests
- [x] 10.9 Create `tests/fixtures/content/combat_pipeline/` — a single combat adventure with one enemy and one item drop, for end-to-end pipeline tests
- [x] 10.10 Create `tests/fixtures/content/condition_gates/` — adventures and locations gated by each leaf condition type (level, milestone, item, character_stat, enemies_defeated, locations_visited, adventures_completed, prestige_count)
- [x] 10.11 Update `AGENTS.md` to add the Game Engine Testing section under the existing Testing section

## 11. Documentation

- [x] 11.1 Create `docs/dev/game-engine.md` — engine internals only (no TUI or interface specifics): architecture diagram, module layout, the `TUICallbacks` protocol and its four-method contract, `MockTUI` usage for engine tests, signal protocol (`_GotoSignal`/`_EndSignal`), and extension guides for new step types, effect types, condition leaves, and manifest kinds
- [x] 11.2 Create `docs/dev/tui.md` — CLI/TUI interface layer: `RichTUI` implementation and why it is the only Rich importer, `show_status()` and its dynamic public-stats rendering, game loop helper structure (`_select_region`, `_select_location`, `_pick_adventure`), the visit-counter timing rule, CLI command reference (`game`, `validate`), and testing CLI code with `CliRunner` and `patch("oscilla.cli.RichTUI")`
- [x] 11.3 Create `docs/authors/content-authoring.md` — full content author reference: manifest envelope format, every kind with field descriptions and minimal examples, all condition types, all step and effect types, `goto`/`label` linking, and the `validate` command
- [x] 11.4 Update `docs/dev/README.md`: add a **Game Engine** subsection linking to `docs/dev/game-engine.md` (engine internals), a **CLI Interface** subsection linking to `docs/dev/tui.md`, and placeholder entries for future **REST API** and **Frontend** subsections so the index communicates the intended interface-layer structure; update `docs/authors/README.md` with a link to `docs/authors/content-authoring.md`
- [x] 11.5 Confirm both developer documents and the author document are accurate against the final implementation (run through at least one example manifest from the POC content as a smoke test)
