# Buff Persistence

## Purpose

Specifies how buffs with time-based duration fields survive combat end, carry their remaining-turns count across encounters within an adventure, and persist across adventures until a tick/second expiry is met.

## Requirements

### Requirement: BuffDuration replaces duration_turns on BuffSpec

`BuffSpec` SHALL declare `duration: BuffDuration` instead of `duration_turns: int`. `BuffDuration` is a Pydantic `BaseModel` with the following fields:

| Field        | Type                 | Default  | Description                                                                            |
| ------------ | -------------------- | -------- | -------------------------------------------------------------------------------------- |
| `turns`      | `int \| str`         | required | Number of combat turns the buff fires per encounter. Template strings accepted (ge=1). |
| `ticks`      | `int \| str \| None` | `None`   | `internal_ticks` elapsed since application before expiry.                              |
| `game_ticks` | `int \| str \| None` | `None`   | `game_ticks` elapsed since application before expiry.                                  |
| `seconds`    | `int \| str \| None` | `None`   | Real-world seconds since application before expiry.                                    |

A `BuffDuration` with none of `ticks`, `game_ticks`, or `seconds` set is **encounter-scoped**: the buff is discarded when combat ends (current default behavior). A `BuffDuration` with at least one time-based field set is **persistent**: the buff is stored on the player and re-entered into subsequent combats. Multiple non-None fields are AND-ed — all expiry conditions must be satisfied before the buff is removed.

#### Scenario: Encounter-scoped buff discarded at combat end

- **WHEN** a buff has `duration: {turns: 3}` with no time-based fields
- **AND** combat ends while the buff still has remaining turns
- **THEN** the buff is not present in `CharacterState.active_buffs`

#### Scenario: Persistent buff stored when combat ends with turns remaining

- **WHEN** a buff has `duration: {turns: 5, ticks: 2}` applied to the player at `internal_ticks == 10`
- **AND** the buff fires twice (2 turns consumed) before combat ends
- **THEN** a `StoredBuff` entry with `buff_ref`, `remaining_turns == 3`, `tick_expiry == 12` is present in `CharacterState.active_buffs`

#### Scenario: Persistent buff with no remaining turns is not stored

- **WHEN** a persistent buff's `remaining_turns` reaches 0 during combat
- **THEN** no entry is written to `CharacterState.active_buffs` for that buff

#### Scenario: Template string in turns resolves at load time

- **WHEN** a buff declares `duration: {turns: "{{ 2 + 1 }}", ticks: 3}`
- **THEN** the manifest loads without error and the resolved `turns` value is 3

---

### Requirement: StoredBuff tracks persistent buff state between combats

`CharacterState` SHALL include `active_buffs: List[StoredBuff]` (default `[]`). `StoredBuff` is a Pydantic `BaseModel`:

| Field              | Type             | Description                                         |
| ------------------ | ---------------- | --------------------------------------------------- |
| `buff_ref`         | `str`            | Buff manifest name                                  |
| `remaining_turns`  | `int`            | Turns remaining as of last combat-exit writeback    |
| `variables`        | `Dict[str, int]` | Merged resolved variables from original application |
| `tick_expiry`      | `int \| None`    | `internal_ticks` value at which this buff expires   |
| `game_tick_expiry` | `int \| None`    | `game_ticks` value at which this buff expires       |
| `real_ts_expiry`   | `int \| None`    | Unix timestamp at which this buff expires           |

`CharacterState.to_dict()` SHALL serialize `active_buffs` as a list of dicts under the `active_buffs` key. `from_dict()` SHALL restore them with `StoredBuff.model_validate()`; when the key is absent, `active_buffs` defaults to `[]` (backward compatibility).

#### Scenario: active_buffs survives serialization roundtrip

- **WHEN** a `CharacterState` with one `StoredBuff` entry is serialized via `to_dict()` and restored via `from_dict()`
- **THEN** `active_buffs` contains the same `StoredBuff` with all fields intact

#### Scenario: Missing active_buffs key defaults to empty

- **WHEN** a saved-game dict lacks the `active_buffs` key
- **THEN** `from_dict()` sets `active_buffs = []` without error

---

### Requirement: Persistent buffs are injected into combat at run_combat() entry

At the start of each `run_combat()` call, after constructing `CombatContext` and before applying item and skill buffs, the engine SHALL:

1. Call `player.sweep_expired_buffs(now_tick, now_game_tick, now_ts)` to remove any `StoredBuff` whose expiry conditions are met.
2. For each remaining `StoredBuff` in `player.active_buffs`, look up the buff manifest by `buff_ref`. If not found, log a WARNING and skip.
3. Construct an `ActiveCombatEffect` from the manifest spec with `remaining_turns` set to `StoredBuff.remaining_turns` and `is_persistent=True`. Append to `CombatContext.active_effects`.

Persistent buffs are injected before item and skill buffs so that exclusion-group blocking applies correctly.

#### Scenario: Stored buff re-enters second combat within adventure

- **WHEN** a buff with `duration: {turns: 5, ticks: 2}` was stored with `remaining_turns == 3` after combat 1
- **AND** a second combat begins before the buff expires
- **THEN** an `ActiveCombatEffect` with `remaining_turns == 3` and `is_persistent=True` is present in `CombatContext.active_effects`

#### Scenario: Expired buff not injected at combat start

- **WHEN** the player's `internal_ticks` has reached `tick_expiry` of a stored buff
- **THEN** `sweep_expired_buffs` removes it before injection
- **THEN** the buff is absent from `CombatContext.active_effects`

#### Scenario: Unknown buff_ref in active_buffs is skipped with warning

- **WHEN** a `StoredBuff` references a buff that no longer exists in the registry
- **THEN** a WARNING is logged and the stored buff is skipped (no crash)

---

### Requirement: Persistent buffs are written back to CharacterState after combat

After combat ends (win, defeat, or flee), the engine SHALL:

1. For each `ActiveCombatEffect` with `is_persistent=True` and `remaining_turns > 0`: update the corresponding `StoredBuff` in `player.active_buffs` with the new `remaining_turns`.
2. Remove any `StoredBuff` entries whose `buff_ref` matches a persistent effect that reached `remaining_turns == 0` during combat.
3. Encounter-scoped effects (`is_persistent=False`) are discarded without writeback.

#### Scenario: Remaining turns written back after partial consumption

- **WHEN** a persistent buff enters combat with `remaining_turns == 4` and fires twice (2 turns) before combat ends
- **THEN** `CharacterState.active_buffs` contains the buff with `remaining_turns == 2`

#### Scenario: Buff fully consumed in combat is removed from active_buffs

- **WHEN** a persistent buff enters combat with `remaining_turns == 2` and both turns fire before combat ends
- **THEN** no entry for that buff remains in `CharacterState.active_buffs`

---

### Requirement: sweep_expired_buffs removes expired StoredBuff entries

`CharacterState` SHALL provide `sweep_expired_buffs(now_tick: int, now_game_tick: int, now_ts: int) -> None`. The method SHALL remove any `StoredBuff` entry where:

- `tick_expiry` is not None AND `now_tick >= tick_expiry`, **OR**
- `game_tick_expiry` is not None AND `now_game_tick >= game_tick_expiry`, **OR**
- `real_ts_expiry` is not None AND `now_ts >= real_ts_expiry`.

(Any single expiry condition being met is sufficient to remove the entry; only one condition must trigger.)

This method is called at two points: `run_combat()` entry and adventure completion (in the pipeline after `internal_ticks` is incremented).

#### Scenario: Tick expiry removes buff

- **WHEN** a `StoredBuff` has `tick_expiry == 15` and `now_tick == 15`
- **THEN** `sweep_expired_buffs` removes that entry

#### Scenario: Not-yet-expired buff is retained

- **WHEN** a `StoredBuff` has `tick_expiry == 15` and `now_tick == 14`
- **THEN** `sweep_expired_buffs` retains the entry

#### Scenario: Buff with only seconds expiry expires on wall-clock

- **WHEN** a `StoredBuff` has `real_ts_expiry == 1000` and `now_ts == 1001`
- **THEN** `sweep_expired_buffs` removes it

---

### Requirement: Persistent buff state is persisted to the database

The database schema SHALL include `character_iteration_active_buffs` table with composite PK `(iteration_id, buff_ref)`:

| Column             | Type | Notes                                |
| ------------------ | ---- | ------------------------------------ |
| `iteration_id`     | UUID | FK → `character_iterations.id`       |
| `buff_ref`         | TEXT | Buff manifest name                   |
| `remaining_turns`  | INT  | Current remaining turns              |
| `variables_json`   | TEXT | JSON-encoded `Dict[str, int]`        |
| `tick_expiry`      | INT  | Nullable; `internal_ticks` at expiry |
| `game_tick_expiry` | INT  | Nullable; `game_ticks` at expiry     |
| `real_ts_expiry`   | INT  | Nullable; Unix timestamp at expiry   |

`save_character()` SHALL delete existing `character_iteration_active_buffs` rows for the iteration and re-insert from `CharacterState.active_buffs`. `load_character()` SHALL populate `active_buffs` from the table rows.

#### Scenario: Active buff survives session restart

- **WHEN** a player has a persistent buff in `active_buffs`, saves, and reloads
- **THEN** the buff is present in `active_buffs` after load with the same field values

#### Scenario: No active buff rows returns empty list

- **WHEN** a character has no rows in `character_iteration_active_buffs`
- **THEN** `active_buffs == []` after load

---

### Requirement: DispelEffect supports permanent removal of persistent buffs

`DispelEffect` SHALL accept an optional `permanent: bool = False` field. When `permanent == False` (default), the dispel removes matching entries only from `CombatContext.active_effects` — existing behavior unchanged. When `permanent == True`, the dispel additionally removes any matching `StoredBuff` entries from `CharacterState.active_buffs` (matched by `buff_ref == label and ae.target == target`) so the buff does not re-enter future combats.

Outside of combat (`combat == None`), the effect logs DEBUG and returns — no change.

#### Scenario: Default dispel does not clear stored buff

- **WHEN** a persistent buff is active in combat and a `dispel` effect fires with `permanent: false`
- **THEN** the `ActiveCombatEffect` is removed from `CombatContext.active_effects`
- **THEN** the corresponding `StoredBuff` remains in `CharacterState.active_buffs`
- **THEN** the buff re-enters the next combat

#### Scenario: Permanent dispel clears stored buff

- **WHEN** a persistent buff is active and a `dispel` effect fires with `permanent: true`
- **THEN** the `ActiveCombatEffect` is removed from `CombatContext.active_effects`
- **THEN** the corresponding `StoredBuff` is removed from `CharacterState.active_buffs`
- **THEN** the buff does not re-enter the next combat
