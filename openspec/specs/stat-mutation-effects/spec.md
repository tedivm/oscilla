# Stat Mutation Effects

## Purpose

Defines the `stat_change` and `stat_set` adventure effects that modify player stat values, including their YAML syntax, validation rules, and runtime behavior.

## Requirements

### Requirement: stat_change effect applies a numeric delta to a player stat

The `stat_change` adventure effect SHALL modify a named stat by a signed numeric amount. The `stat` field SHALL reference a stat name declared in `CharacterConfig`. The `amount` field SHALL be a non-zero integer or float. The effect SHALL be validated at content load time: the referenced stat MUST exist in `CharacterConfig` and its declared type MUST be `int` or `float`. A `stat_change` targeting a `bool` stat SHALL be a content load error.

#### Scenario: Positive delta increases int stat

- **WHEN** `stat_change { stat: strength, amount: 2 }` is applied to a player with `strength: 10`
- **THEN** `player.stats["strength"]` equals `12`

#### Scenario: Negative delta decreases float stat

- **WHEN** `stat_change { stat: speed, amount: -0.5 }` is applied to a player with `speed: 1.0`
- **THEN** `player.stats["speed"]` equals `0.5`

#### Scenario: Targeting a bool stat is a load error

- **WHEN** a manifest declares `stat_change { stat: is_blessed, amount: 1 }` and `is_blessed` is a `bool` stat
- **THEN** the content loader raises a `LoadError` identifying the adventure manifest and the invalid stat type

#### Scenario: Targeting an unknown stat is a load error

- **WHEN** a manifest declares `stat_change { stat: nonexistent, amount: 1 }`
- **THEN** the content loader raises a `LoadError` identifying the adventure manifest and the unknown stat name

---

### Requirement: stat_set effect assigns an absolute value to a player stat

The `stat_set` adventure effect SHALL set a named stat to an explicit value. The `stat` field SHALL reference a stat name declared in `CharacterConfig`. The `value` field SHALL be validated at content load time for type compatibility with the stat's declared type. An incompatible value (e.g. a string assigned to an `int` stat) SHALL be a content load error.

#### Scenario: Setting an int stat to a specific value

- **WHEN** `stat_set { stat: strength, value: 15 }` is applied to a player with any `strength` value
- **THEN** `player.stats["strength"]` equals `15`

#### Scenario: Setting a bool stat toggles its value

- **WHEN** `stat_set { stat: is_blessed, value: true }` is applied
- **THEN** `player.stats["is_blessed"]` is `True`

#### Scenario: Type-incompatible value is a load error

- **WHEN** a manifest declares `stat_set { stat: strength, value: "hello" }` and `strength` is an `int` stat
- **THEN** the content loader raises a `LoadError` identifying the incompatible value type
