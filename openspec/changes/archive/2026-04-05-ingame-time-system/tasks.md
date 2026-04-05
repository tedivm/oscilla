## 1. Models — New Time System Manifest Models

- [x] 1.1 Create `oscilla/engine/models/time.py` with `RootCycleSpec`, `DerivedCycleSpec`, `CycleSpec` (discriminated union), `EraSpec`, and `GameTimeSpec` Pydantic models as specified in the design doc. `EraSpec` has `start_condition` and `end_condition` fields (not `condition`). Include Pydantic `model_validator` for label count enforcement.
- [x] 1.2 Add `from oscilla.engine.models.time import GameTimeSpec` import and `time: GameTimeSpec | None = None` field to `GameSpec` in `oscilla/engine/models/game.py`.
- [x] 1.3 Add `ticks: int | None`, `cooldown_ticks: int | None`, and `cooldown_game_ticks: int | None` fields to `AdventureSpec` in `oscilla/engine/models/adventure.py`.
- [x] 1.4 Add `cooldown_adventures` deprecation `model_validator` to `AdventureSpec` that copies its value to `cooldown_ticks` (when absent) and logs a warning. The `cooldown_adventures` field is retained for backward compatibility.
- [x] 1.5 Add `AdjustGameTicksEffect` model (type: `adjust_game_ticks`, delta: int) to `oscilla/engine/models/adventure.py` and register it in the `Effect` union.
- [x] 1.6 Add `GameCalendarTimeCondition`, `GameCalendarCycleCondition`, and `GameCalendarEraCondition` model classes to `oscilla/engine/models/base.py`. Register all three in the `Condition` union.

## 2. Character State — Dual Clock Fields

- [x] 2.1 Add `internal_ticks: int = 0` and `game_ticks: int = 0` fields to the `CharacterState` dataclass in `oscilla/engine/character.py`.
- [x] 2.2 Rename `adventure_last_completed_at_total` to `adventure_last_completed_at_ticks` in `CharacterState`. Update all internal usages in the same file.
- [x] 2.3 Update `CharacterState.to_dict()` to serialize `internal_ticks`, `game_ticks`, `adventure_last_completed_at_ticks`, `era_started_at_ticks`, and `era_ended_at_ticks` under the new key names.
- [x] 2.4 Update `CharacterState.from_dict()` to deserialize both `adventure_last_completed_at_ticks` (new) and `adventure_last_completed_at_total` (old, fallback) for backward compatibility. Deserialize `internal_ticks` and `game_ticks` with default of 0. Deserialize `era_started_at_ticks` and `era_ended_at_ticks` with default of `{}`.
- [x] 2.5 Update `CharacterState.is_adventure_eligible()` to replace the `cooldown_adventures` check with `cooldown_ticks` (against `internal_ticks`) and `cooldown_game_ticks` (against `game_ticks`). Record `internal_ticks` at completion in `adventure_last_completed_at_ticks`.
- [x] 2.6 Add `era_started_at_ticks: Dict[str, int]` and `era_ended_at_ticks: Dict[str, int]` fields to `CharacterState` (both default to empty dict). These record `game_ticks` at the moment each era's start/end condition first fires. Reset on new iteration.

## 3. Database — Migration and Model Columns

- [x] 3.1 Add `internal_ticks: Mapped[int]` and `game_ticks: Mapped[int]` columns (BigInteger, default 0, not null) to `CharacterIterationRecord` in `oscilla/models/character_iteration.py`. Add `era_state_rows` relationship.
- [x] 3.2 Rename `last_completed_at_total` to `last_completed_at_ticks` and change its type from `Integer` to `BigInteger` on `CharacterIterationAdventureState`. Update all references in `save_character()` and `load_character()`.
- [x] 3.3 Add `CharacterIterationEraState` child table to `oscilla/models/character_iteration.py` with columns `iteration_id` (FK PK), `era_name` (String PK), `started_at_game_ticks` (BigInteger nullable), `ended_at_game_ticks` (BigInteger nullable).
- [x] 3.4 Run `make create_migration MESSAGE="add ingame time tables"` to generate the Alembic migration covering all four database changes (two new columns on `character_iterations`, column rename on `character_iteration_adventure_state`, new `character_iteration_era_state` table). Review the generated file for correctness and write the downgrade.

## 4. In-Game Time Resolver

- [x] 4.1 Create `oscilla/engine/ingame_time.py` with `CycleState`, `EraState`, `InGameTimeView`, and `InGameTimeResolver` as specified in the design doc.
- [x] 4.2 Implement `InGameTimeResolver.__init__()`: build `_by_name` dict (including aliases), compute `_ticks_per_unit` for every cycle.
- [x] 4.3 Implement `InGameTimeResolver.resolve()`: compute all cycle labels and era states using the epoch offset, current tick values, and the latch dicts from `CharacterState`.
- [x] 4.6 Implement `update_era_states(player, spec, registry)` in `oscilla/engine/ingame_time.py`. For each era: if not yet started and `start_condition` is set, evaluate it and record `player.game_ticks` in `era_started_at_ticks` when true. If already started and not ended and `end_condition` is set, evaluate it and record `player.game_ticks` in `era_ended_at_ticks` when true.
- [x] 4.4 Implement `compute_epoch_offset(spec: GameTimeSpec) -> int` in `oscilla/engine/loader.py`.
- [x] 4.5 Update `oscilla/engine/registry.py` to build and store an `InGameTimeResolver` when `game.spec.time` is not None. Add `ingame_time_resolver` property.

## 5. Semantic Validator

- [x] 5.1 Add `_validate_time_spec()` method to the semantic validator. Enforce: exactly one root cycle, no circular parent references, all parent names resolve, no duplicate names/aliases. Call it from the main `validate()` method.
- [x] 5.2 Extend `_validate_time_spec()` to enforce: labels list length equals count (per cycle), epoch values reference declared cycles and valid labels/indices, era `tracks` values reference declared cycles.
- [x] 5.3 Extend `_validate_time_spec()` to validate all `game_calendar_cycle_is` and `game_calendar_era_is` conditions found in the loaded content: cycle names must be declared, `value` fields must be in the cycle's declared labels, era names must be declared.

## 6. Condition Evaluator

- [x] 6.1 Add imports for `GameCalendarTimeCondition`, `GameCalendarCycleCondition`, `GameCalendarEraCondition` to `oscilla/engine/conditions.py`.
- [x] 6.2 Add `case GameCalendarTimeCondition()` branch to the `evaluate()` match block. Query `internal_ticks` or `game_ticks` based on `clock` field; use `_numeric_compare` helper; log warning and return False if time system not configured.
- [x] 6.3 Add `case GameCalendarCycleCondition()` branch. Resolve cycle name from `InGameTimeView`; compare label to `value`; log warning and return False if cycle not found or time system not configured.
- [x] 6.4 Add `case GameCalendarEraCondition()` branch. Resolve era from `InGameTimeView`; compare `active` to `state`; log warning and return False if era not found or time system not configured.

## 7. Adventure Pipeline

- [x] 7.1 Add `_resolve_tick_cost(adventure_ref: str) -> int` helper to the pipeline class. Prefers adventure-level `ticks`; falls back to `game.time.ticks_per_adventure`; falls back to 1.
- [x] 7.2 After recording adventure completion in the pipeline, advance both `internal_ticks` and `game_ticks` by `_resolve_tick_cost(adventure_ref)`. Record `adventure_last_completed_at_ticks[adventure_ref] = internal_ticks`. Then call `update_era_states(player, spec, registry)` when `game.spec.time` is not None.
- [x] 7.4 Update the pipeline service call to invoke `update_character_tick_state()` after each adventure completes, passing the updated tick counters, adventure latch dict entry, and era latch dicts.
- [x] 7.3 Add `case AdjustGameTicksEffect()` handler to the effect dispatch. Apply delta to `game_ticks`; apply `pre_epoch_behavior` clamping; leave `internal_ticks` unchanged; log warning if time system not configured.

## 8. Templates

- [x] 8.1 Add `InGameTimeView` to module imports in `oscilla/engine/templates.py`. Add `ingame_time: InGameTimeView | None = None` field to `ExpressionContext`.
- [x] 8.2 Update the pipeline (or template context builder) to populate `ExpressionContext.ingame_time` using the registry's `InGameTimeResolver` when the time system is configured. Pass `None` when it is not.

## 9. Character Service

- [x] 9.1 Update `save_character()` in `oscilla/services/character.py` to write `internal_ticks` and `game_ticks` on the `CharacterIterationRecord`, use `last_completed_at_ticks` on adventure state rows, and insert any initial `CharacterIterationEraState` rows.
- [x] 9.2 Update `load_character()` to eager-load `era_state_rows`, read `internal_ticks`/`game_ticks` from the iteration record, build `adventure_last_completed_at_ticks` from the renamed column, and build `era_started_at_ticks`/`era_ended_at_ticks` from `era_state_rows`.
- [x] 9.3 Add `update_character_tick_state()` to `oscilla/services/character.py` as specified in the design doc. Called by the pipeline after each adventure completion. Upserts tick counters, adventure state, and era state.

## 10. Tests — Unit Tests

- [x] 10.1 Create `tests/engine/test_ingame_time.py`. Add unit tests for `InGameTimeResolver`:
  - Root cycle label at tick 0 and wrap-around
  - Derived cycle position advancement
  - Epoch offset shifts display position
  - Always-active era count starts at `epoch_count` at tick 0 and increments per cycle
  - Conditioned era count starts at `epoch_count` on the activation tick, not tick 0
  - Era is inactive before `start_condition` fires
  - Era deactivates after `end_condition` fires (latch)
  - Alias resolves to root cycle
  - Parallel branches computed independently
  - Unit test for `update_era_states()`: verifies `era_started_at_ticks` is populated on first true evaluation and not re-evaluated thereafter
  - Unit test: era that has ended is never restarted even if `start_condition` would evaluate true again
- [x] 10.2 Create `tests/engine/test_conditions_ingame_time.py`. Add unit tests for all three new condition predicates:
  - `game_calendar_time_is` with each operator (`gt`, `gte`, `lt`, `lte`, `eq`, `mod`) for both clocks
  - `game_calendar_cycle_is` match and non-match cases
  - `game_calendar_era_is` active/inactive for conditioned and unconditioned eras
  - All three return False with warning when time system not configured
  - Composition via `all`, `any`, `not` nodes
- [x] 10.3 Create `tests/engine/test_adventure_ticks.py`. Add unit tests for tick advancement and repeat controls:
  - Both clocks advance by tick cost on completion
  - `adjust_game_ticks` positive and negative delta
  - `adjust_game_ticks` clamp at zero behavior
  - `adjust_game_ticks` allow-negative behavior
  - `adjust_game_ticks` does not affect `internal_ticks`
  - `cooldown_ticks` blocks replay and allows after cooldown
  - `cooldown_game_ticks` blocks replay and allows after cooldown
  - `cooldown_adventures` deprecated migration: mapped to `cooldown_ticks` with warning
- [x] 10.4 Add unit tests for `compute_epoch_offset` in the existing or a new test file:
  - Zero offset when no epoch declared
  - Named label offset computed correctly
  - 1-based integer index offset computed correctly
  - Multi-cycle compound epoch offset
- [x] 10.5 Add unit tests for `CharacterState` serialization/deserialization:
  - New keys `internal_ticks` and `game_ticks` round-trip correctly
  - Old key `adventure_last_completed_at_total` is accepted and mapped to new key
  - New key `adventure_last_completed_at_ticks` takes precedence over old key
- [x] 10.6 Add fixture directory `tests/fixtures/content/ingame-time/` with a minimal `game.yaml` containing a simple cycle DAG (root `hour` count 24, derived `season` count 4 with labels, one era). Add `conftest.py` fixture `registry_with_time` that loads this content.

## 11. Tests — Integration Tests

- [x] 11.1 Create `tests/engine/test_ingame_time_integration.py`. Add integration tests using the `tests/fixtures/content/ingame-time/` fixture:
  - Full pipeline run advances both clocks
  - `game_calendar_cycle_is` gate on adventure correctly allows/blocks
  - `game_calendar_era_is` gate correctly allows/blocks
  - `adjust_game_ticks` effect fires and updates `game_ticks` without touching `internal_ticks`
  - Cooldown check after pipeline run uses `adventure_last_completed_at_ticks`

## 12. Tests — Semantic Validator

- [x] 12.1 Add tests for cycle DAG validation errors:
  - Missing root cycle raises error
  - Two root cycles raises error
  - Circular parent reference raises error
  - Unknown parent name raises error
  - Duplicate cycle name raises error
  - Labels list length mismatch raises error
- [x] 12.2 Add tests for epoch validation errors:
  - Nonexistent cycle name in epoch raises error
  - Invalid label value in epoch raises error
  - Out-of-range integer in epoch raises error
- [x] 12.3 Add tests for era validation errors:
  - Unknown `tracks` cycle name raises error
  - Era `tracks` field referencing an undeclared cycle raises error
- [x] 12.4 Add tests for condition cross-reference validation:
  - `game_calendar_cycle_is` with unknown cycle name raises error
  - `game_calendar_cycle_is` with invalid label value raises error
  - `game_calendar_era_is` with unknown era name raises error

## 13. Documentation

- [x] 13.1 Create `docs/authors/ingame-time.md`. Include: introduction and when to use the time system; full `game.yaml time:` schema reference with annotated YAML examples; cycle DAG authoring guide with simple and branching examples; era definition guide with condition-gated and always-active examples; epoch configuration guide; per-adventure `ticks:` field; template reference (`ingame_time.internal_ticks`, `ingame_time.game_ticks`, `ingame_time.cycles["<name>"].label`, `ingame_time.eras["<name>"].count`, `ingame_time.eras["<name>"].active`); condition predicate reference for all three new types with examples; repeat control migration from `cooldown_adventures` to `cooldown_ticks`.
- [x] 13.2 Update `docs/authors/README.md` table of contents to add the new `ingame-time.md` entry.
- [x] 13.3 Update `docs/authors/game-configuration.md` to reference the new `time:` block and link to `ingame-time.md`.
- [x] 13.4 Update `docs/dev/game-engine.md` to add a "Dual Clock Model" section explaining `internal_ticks` vs `game_ticks`, reset behavior, tick advancement in the pipeline, and the `InGameTimeResolver` architecture.
- [x] 13.5 Update `docs/dev/database.md` to document the two new `character_iterations` columns.
- [x] 13.6 Update `docs/dev/README.md` if a new developer doc was added (no new dev doc is required, but review for accuracy).

## 14. Testlandia — Time Configuration

- [x] 14.1 Add a `time:` block to `content/testlandia/game.yaml` as specified in the design doc:
  - `ticks_per_adventure: 1`
  - `base_unit: hour`
  - `pre_epoch_behavior: clamp`
  - Root cycle `hour` with 24 labels (Dawn, Early Morning, …, Pre-Dawn)
  - Derived cycle `season` with parent `hour` count 4, labels `[Spring, Summer, Autumn, Winter]`
  - Derived cycle `lunar_cycle` with parent `hour` count 28, labels for 8 moon phases (cycling through)
  - Epoch: `{season: Spring}`
  - Era `testlandia_era`: format `"Year {count} of the Realm"`, `epoch_count: 1`, `tracks: season`
  - Era `moon_age`: format `"Moon Age {count}"`, `epoch_count: 1`, `tracks: lunar_cycle`, `start_condition: {type: game_calendar_time_is, clock: game, gte: 56}`

## 15. Testlandia — Test Adventures

- [x] 15.1 Create `content/testlandia/regions/test-region/test-time-display.yaml`: always-available adventure showing `{{ ingame_time.internal_ticks }}`, `{{ ingame_time.game_ticks }}`, `{{ ingame_time.cycles['season'].label }}`, and `{{ ingame_time.eras['testlandia_era'].count }}`. Acceptance: adventure is selectable at any tick and renders time values without errors.
- [x] 15.2 Create `content/testlandia/regions/test-region/test-time-advances.yaml`: adventure with `ticks: 10`. Step text displays `{{ ingame_time.game_ticks }}` before and after. Acceptance: both clocks advance by 10 on completion; template shows updated count.
- [x] 15.3 Create `content/testlandia/regions/test-region/test-wait-for-season.yaml`: adventure with `requires: {type: game_calendar_cycle_is, cycle: season, value: Summer}`. Acceptance: adventure is unavailable in Spring; available in Summer (after 4 completions of `test-time-advances` to advance 40 hours = Summer).
- [x] 15.4 Create `content/testlandia/regions/test-region/test-turn-back-the-clock.yaml`: adventure with `adjust_game_ticks: {delta: -10}` step effect. Text shows `game_ticks` before and after. Acceptance: `game_ticks` decreases by 10; `internal_ticks` unchanged; clamp at 0 prevents negative values.
- [x] 15.5 Create `content/testlandia/regions/test-region/test-new-era-unlocked.yaml`: adventure gated on `{type: game_calendar_era_is, era: moon_age, state: active}`. Acceptance: unavailable until `game_ticks >= 56`; available after.
- [x] 15.6 Create `content/testlandia/regions/test-region/test-count-the-days.yaml`: multi-step adventure. Step 1 text: `You have traveled {{ ingame_time.internal_ticks }} hours.` Step 2 gated on `{type: game_calendar_time_is, clock: internal, gte: 5}`. Acceptance: step 2 is reachable after at least 5 completions of any tick-advancing adventure.
