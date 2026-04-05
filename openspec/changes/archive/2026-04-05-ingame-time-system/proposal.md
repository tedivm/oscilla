## Why

Content authors building games with no real-world tie-in — dungeon crawlers, fantasy epics, historical simulators, space operas — have no way to express in-game time. The engine provides real-world calendar functions but has no concept of a game clock, in-game seasons, or narrative eras. This change adds an opt-in in-game time system that is fully author-defined, composable with the existing condition evaluator, and invisible to games that don't use it.

## What Changes

- **New `time:` block in `game.yaml`**: An optional configuration section that declares the game's time system, including a root tick unit, a directed acyclic graph of derived cycles (day, week, month, season, lunar cycle, etc.), named eras that track a cycle counter, an epoch (the named calendar position that corresponds to tick zero), and behavior controls.
- **Dual clock on `CharacterIterationRecord`**: Two new integer columns — `internal_ticks` (monotone, always increments, never directly adjusted, resets to zero on new iteration) and `game_ticks` (narrative clock, increments by default, can be adjusted by adventure effects, resets to zero on new iteration). At new iteration both reset to zero; the epoch configuration provides the display label for zero.
- **Adventure tick cost**: Adventures declare an optional `ticks` field that overrides the game-wide `ticks_per_adventure` default. Both clocks advance by the same tick cost on adventure completion.
- **New effect `adjust_game_ticks`**: Adjusts `game_ticks` by a signed integer delta. Subject to `pre_epoch_behavior` (clamp or allow). `internal_ticks` is never affected by effects.
- **Three new condition predicates**: `game_calendar_time_is` (numeric comparison on `internal_ticks` or `game_ticks`), `game_calendar_cycle_is` (tests the current named label of any cycle), `game_calendar_era_is` (tests whether a named era is active or inactive given current `game_ticks`).
- **Repeat control unification**: New `cooldown_ticks` (internal clock, default) and `cooldown_game_ticks` (game clock) fields on `AdventureSpec`. The existing `cooldown_adventures` field is deprecated and maps to `cooldown_ticks` with a load warning. `cooldown_days` (real-world calendar) is unchanged.
- **Template exposure**: `ingame_time` object in the template `ExpressionContext` exposing `internal_ticks`, `game_ticks`, current cycle label for every defined cycle, and an `eras` mapping of era name → current count and active status.

## Capabilities

### New Capabilities

- `ingame-time-system`: The in-game time system — dual clocks, cycle DAG, epoch configuration, era counters, and all associated game.yaml schema.
- `ingame-time-conditions`: The three new condition predicates (`game_calendar_time_is`, `game_calendar_cycle_is`, `game_calendar_era_is`).
- `ingame-time-effects`: The `adjust_game_ticks` effect.
- `ingame-time-templates`: The `ingame_time` object in the template expression context.

### Modified Capabilities

- `condition-evaluator`: Three new leaf predicate types added to the `Condition` union.
- `adventure-repeat-controls`: New `cooldown_ticks` and `cooldown_game_ticks` fields; `cooldown_adventures` deprecated.
- `dynamic-content-templates`: New `ingame_time` object in `ExpressionContext`.

## Impact

- **`oscilla/engine/models/time.py`**: New `GameTimeSpec`, `RootCycleSpec`, `DerivedCycleSpec`, `CycleSpec` (discriminated union), and `EraSpec` Pydantic models. Epoch is a plain `dict[str, int | str]` field on `GameTimeSpec` — no separate `EpochSpec` class.
- **`oscilla/engine/models/game.py`**: `GameSpec` gains optional `time: GameTimeSpec | None` import and field.
- **`oscilla/engine/models/adventure.py`**: New `ticks` field on `AdventureSpec`; new `cooldown_ticks` and `cooldown_game_ticks` fields; `cooldown_adventures` deprecated.
- **`oscilla/engine/models/base.py`**: Three new condition model classes (`GameCalendarTimeCondition`, `GameCalendarCycleCondition`, `GameCalendarEraCondition`) added to the `Condition` union.
- **`oscilla/engine/models/adventure.py`**: New `AdjustGameTicksEffect` model added to the `Effect` union.
- **`oscilla/engine/character.py`**: `CharacterState` gains `internal_ticks: int`, `game_ticks: int`, `era_started_at_ticks: Dict[str, int]`, and `era_ended_at_ticks: Dict[str, int]`; `adventure_last_completed_at_total` renamed to `adventure_last_completed_at_ticks`; `is_adventure_eligible` updated; serialization/deserialization updated (backward-compatible: old key `adventure_last_completed_at_total` accepted on load).
- **`oscilla/models/character_iteration.py`**: Two new `BigInteger` columns (`internal_ticks`, `game_ticks`) on `CharacterIterationRecord` plus an `era_state_rows` relationship; `last_completed_at_total` renamed to `last_completed_at_ticks` and widened to `BigInteger` on `CharacterIterationAdventureState`; new `CharacterIterationEraState` child table with `(iteration_id, era_name)` composite PK and nullable `started_at_game_ticks` / `ended_at_game_ticks` BigInteger columns.
- **`oscilla/services/character.py`**: `save_character()` and `load_character()` updated for renamed column and era state rows; new `update_character_tick_state()` function called by the pipeline after each adventure to upsert tick counters, adventure cooldown state, and era latch state.
- **`db/versions/`**: New Alembic migration (`add ingame time tables`) covering all four database changes: two new columns on `character_iterations`, column rename + widening on `character_iteration_adventure_state`, and new `character_iteration_era_state` table.
- **`oscilla/engine/conditions.py`**: Three new `case` branches in the `evaluate()` match block.
- **`oscilla/engine/ingame_time.py`**: New module containing `InGameTimeResolver`, `InGameTimeView`, `CycleState`, `EraState`, and `update_era_states()`: reads `GameTimeSpec` from registry, computes cycle positions and era latch states from tick values.
- **`oscilla/engine/pipeline.py`**: Adventure completion advances both clocks; `adjust_game_ticks` effect handler added.
- **`oscilla/engine/templates.py`**: `ExpressionContext` gains `ingame_time`; populated only when `time:` is configured.
- **`oscilla/engine/semantic_validator.py`**: Validation for cycle DAG (one root, no cycles, parent references, label count matching count, epoch values in range, era `tracks` references, condition references to declared cycle/era names).
- **`oscilla/engine/loader.py`**: Epoch offset pre-computed at load time and attached to registry for use by resolvers.
- **`docs/authors/ingame-time.md`**: New author guide.
- **`docs/dev/game-engine.md`**: Updated to document the dual-clock model.
- **`content/testlandia/`**: New adventures, regions, or steps exercising the in-game time system for manual QA.
- **No new Python dependencies.**
- **One database migration required** covering four changes: two new columns on `character_iterations`, a column rename and type widening on `character_iteration_adventure_state`, and the new `character_iteration_era_state` table. All changes are backward compatible (new columns default to 0 or null; renamed column uses a compatible widening cast).

## Testlandia Updates

The testlandia content package must be updated to demonstrate and manually QA the new feature:

- **Time configuration in `content/testlandia/game.yaml`**: Add a `time:` block with a multi-branch cycle DAG (`tick → hour → day → season → solar_year` and `tick → day → lunar_cycle → lunar_year`), two eras (a primary era tracking `solar_year` and a secondary era tracking `lunar_year` with a condition gate), a named epoch, and `ticks_per_adventure: 1`.
- **Adventure: "Wait for the Season"** (`content/testlandia/regions/<region>/test-wait-for-season.yaml`): An adventure gated on `game_calendar_cycle_is: season: Summer` that can only be started in summer. Completing it rewards XP. Used to verify cycle-based condition gating.
- **Adventure: "Time Marches On"** (`content/testlandia/regions/<region>/test-time-marches-on.yaml`): An adventure with `ticks: 10` that advances the clock by 10 in a single run, demonstrating multi-tick adventures and testing that `internal_ticks` and `game_ticks` both advance correctly.
- **Adventure: "Turn Back the Clock"** (`content/testlandia/regions/<region>/test-turn-back-the-clock.yaml`): An adventure that applies an `adjust_game_ticks` effect with a negative delta, demonstrating game clock manipulation while `internal_ticks` remains unaffected.
- **Adventure: "The New Era Begins"** (`content/testlandia/regions/<region>/test-new-era.yaml`): An adventure gated on `game_calendar_era_is: secondary_era: active`, only available once sufficient game ticks have elapsed to activate the secondary era.
- **Adventure: "Count the Days"** (`content/testlandia/regions/<region>/test-count-the-days.yaml`): An adventure using `game_calendar_time_is` with both `clock: internal` and `clock: game` comparisons to gate on tick count thresholds.
- **Template display**: At least one adventure step in each test adventure must display the current value of `ingame_time.game_ticks`, cycle labels (e.g., current season), and active era counts via template expressions, so a manual tester can see the time state at a glance.
