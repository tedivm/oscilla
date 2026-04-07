## MODIFIED Requirements

### Requirement: prestige_character() transitions to a new iteration

`prestige_character(session, character_id, character_config, game_manifest=None)` in `oscilla/services/character.py` SHALL:

1. Load the active iteration row via `WHERE character_id = X AND is_active = TRUE`.
2. Set `is_active = FALSE, completed_at = now()` on that row.
3. Count existing `character_iterations` rows for the character to derive the next `iteration` ordinal.
4. Derive `base_hp` from `game_manifest.spec.hp_formula.base_hp` when `game_manifest` is provided; fall back to 10 when it is `None`.
5. Insert a new `character_iterations` row with `iteration = count`, `is_active = TRUE`, `completed_at = NULL`, and scalar fields seeded from config defaults and `base_hp`.
6. Insert child rows (`character_iteration_stat_values`) seeded from `character_config` stat defaults.
7. Flush but NOT commit; the calling session layer owns the transaction.
8. Return the new `CharacterIterationRecord`.

The carry-forward (copying specific stat values and skill memberships from the old iteration to the new one) is applied entirely in-memory by the `PrestigeEffect` handler before `prestige_character()` is called. `prestige_character()` seeds only bare defaults; the `_persist_diff` path that follows in the same transaction writes the fully-resolved (carry-applied) state on top.

#### Scenario: Prestige preserves history and seeds new defaults

- **WHEN** `prestige_character()` is called on a character that is currently on iteration 0
- **THEN** the original `character_iterations` row has `is_active = FALSE` and a non-null `completed_at`, and the new `character_iterations` row has `iteration = 1`, `is_active = TRUE`, and `completed_at = NULL`

#### Scenario: base_hp comes from game_manifest when provided

- **WHEN** `prestige_character()` is called with a `game_manifest` whose `hp_formula.base_hp = 25`
- **THEN** the new iteration row is inserted with `hp = 25` and `max_hp = 25`

#### Scenario: base_hp falls back when game_manifest is absent

- **WHEN** `prestige_character()` is called with `game_manifest=None`
- **THEN** the new iteration row is inserted with `hp = 10` and `max_hp = 10`

## ADDED Requirements

### Requirement: \_persist_diff handles prestige_pending at adventure_end

When `_persist_diff(state, event="adventure_end")` is called and `state.prestige_pending is not None`, the session layer SHALL perform the prestige iteration transition before writing the updated state:

1. Call `prestige_character(session, character_id, character_config, game_manifest)` to close the old iteration and open a new one.
2. Update `self._iteration_id` to the newly created iteration's `id`.
3. Set `self._last_saved_state = None` to force a full diff against the empty new row.
4. Clear `state.prestige_pending = None`.
5. Continue with the normal `adventure_end` diff, which writes the fully-resolved reset state to the new iteration row.

#### Scenario: Prestige transition happens before state is written

- **WHEN** `_persist_diff` is called with `event="adventure_end"` and `prestige_pending` is set
- **THEN** the old iteration row is closed before any state is written, and all state writes go to the new iteration row

#### Scenario: adventure_end commit covers both transition and state write

- **WHEN** the prestige transition and state write happen in the same `_persist_diff` call
- **THEN** both the `prestige_character()` flush and the state diff writes are committed atomically in the `adventure_end` transaction

### Requirement: \_persist_diff skips checkpoints during prestige_pending

When `state.prestige_pending is not None` and `event` is `"step_start"` or `"combat_round"`, `_persist_diff` SHALL return immediately without writing anything. This prevents the in-memory reset state from being written to the old iteration row before the `adventure_end` transition is finalized.

#### Scenario: step_start persist is skipped while prestige pending

- **WHEN** `_persist_diff(state, event="step_start")` is called while `state.prestige_pending is not None`
- **THEN** no database writes are performed and the function returns without error

#### Scenario: adventure_end persist is NOT skipped when prestige pending

- **WHEN** `_persist_diff(state, event="adventure_end")` is called while `state.prestige_pending is not None`
- **THEN** the prestige transition proceeds and state is written to the new iteration row
