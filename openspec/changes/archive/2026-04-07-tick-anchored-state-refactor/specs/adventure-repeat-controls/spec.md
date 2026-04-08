## MODIFIED Requirements

### Requirement: Adventures can declare a tick-based cooldown using internal_ticks

An `AdventureSpec` MAY declare a nested `cooldown: {ticks: int | str}` to enforce a minimum `internal_ticks` elapsed since last completion. The value SHALL be a positive integer or a Jinja2 template string that resolves to a positive integer. All cooldown fields are nested under a single `cooldown:` object (see unified-cooldown-schema spec).

`internal_ticks` is the monotone clock — time-manipulation effects cannot bypass this cooldown.

If the adventure has never been completed, no cooldown applies.

#### Scenario: Adventure on tick cooldown is hidden

- **WHEN** an adventure has `cooldown: {ticks: 10}`, `internal_ticks` at last completion was 5, and current `internal_ticks` is 12
- **THEN** the adventure does not appear in the eligible pool (12 − 5 = 7 < 10)

#### Scenario: Adventure is available after enough ticks pass

- **WHEN** an adventure has `cooldown: {ticks: 10}`, `internal_ticks` at last completion was 5, and current `internal_ticks` is 15
- **THEN** the adventure is eligible (15 − 5 = 10 >= 10)

#### Scenario: Never-completed adventure has no cooldown

- **WHEN** an adventure has `cooldown: {ticks: 100}` and has never been completed this iteration
- **THEN** the adventure is eligible regardless of current tick values

---

### Requirement: Adventures can declare a game-clock cooldown using game_ticks

An `AdventureSpec` MAY declare a nested `cooldown: {game_ticks: int | str}` to enforce a minimum `game_ticks` elapsed since last completion. The value SHALL be a positive integer or a Jinja2 template string. Note that `adjust_game_ticks` effects CAN affect this cooldown.

#### Scenario: Adventure on game-tick cooldown is hidden

- **WHEN** an adventure has `cooldown: {game_ticks: 20}`, `game_ticks` at last completion was 10, and current `game_ticks` is 25
- **THEN** the adventure does not appear in the eligible pool (25 − 10 = 15 < 20)

#### Scenario: Time-travel effect can affect game-tick cooldown

- **WHEN** `adjust_game_ticks: {delta: -50}` fires after completing an adventure with `cooldown: {game_ticks: 30}`
- **THEN** the cooldown window may be affected because `game_ticks` decreased

---

### Requirement: Adventures can declare a real-world seconds cooldown

An `AdventureSpec` MAY declare a nested `cooldown: {seconds: int | str}` to enforce a minimum real-world time elapsed since last completion. The value SHALL be a positive integer of seconds or a template string resolving to one. The template constants `SECONDS_PER_MINUTE`, `SECONDS_PER_HOUR`, `SECONDS_PER_DAY`, and `SECONDS_PER_WEEK` may be used in template expressions.

The timestamp of last completion SHALL be stored as a Unix timestamp integer in `adventure_last_completed_real_ts`.

#### Scenario: Adventure on seconds cooldown is hidden

- **WHEN** an adventure has `cooldown: {seconds: 3600}` and was last completed 1800 seconds ago
- **THEN** the adventure does not appear in the eligible pool

#### Scenario: Adventure is available after seconds cooldown expires

- **WHEN** an adventure has `cooldown: {seconds: 3600}` and was last completed 3600 seconds ago
- **THEN** the adventure is eligible

#### Scenario: Template constant in seconds cooldown

- **WHEN** an adventure has `cooldown: {seconds: "{{ SECONDS_PER_DAY }}"}` and was last completed 86401 seconds ago
- **THEN** the adventure is eligible

#### Scenario: Never-completed adventure has no cooldown

- **WHEN** an adventure has `cooldown: {seconds: 3600}` and has never been completed
- **THEN** the adventure is eligible

---

### Requirement: Multiple cooldown constraints are AND-ed

When a `Cooldown` object specifies more than one constraint field (e.g., `ticks` and `seconds`), ALL constraints SHALL pass for the adventure to be eligible.

#### Scenario: All constraints must pass

- **WHEN** an adventure has `cooldown: {ticks: 5, seconds: 3600}` and 6 ticks have elapsed but only 1800 seconds
- **THEN** the adventure is not eligible (seconds constraint fails)

#### Scenario: Both constraints satisfied

- **WHEN** an adventure has `cooldown: {ticks: 5, seconds: 3600}` and 6 ticks and 3601 seconds have both elapsed
- **THEN** the adventure is eligible

---

### Requirement: Repeat state persists across sessions

`adventure_last_completed_real_ts`, `adventure_last_completed_at_ticks`, and `adventure_last_completed_game_ticks` SHALL be persisted to the database in the character iteration state and restored on character load.

Deserialization SHALL accept the old key `adventure_last_completed_at_total` for backward compatibility with very old sessions, preferring the new key `adventure_last_completed_at_ticks` when present.

Deserialization SHALL detect and migrate `__game__` prefixed keys from `adventure_last_completed_at_ticks` into `adventure_last_completed_game_ticks`.

#### Scenario: Tick cooldown survives session restart

- **WHEN** a player completes an adventure with `cooldown: {ticks: 10}` and ends the session
- **THEN** on next session start, `adventure_last_completed_at_ticks` is restored
- **THEN** the adventure is still unavailable if fewer than 10 `internal_ticks` have elapsed

#### Scenario: Seconds cooldown survives session restart

- **WHEN** a player completes an adventure with `cooldown: {seconds: 3600}` and ends the session
- **THEN** on next session start, `adventure_last_completed_real_ts` is restored as a Unix timestamp
- **THEN** the adventure is still unavailable if fewer than 3600 seconds have elapsed since completion

---

## REMOVED Requirements

### Requirement: Adventures can declare a calendar-day cooldown

**Reason:** Day-precision is an arbitrary and inconsistent constraint. Real-world time cooldowns now use `cooldown: {seconds: N}` which supports any granularity. Template constants (`SECONDS_PER_DAY`) are available to replicate the "N days" pattern with full sub-day flexibility.

**Migration:** `cooldown_days: N` → `cooldown: {seconds: "{{ SECONDS_PER_DAY * N }}"}`.

### Requirement: Adventures can declare an adventure-count cooldown (deprecated field)

**Reason:** The `cooldown_adventures` → `cooldown_ticks` auto-migration bridged the original deprecated field. With the switch to nested `cooldown:` schema, the deprecated flat-field auto-migration is no longer needed.

**Migration:** Remove any `cooldown_adventures` fields; use `cooldown: {ticks: N}` directly.

### Requirement: Flat cooldown fields cooldown_days, cooldown_ticks, cooldown_game_ticks

**Reason:** Replaced by a single nested `cooldown:` object (see unified-cooldown-schema spec) that provides a consistent schema shared with skills and supports template expressions.

**Migration:** Replace flat fields with equivalent nested syntax:

- `cooldown_ticks: N` → `cooldown: {ticks: N}`
- `cooldown_game_ticks: N` → `cooldown: {game_ticks: N}`
- `cooldown_days: N` → `cooldown: {seconds: "{{ SECONDS_PER_DAY * N }}"}`
