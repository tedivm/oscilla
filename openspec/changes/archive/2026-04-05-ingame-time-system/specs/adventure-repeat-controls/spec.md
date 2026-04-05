## ADDED Requirements

### Requirement: Adventures can declare a tick-based cooldown using internal_ticks

An `AdventureSpec` MAY declare `cooldown_ticks: int` (positive integer). When set, the adventure SHALL be excluded from the eligible pool until at least `cooldown_ticks` of `internal_ticks` have elapsed since the adventure was last completed. The `internal_ticks` value at last completion is stored in `CharacterState.adventure_last_completed_at_ticks`. If the adventure has never been completed, no cooldown applies.

`cooldown_ticks` uses `internal_ticks` (the monotone clock) so time-manipulation effects cannot bypass the cooldown.

#### Scenario: Adventure on tick cooldown is hidden

- **WHEN** an adventure has `cooldown_ticks: 10`, `internal_ticks` at last completion was 5, and current `internal_ticks` is 12
- **THEN** the adventure does not appear in the eligible pool (12 − 5 = 7 < 10)

#### Scenario: Adventure is available after enough ticks pass

- **WHEN** an adventure has `cooldown_ticks: 10`, `internal_ticks` at last completion was 5, and current `internal_ticks` is 15
- **THEN** the adventure is eligible (15 − 5 = 10 >= 10)

#### Scenario: Never-completed adventure has no cooldown

- **WHEN** an adventure has `cooldown_ticks: 100` and has never been completed this iteration
- **THEN** the adventure is eligible regardless of current tick values

---

### Requirement: Adventures can declare a game-clock cooldown using game_ticks

An `AdventureSpec` MAY declare `cooldown_game_ticks: int` (positive integer). When set, the adventure SHALL be excluded from the eligible pool until at least `cooldown_game_ticks` of `game_ticks` have elapsed since the adventure was last completed. Uses `game_ticks` (the narrative clock); note that `adjust_game_ticks` effects CAN affect this cooldown.

#### Scenario: Adventure on game-tick cooldown is hidden

- **WHEN** an adventure has `cooldown_game_ticks: 20`, `game_ticks` at last completion was 10, and current `game_ticks` is 25
- **THEN** the adventure does not appear in the eligible pool (25 − 10 = 15 < 20)

#### Scenario: Time-travel effect can affect game-tick cooldown

- **WHEN** `adjust_game_ticks: {delta: -50}` fires after completing an adventure with `cooldown_game_ticks: 30`
- **THEN** the cooldown window may be affected because `game_ticks` decreased

---

## MODIFIED Requirements

### Requirement: Adventures can declare an adventure-count cooldown

An `AdventureSpec` MAY declare `cooldown_adventures: int` (positive integer). **This field is deprecated.** At content load time, if `cooldown_adventures` is set, the engine SHALL emit a load warning and copy its value to `cooldown_ticks` (if `cooldown_ticks` is not already set). The `cooldown_adventures` field SHALL still be accepted by the manifest parser to allow existing content to continue functioning during migration.

The load warning SHALL identify the adventure by name and state: `"Adventure uses deprecated 'cooldown_adventures' — use 'cooldown_ticks' instead."`.

#### Scenario: cooldown_adventures is accepted and mapped to cooldown_ticks

- **WHEN** an adventure declares `cooldown_adventures: 5`
- **THEN** the content loader maps it to `cooldown_ticks: 5`
- **THEN** a load warning is emitted

#### Scenario: cooldown_adventures does not override explicit cooldown_ticks

- **WHEN** an adventure declares both `cooldown_adventures: 5` and `cooldown_ticks: 10`
- **THEN** `cooldown_ticks` retains the value 10
- **THEN** a load warning is still emitted for `cooldown_adventures`

---

## MODIFIED Requirements

### Requirement: Repeat state persists across sessions

`adventure_last_completed_on` and `adventure_last_completed_at_ticks` SHALL be persisted to the database in the character iteration state and restored on character load. The field `adventure_last_completed_at_ticks` replaces the previously specified `adventure_last_completed_at_total` (which tracked total adventure completion count). The deserialization layer SHALL accept both the old key name `adventure_last_completed_at_total` (for backward compatibility with existing sessions) and the new key `adventure_last_completed_at_ticks`, preferring the new key when both are present.

#### Scenario: Tick cooldown survives session restart

- **WHEN** a player completes an adventure with `cooldown_ticks: 10` and ends the session
- **THEN** on next session start, `adventure_last_completed_at_ticks` is restored
- **THEN** the adventure is still unavailable if fewer than 10 `internal_ticks` have elapsed since the restart

#### Scenario: Old adventure_last_completed_at_total key is accepted on load

- **WHEN** a serialized character state contains `adventure_last_completed_at_total: {my-adventure: 42}`
- **THEN** `adventure_last_completed_at_ticks` is populated with `{my-adventure: 42}` after deserialization
