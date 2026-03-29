# Level Down

## Purpose

Defines the behavior of the `add_xp()` function when receiving negative XP grants, including level reduction, HP capping, and hard minimums for XP and level.

## Requirements

### Requirement: Negative XP drains levels

`add_xp()` SHALL support negative `amount` values that reduce the player's XP and, if the resulting XP falls below the threshold for the current level, reduce the player's level. For each level lost, `max_hp` SHALL be reduced by `hp_per_level`. `hp` SHALL be capped at the new `max_hp` if it exceeds it. The return value SHALL be a `tuple[List[int], List[int]]` where the first list contains levels gained and the second contains levels lost.

#### Scenario: XP reduction causes de-level

- **WHEN** a player is level 2 with `xp = 80` (threshold for level 2 is 100) and `xp_grant { amount: -50 }` is applied
- **THEN** the player is level 1, `xp = 30` (clamped above 0), and `max_hp` is reduced by `hp_per_level`

#### Scenario: HP is capped after de-level

- **WHEN** a player de-levels and was at full HP
- **THEN** `hp` equals the new `max_hp` (excess HP is removed)

#### Scenario: Multiple levels can be lost in one grant

- **WHEN** a very large negative XP grant would cross multiple level thresholds
- **THEN** all affected levels are listed in `levels_lost` and `max_hp` is reduced once per lost level

#### Scenario: De-level TUI message is shown for each lost level

- **WHEN** a player loses one or more levels
- **THEN** the TUI displays a message for each level lost naming the new level

---

### Requirement: XP and level are clamped at their minimum values

XP SHALL be clamped at 0; it SHALL NOT go below 0. Level SHALL be clamped at 1; it SHALL NOT go below 1. If a negative XP grant would reduce XP below 0, XP is set to 0 and the level remains 1 regardless of the grant amount.

#### Scenario: XP cannot go below zero

- **WHEN** a player at level 1 with `xp = 30` receives `xp_grant { amount: -200 }`
- **THEN** `xp` equals `0` and `level` remains `1`

#### Scenario: XP grant to already-minimum state is a no-op

- **WHEN** a player is level 1 with `xp = 0` and receives `xp_grant { amount: -1 }`
- **THEN** `xp` remains `0`, `level` remains `1`, and `levels_lost` is empty
