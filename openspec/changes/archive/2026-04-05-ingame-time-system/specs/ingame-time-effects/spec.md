# In-Game Time Effects

## Purpose

Defines the `adjust_game_ticks` effect that modifies the character's `game_ticks` counter. This is the only effect in this change that directly interacts with the in-game time system.

## Requirements

### Requirement: adjust_game_ticks effect modifies game_ticks by a signed delta

An adventure step MAY declare an effect with `type: adjust_game_ticks` and a `delta: int` field (positive or negative integer). When the effect fires, `CharacterState.game_ticks` SHALL be adjusted by `delta`. `CharacterState.internal_ticks` SHALL NOT be affected.

The effect is subject to the game's `pre_epoch_behavior` setting:

- When `pre_epoch_behavior: clamp` (default): the result is clamped at a minimum of 0. `game_ticks` cannot go below 0.
- When `pre_epoch_behavior: allow`: the result may be any integer including negative values.

When no `time:` block is configured for the game, the effect SHALL be a no-op and SHALL log a warning.

#### Scenario: Positive delta advances game_ticks

- **WHEN** `adjust_game_ticks: {delta: 50}` fires and `game_ticks = 100`
- **THEN** `game_ticks = 150` after the effect

#### Scenario: Negative delta moves game_ticks backward

- **WHEN** `adjust_game_ticks: {delta: -30}` fires and `game_ticks = 100`
- **THEN** `game_ticks = 70` after the effect

#### Scenario: internal_ticks is not affected by the effect

- **WHEN** `adjust_game_ticks: {delta: 100}` fires and `internal_ticks = 200`
- **THEN** `internal_ticks = 200` after the effect (unchanged)

#### Scenario: Clamp behavior prevents negative game_ticks

- **WHEN** `pre_epoch_behavior: clamp`, `game_ticks = 5`, and `adjust_game_ticks: {delta: -100}` fires
- **THEN** `game_ticks = 0` after the effect

#### Scenario: Allow behavior permits negative game_ticks

- **WHEN** `pre_epoch_behavior: allow`, `game_ticks = 5`, and `adjust_game_ticks: {delta: -100}` fires
- **THEN** `game_ticks = -95` after the effect

#### Scenario: Effect with no time system is a no-op with warning

- **WHEN** `adjust_game_ticks: {delta: 10}` fires on a game with no `time:` block configured
- **THEN** `game_ticks` is unchanged
- **THEN** a warning is logged identifying the missing time system

---

### Requirement: adjust_game_ticks composes with other step effects

The `adjust_game_ticks` effect SHALL be a valid member of the adventure step effect union and SHALL fire in the same order as other effects declared in the same step.

#### Scenario: adjust_game_ticks fires alongside stat effects

- **WHEN** a step declares both `stat_set: {stat: score, value: 100}` and `adjust_game_ticks: {delta: 5}` as effects
- **THEN** both effects are applied when the step is processed
- **THEN** `game_ticks` increases by 5
- **THEN** the `score` stat is set to 100

#### Scenario: Effect is valid in combat step post-combat effects

- **WHEN** a `CombatStep` victory outcome includes `adjust_game_ticks: {delta: 24}` as a post-combat effect
- **THEN** the effect fires on victory and `game_ticks` advances by 24
