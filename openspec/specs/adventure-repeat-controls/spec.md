# Adventure Repeat Controls

## Purpose

Defines the mechanisms by which adventure authors can control how often a player is allowed to run a given adventure, including non-repeatability, completion caps, calendar-day cooldowns, and adventure-count cooldowns.

## Requirements

### Requirement: Adventures can be marked non-repeatable

An `AdventureSpec` MAY declare `repeatable: false`. When set, the adventure SHALL be excluded from the location's eligible pool if the player has completed it one or more times in the current character iteration. Completion count is sourced from `CharacterStatistics.adventures_completed`. After prestige, the iteration resets and the adventure becomes available again.

#### Scenario: Non-repeatable adventure is hidden after first completion

- **WHEN** an adventure has `repeatable: false` and the player has completed it once this iteration
- **THEN** the adventure does not appear in the eligible pool at that location

#### Scenario: Non-repeatable adventure is available on a fresh iteration

- **WHEN** an adventure has `repeatable: false` and the player's `adventures_completed[ref]` is 0 for the current iteration
- **THEN** the adventure is eligible for selection (subject to its `requires` condition)

---

### Requirement: Adventures can cap total completions per iteration

An `AdventureSpec` MAY declare `max_completions: int` (positive integer). When set, the adventure SHALL be excluded from the eligible pool once `adventures_completed[ref] >= max_completions` for the current iteration. `repeatable: false` and `max_completions` SHALL NOT be declared on the same adventure — the content loader SHALL raise a validation error if both are present.

#### Scenario: Adventure is hidden at cap

- **WHEN** an adventure has `max_completions: 3` and the player has completed it 3 times this iteration
- **THEN** the adventure does not appear in the eligible pool

#### Scenario: Adventure is eligible below cap

- **WHEN** an adventure has `max_completions: 3` and the player has completed it 2 times
- **THEN** the adventure is eligible

#### Scenario: repeatable: false and max_completions together is a load error

- **WHEN** an adventure declares both `repeatable: false` and `max_completions: 5`
- **THEN** the content loader raises a validation error at load time

---

### Requirement: Adventures can declare a calendar-day cooldown

An `AdventureSpec` MAY declare `cooldown_days: int` (positive integer). When set, the adventure SHALL be excluded from the pool until at least `cooldown_days` calendar days have elapsed since the adventure was last completed. The date of last completion is stored in `CharacterState.adventure_last_completed_on` as an ISO date string. If the adventure has never been completed, no cooldown applies.

#### Scenario: Adventure on cooldown is hidden

- **WHEN** an adventure has `cooldown_days: 1` and was completed today
- **THEN** the adventure does not appear in the eligible pool today

#### Scenario: Adventure is available after cooldown expires

- **WHEN** an adventure has `cooldown_days: 1` and was completed at least 1 day ago
- **THEN** the adventure is eligible (subject to other constraints)

#### Scenario: Adventure never completed has no cooldown

- **WHEN** an adventure has `cooldown_days: 7` and has never been completed
- **THEN** the adventure is eligible regardless of the date

---

### Requirement: Adventures can declare an adventure-count cooldown

An `AdventureSpec` MAY declare `cooldown_adventures: int` (positive integer). When set, the adventure SHALL be excluded from the pool until the player has completed at least `cooldown_adventures` other adventures since the adventure was last run. The total adventures completed count at time of last completion is stored in `CharacterState.adventure_last_completed_at_total`. The current total is `sum(statistics.adventures_completed.values())`. Cooldown is active if `current_total - last_total < cooldown_adventures`.

#### Scenario: Adventure on adventure-count cooldown is hidden

- **WHEN** an adventure has `cooldown_adventures: 3` and was last completed when total was 10, and total is now 12
- **THEN** the adventure does not appear (12 - 10 = 2 < 3)

#### Scenario: Adventure is available after enough adventures pass

- **WHEN** an adventure has `cooldown_adventures: 3` and was last completed when total was 10, and total is now 13
- **THEN** the adventure is eligible (13 - 10 = 3 >= 3)

---

### Requirement: Repeat state persists across sessions

`adventure_last_completed_on` and `adventure_last_completed_at_total` SHALL be persisted to the database in a `character_iteration_adventure_state` table and restored on character load. Existing per-iteration adventure completion counts (via `CharacterStatistics.adventures_completed`) already persist via `character_iteration_statistics`.

#### Scenario: Cooldown survives session restart

- **WHEN** a player completes an adventure with `cooldown_days: 1` and ends the session
- **THEN** on next session start, the adventure is still unavailable if the calendar day has not changed
