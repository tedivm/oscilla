## MODIFIED Requirements

### Requirement: stat_change effect applies a numeric delta to a player stat

The `stat_change` adventure effect SHALL modify a named stat by a signed integer amount. The `stat` field SHALL reference a stat name declared in `CharacterConfig`. The `amount` field SHALL be a non-zero integer. The effect SHALL be validated at content load time: the referenced stat MUST exist in `CharacterConfig` and its declared type MUST be `int`. A `stat_change` targeting a `bool` stat SHALL be a content load error.

If applying the delta would produce a value outside the stat's effective bounds (see stat-bounds spec), the result SHALL be clamped, a WARNING logged, and the player notified via the TUI. The amount type is now strictly `int` — float amounts are no longer accepted.

#### Scenario: Positive delta increases int stat

- **WHEN** `stat_change { stat: strength, amount: 2 }` is applied to a player with `strength: 10`
- **THEN** `player.stats["strength"]` equals `12`

#### Scenario: Negative delta decreases int stat

- **WHEN** `stat_change { stat: speed, amount: -1 }` is applied to a player with `speed: 5`
- **THEN** `player.stats["speed"]` equals `4`

#### Scenario: Targeting a bool stat is a load error

- **WHEN** a manifest declares `stat_change { stat: is_blessed, amount: 1 }` and `is_blessed` is a `bool` stat
- **THEN** the content loader raises a `LoadError` identifying the adventure manifest and the invalid stat type

#### Scenario: Targeting an unknown stat is a load error

- **WHEN** a manifest declares `stat_change { stat: nonexistent, amount: 1 }`
- **THEN** the content loader raises a `LoadError` identifying the adventure manifest and the unknown stat name

#### Scenario: Float amount is rejected at load time

- **WHEN** a manifest declares `stat_change { stat: speed, amount: 0.5 }` and `speed` is an `int` stat
- **THEN** the content loader raises a `LoadError` identifying the invalid float amount

---

### Requirement: stat_set effect assigns an absolute value to a player stat

The `stat_set` adventure effect SHALL set a named stat to an explicit value. The `stat` field SHALL reference a stat name declared in `CharacterConfig`. The `value` field SHALL be validated at content load time for type compatibility with the stat's declared type: `int` stats require an integer value; `bool` stats require a boolean value. An incompatible value (e.g. a float or string assigned to an `int` stat) SHALL be a content load error.

If the new value would fall outside the stat's effective bounds, the result SHALL be clamped, a WARNING logged, and the player notified via the TUI.

#### Scenario: Setting an int stat to a specific value

- **WHEN** `stat_set { stat: strength, value: 15 }` is applied to a player with any `strength` value
- **THEN** `player.stats["strength"]` equals `15`

#### Scenario: Setting a bool stat toggles its value

- **WHEN** `stat_set { stat: is_blessed, value: true }` is applied
- **THEN** `player.stats["is_blessed"]` is `True`

#### Scenario: Float value for int stat is a load error

- **WHEN** a manifest declares `stat_set { stat: strength, value: 1.5 }` and `strength` is an `int` stat
- **THEN** the content loader raises a `LoadError` identifying the incompatible value type

#### Scenario: String value for int stat is a load error

- **WHEN** a manifest declares `stat_set { stat: strength, value: "hello" }` and `strength` is an `int` stat
- **THEN** the content loader raises a `LoadError` identifying the incompatible value type

## REMOVED Requirements

### Requirement: stat_change effect accepts float amounts

**Reason**: Float stat types have been removed from the system. All stats are now `int` or `bool`. Float amounts are meaningless for integer stats and were only used by the testlandia `speed` test fixture.

**Migration**: Change any `stat_change` `amount` values that are floats to `int`. If fractional increments were intentional game design, reconsider the stat's unit scale (e.g., represent speed as tenths: `10` instead of `1.0`, increment by `1` instead of `0.1`).

### Requirement: stat_set accepts float values for float stats

**Reason**: The `float` stat type has been removed. Float values are no longer valid as `stat_set` targets.

**Migration**: Update any `stat_set` effects that set float values to use integer values. Update the corresponding `StatDefinition` from `type: float` to `type: int`.
