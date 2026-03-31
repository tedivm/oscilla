## Why

The character stat system currently admits a `float` type that no production content uses and that introduces precision loss when stored in a `REAL` column (integers above 2^53 lose exact representation). The system also has no bounds enforcement — malformed or malicious content can set any stat to an arbitrary integer value, silently corrupting game state. Both issues share the same root cause (loose numeric semantics) and are cleanest to fix together.

## What Changes

- **BREAKING**: Remove `float` from `StatType`. The valid types become `Literal["int", "bool"]`. Content packages with `type: float` stats must change them to `type: int`.
- Add `StatBounds` model with `min: int | None` and `max: int | None` fields.
- Add `bounds: StatBounds | None` to `StatDefinition`. Setting `bounds` on a `bool` stat is a content load error.
- When `bounds` is absent (or a bound is `None`), default to the PostgreSQL `Integer` range: min = −2,147,483,648, max = 2,147,483,647.
- Change the `character_iteration_stat_values.stat_value` DB column from `Float` (REAL) to `Integer`. A migration converts existing values with `ROUND()`.
- Enforce bounds at effect application time in `effects.py`: clamp the result, log a warning, and notify the player via the TUI.
- Add a hard INT32 floor/ceiling check in `CharacterState` as a backstop that applies regardless of how stats are mutated.
- Remove all float-specific branches from the content loader, effect handlers, and character serialization.
- Update testlandia content: change the `speed` stat from `type: float` to `type: int` and update its bump-speed adventures to use integer amounts.

## Capabilities

### New Capabilities

- `stat-bounds`: Per-stat optional bounds defined in `CharacterConfig`. Covers the `StatBounds` model, its YAML syntax, validation rules, loader enforcement, and runtime clamp/log/notify behavior.

### Modified Capabilities

- `stat-mutation-effects`: The `float` stat type is removed; `stat_change` and `stat_set` now only target `int` or `bool` stats. When a delta or set would violate a stat's bounds, the value is clamped, logged, and the player is notified rather than applied unchecked.
- `player-state`: The `stats` dict type narrows from `int | float | bool | None` to `int | bool | None`. The `CharacterState` model gains a stat-setting method that enforces hard INT32 floor/ceiling as a backstop.
- `manifest-system`: `StatDefinition` gains an optional `bounds` field. `float` is removed from `StatType`. `StatBounds` on a `bool` stat is a load-time validation error.

## Impact

- `oscilla/engine/models/character_config.py` — new `StatBounds` model; `StatType`, `StatDefinition` updated
- `oscilla/engine/models/adventure.py` — `StatChangeEffect.amount` and `StatSetEffect.value` types narrowed (no float)
- `oscilla/engine/character.py` — `stats` dict type annotation narrowed; new `set_stat()` method with INT32 backstop
- `oscilla/engine/steps/effects.py` — bounds clamping with log + TUI notification on `stat_change` and `stat_set`
- `oscilla/engine/loader.py` — remove float validation branches; add bounds-on-bool load error
- `oscilla/engine/conditions.py` — numeric comparisons still work, float isinstance checks removed
- `oscilla/models/character_iteration.py` — `stat_value` column changed from `Float` to `Integer`
- `oscilla/services/character.py` — `_stat_to_float()` replaced by `_stat_to_int()`
- `db/versions/` — new Alembic migration for the column type change
- `content/testlandia/` — `speed` stat type and bump-speed adventure amounts updated
- `tests/engine/test_stat_effects.py` — float stat tests updated or replaced
