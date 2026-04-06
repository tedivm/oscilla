## 1. Data Models

- [x] 1.1 Add `StatThresholdTrigger`, `GameRejoinTrigger`, and `GameTriggers` Pydantic models to `oscilla/engine/models/game.py`
- [x] 1.2 Add `triggers: GameTriggers` and `trigger_adventures: Dict[str, List[str]]` fields to `GameSpec`
- [x] 1.3 Add `EmitTriggerEffect` to `oscilla/engine/models/adventure.py` and update the `Effect` union discriminator
- [x] 1.4 Add `pending_triggers: List[str]` field to `CharacterState` in `oscilla/engine/character.py`
- [x] 1.5 Add `max_trigger_queue_depth: int = Field(default=6, ge=1)` to `GameTriggers` in `oscilla/engine/models/game.py`
- [x] 1.6 Implement `enqueue_trigger(trigger_name: str, max_depth: int = 6) -> None` on `CharacterState`; all callsites SHALL pass `registry.game.spec.triggers.max_trigger_queue_depth`

## 2. Database

- [x] 2.1 Add `CharacterIterationPendingTrigger` ORM class to `oscilla/models/character_iteration.py` with composite PK `(iteration_id, position)` and `trigger_name: str`
- [x] 2.2 Add `pending_trigger_rows` back-reference to `CharacterIterationRecord` (ordered by `position`, cascade delete-orphan)
- [x] 2.3 Generate Alembic migration creating the `character_iteration_pending_triggers` table
- [x] 2.4 Update `load_character` in `oscilla/services/character.py` to restore `pending_triggers` from the ordered `pending_trigger_rows` relationship
- [x] 2.5 Update `_persist_diff` in `oscilla/engine/session.py` to atomically replace pending trigger rows (delete + insert by position) at `adventure_end`

## 3. Content Registry

- [x] 3.1 Add `trigger_index: Dict[str, List[str]]` and `stat_threshold_index: Dict[str, List[tuple[int, str]]]` fields to `ContentRegistry` in `oscilla/engine/registry.py`
- [x] 3.2 Implement `_build_trigger_index()` in the loader that maps `trigger_adventures` keys to ordered adventure ref lists
- [x] 3.3 Implement `_build_stat_threshold_index()` in the loader that maps stat names to sorted `(threshold, trigger_name)` pairs

## 4. Loader Validation

- [x] 4.1 Implement `_validate_trigger_adventures()` in `oscilla/engine/loader.py` checking keys against the known trigger vocabulary (built-in, `on_outcome_*`, threshold names, custom names)
- [x] 4.2 Add load warnings for unknown trigger keys, unresolvable adventure refs, and duplicate threshold names
- [x] 4.3 Add load warnings for `emit_trigger` effects referencing names not declared in `triggers.custom`
- [x] 4.4 Wire validation and index-building into `ContentRegistry.build()` after all manifests are registered

## 5. Trigger Detection Points

- [x] 5.1 Add `on_character_create` enqueue call to `GameSession._create_new_character()` (before first persist)
- [x] 5.2 Add `on_game_rejoin` detection to `GameSession.start()` using `characters.updated_at` and `GameRejoinTrigger.absence_hours`
- [x] 5.3 Add `on_level_up` enqueue call in the `xp_grant` effect handler (`oscilla/engine/steps/effects.py`) — once per level in `levels_gained`
- [x] 5.4 Add `on_outcome_<name>` enqueue call in `GameSession.run_adventure()` after outcome is returned
- [x] 5.5 Add `on_stat_threshold` upward-crossing detection in the `stat_change` effect handler
- [x] 5.6 Add `on_stat_threshold` upward-crossing detection in the `stat_set` effect handler
- [x] 5.7 Implement `emit_trigger` effect dispatch case in `oscilla/engine/steps/effects.py`

## 6. Drain Logic

- [x] 6.1 Implement `GameSession.drain_trigger_queue()` in `oscilla/engine/session.py` with FIFO loop, condition check, repeat-control check, and post-drain persist call
- [x] 6.2 Add Drain A call in `oscilla/engine/tui.py` immediately after `session.start()` returns
- [x] 6.3 Add Drain B call in `oscilla/engine/tui.py` immediately after each `session.run_adventure()` returns

## 7. Tests — Unit

- [x] 7.1 Create `tests/engine/test_triggers.py` with `test_enqueue_trigger_max_depth`
- [x] 7.2 Add `test_on_level_up_enqueues_per_level` to `tests/engine/test_triggers.py`
- [x] 7.3 Add `test_stat_threshold_upward_crossing_only` to `tests/engine/test_triggers.py`
- [x] 7.4 Add `test_drain_skips_ineligible` to `tests/engine/test_triggers.py`
- [x] 7.5 Create `tests/engine/test_trigger_loader_validation.py` with unknown-key, unknown-ref, valid `on_outcome_<custom>`, and invalid `on_outcome_<custom>` test cases
- [x] 7.6 Add test for duplicate threshold name load warning
- [x] 7.7 Add test for `emit_trigger` with undeclared custom name producing load warning

## 8. Tests — Integration

- [x] 8.1 Create `tests/fixtures/content/trigger_tests/` with a minimal fixture set (game manifest with all trigger types wired, one minimal adventure per trigger)
- [x] 8.2 Create `tests/engine/test_trigger_integration.py` with `test_on_character_create_fires_before_game_loop`
- [x] 8.3 Add `test_on_game_rejoin_fires_when_absent` integration test
- [x] 8.4 Add `test_on_level_up_fires_after_xp_grant` integration test
- [x] 8.5 Add `test_on_outcome_defeated_fires_after_defeat` integration test
- [x] 8.6 Add `test_emit_trigger_chains_custom_adventure` integration test
- [x] 8.7 Add `test_on_stat_threshold_fires_on_upward_crossing` integration test
- [x] 8.8 Add `test_pending_triggers_survive_session_roundtrip` (persist + load)

## 9. Documentation

- [x] 9.1 Update `docs/authors/game-configuration.md` with `triggers` and `trigger_adventures` schema, all trigger type names, `on_stat_threshold` syntax, `on_game_rejoin` config, `on_outcome_<name>` family, and custom trigger declaration
- [x] 9.2 Update `docs/authors/effects.md` with `emit_trigger` effect definition, fields, validation rules, and YAML example
- [x] 9.3 Update `docs/authors/adventures.md` with a note that triggered adventures use the same manifest structure and that `requires`/repeat controls apply; cross-ref to game-configuration.md
- [x] 9.4 Update `docs/dev/game-engine.md` with trigger queue lifecycle, detection points for each trigger type, drain algorithm, `trigger_index` / `stat_threshold_index` build process, and max-depth guard

## 10. Testlandia QA Content

- [x] 10.1 Update `content/testlandia/game.yaml` with `triggers` and `trigger_adventures` blocks covering all six trigger types
- [x] 10.2 Create `content/testlandia/adventures/triggered/test-character-intro.yaml`
- [x] 10.3 Create `content/testlandia/adventures/triggered/test-level-up-scene.yaml`
- [x] 10.4 Create `content/testlandia/adventures/triggered/test-defeat-recovery.yaml`
- [x] 10.5 Create `content/testlandia/adventures/triggered/test-threshold-scene.yaml`
- [x] 10.6 Create `content/testlandia/adventures/triggered/test-custom-trigger-scene.yaml`
- [x] 10.7 Create `content/testlandia/adventures/triggered/test-rejoin-scene.yaml`
- [x] 10.8 Add `emit_trigger: test-custom-event` effect to an existing testlandia adventure to provide a way to fire the custom trigger during manual QA

## 11. Validation

- [x] 11.1 Run `make tests` and confirm all existing tests pass
- [x] 11.2 Run `make chores` and fix any formatting issues
- [x] 11.3 Validate testlandia content package loads without warnings using `oscilla content test`
- [x] 11.4 Validate the-example-kingdom content package still loads cleanly (no regressions)
- [x] 11.5 Run `make check_ungenerated_migrations` to confirm no ungenerated migrations remain
