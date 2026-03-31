# Stat Bounds

## Purpose

Defines the optional per-stat bounds system that constrains how far `int` stat values can be driven by adventure effects. Covers the `StatBounds` model, its YAML syntax, content load validation rules, the runtime clamp-and-notify behavior, the hard engine-level backstop, and the default bounds that apply when no explicit bounds are declared.

## Requirements

### Requirement: StatBounds model with optional min and max

The `StatDefinition` model SHALL support an optional `bounds: StatBounds | None` field. `StatBounds` SHALL have two fields: `min: int | None` and `max: int | None`, both defaulting to `None`. When `bounds` is entirely absent or `None`, the effective bounds default to the PostgreSQL `Integer` column range: min = −2,147,483,648 (INT32_MIN), max = 2,147,483,647 (INT32_MAX). When a bound is set to `None` explicitly, the corresponding effective bound SHALL use the same INT32 default for that direction.

#### Scenario: Stat with no bounds uses INT32 defaults

- **WHEN** a `StatDefinition` declares no `bounds` field
- **THEN** the effective min is −2,147,483,648 and the effective max is 2,147,483,647

#### Scenario: Stat with explicit min only

- **WHEN** a `StatDefinition` declares `bounds: { min: 0 }` with no `max`
- **THEN** the effective min is 0 and the effective max is 2,147,483,647

#### Scenario: Stat with both bounds set

- **WHEN** a `StatDefinition` declares `bounds: { min: 0, max: 1000000 }`
- **THEN** the effective min is 0 and the effective max is 1,000,000

---

### Requirement: StatBounds min must not exceed max

When both `min` and `max` are set, `min` SHALL be less than or equal to `max`. A `StatDefinition` where `min > max` SHALL be a content load error.

#### Scenario: min exceeds max is a load error

- **WHEN** a `StatDefinition` declares `bounds: { min: 100, max: 10 }`
- **THEN** the content loader raises a `ValidationError` identifying the invalid bounds

#### Scenario: min equals max is valid

- **WHEN** a `StatDefinition` declares `bounds: { min: 50, max: 50 }`
- **THEN** the content loads successfully (a locked-value stat is unusual but not invalid)

---

### Requirement: Bounds on a bool stat is a load error

`StatBounds` SHALL NOT be set on a stat with `type: "bool"`. A `StatDefinition` where `type == "bool"` and `bounds` is non-null SHALL be a content load error detected at manifest parse time.

#### Scenario: bounds on bool stat raises validation error

- **WHEN** a `StatDefinition` declares `type: bool` and any `bounds` value
- **THEN** a `ValidationError` is raised identifying the stat name and the invalid field

---

### Requirement: Effects layer enforces content-defined bounds (clamp + log + notify)

When a `stat_change` or `stat_set` effect would result in a value outside the stat's content-defined bounds, the engine SHALL:

1. Clamp the result to the nearest bound.
2. Log a `WARNING`-level message including the stat name, attempted value, and clamped value.
3. Notify the player via `tui.show_text()` with a yellow warning message.

The stat SHALL be stored at the clamped value. The application of the effect SHALL NOT be treated as an error or halt the adventure.

#### Scenario: stat_change clamped at max bound

- **WHEN** `stat_change { stat: gold, amount: 5000 }` is applied to a player with `gold: 9999800` and the stat has `bounds.max: 10000000`
- **THEN** `player.stats["gold"]` is set to 10,000,000 (clamped), a WARNING is logged, and the TUI shows a yellow clamp notification

#### Scenario: stat_change clamped at min bound

- **WHEN** `stat_change { stat: gold, amount: -999 }` is applied to a player with `gold: 10` and the stat has `bounds.min: 0`
- **THEN** `player.stats["gold"]` is set to 0 (clamped), a WARNING is logged, and the TUI shows a yellow clamp notification

#### Scenario: stat_set clamped at max bound

- **WHEN** `stat_set { stat: gold, value: 9999999 }` is applied and the stat has `bounds.max: 1000000`
- **THEN** `player.stats["gold"]` is set to 1,000,000 (clamped), a WARNING is logged, and the TUI shows a yellow clamp notification

#### Scenario: value within bounds is applied unchanged

- **WHEN** `stat_change { stat: gold, amount: 100 }` is applied to a player with `gold: 500` and `bounds: { min: 0, max: 1000000 }`
- **THEN** `player.stats["gold"]` is 600 and no clamp warning is emitted

---

### Requirement: CharacterState provides a set_stat backstop enforcing hard INT32 limits

`CharacterState` SHALL expose a `set_stat(name: str, value: int) -> None` method. This method SHALL clamp `value` to INT32_MIN–INT32_MAX before storing it, and SHALL log a `WARNING` if clamping occurs. This check applies regardless of whether the caller has access to content-defined bounds, ensuring no out-of-range value can be written to the database column.

The stats dict SHALL only be mutated through `set_stat()` for integer stats.

#### Scenario: backstop clamps above INT32_MAX

- **WHEN** `set_stat("score", 2147483648)` is called (INT32_MAX + 1)
- **THEN** `player.stats["score"]` is 2,147,483,647 and a WARNING is logged

#### Scenario: backstop clamps below INT32_MIN

- **WHEN** `set_stat("debt", -2147483649)` is called (INT32_MIN - 1)
- **THEN** `player.stats["debt"]` is −2,147,483,648 and a WARNING is logged

#### Scenario: value within INT32 range is stored unchanged by backstop

- **WHEN** `set_stat("gold", 500)` is called
- **THEN** `player.stats["gold"]` is 500 and no WARNING is logged
