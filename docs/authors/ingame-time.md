# In-Game Time System

Oscilla's in-game time system lets you define a calendar — hours, days, seasons, years — that advances as players complete adventures. The calendar drives new condition predicates, template variables, named "eras" with custom counters, and a second adjustable clock for time-manipulation effects.

The system is entirely opt-in. Games that don't configure `time:` in `game.yaml` are completely unaffected.

---

## Overview

The time system consists of three parts:

1. **Cycles** — a hierarchy of calendar units (tick → hour → day → season → year), each with optional display labels and a position within its parent cycle.
2. **Eras** — named counters that activate under conditions and track how many of a given cycle have completed while the era is active (e.g., "Year 298 AC").
3. **Two clocks** — `internal_ticks` (monotone, never adjustable, used for cooldowns) and `game_ticks` (narrative, adjustable by the `adjust_game_ticks` effect).

---

## Enabling the System

Add a `time:` block to `game.yaml` under `spec`:

```yaml
apiVersion: oscilla/v1
kind: Game
metadata:
  name: my-game
spec:
  displayName: "My Game"
  xp_thresholds: [100, 300, 600]
  hp_formula:
    base_hp: 10
    hp_per_level: 5
  time:
    ticks_per_adventure: 1
    base_unit: tick
    cycles:
      - type: ticks
        name: tick
```

---

## `time:` Fields at a Glance

| Field                 | Default | Description                                                                                                                |
| --------------------- | ------- | -------------------------------------------------------------------------------------------------------------------------- |
| `ticks_per_adventure` | `1`     | How many ticks each completed adventure costs.                                                                             |
| `base_unit`           | `tick`  | Display name for a single tick (used in templates).                                                                        |
| `pre_epoch_behavior`  | `clamp` | How `adjust_game_ticks` handles negative results: `clamp` (floor at 0) or `allow` (allow negative).                        |
| `cycles`              | `[]`    | Ordered list of cycle definitions. At least one `type: ticks` root cycle is required when using the time system.           |
| `epoch`               | `{}`    | Starting position of the calendar at `game_ticks = 0`. Keys are cycle names; values are label strings or 1-based integers. |
| `eras`                | `[]`    | Named counters that activate and increment automatically.                                                                  |

---

## Cycles

### Root cycle (`type: ticks`)

Exactly one root cycle defines the base tick unit. Every game tick advances the root cycle by one. The root cycle has no `count` or `labels` — those belong on derived cycles.

```yaml
- type: ticks
  name: tick
```

### Derived cycle (`type: cycle`)

Derived cycles are built on top of a parent cycle. One unit of this cycle equals `count` units of its parent.

```yaml
- type: cycle
  name: day
  parent: tick
  count: 4
  labels:
    - Dawn
    - Noon
    - Dusk
    - Midnight
```

Cycles can be chained to arbitrary depth (`tick → hour → day → month → year`). The engine pre-computes the tick-to-unit mapping at load time.

### Epoch

The `epoch` block shifts the display calendar so that `game_ticks = 0` shows the named starting position instead of position 0:

```yaml
epoch:
  day: Dawn
  year: 1
```

Values may be label strings (if labels are declared) or 1-based integers. Multiple keys combine their offsets; they don't constrain each other.

---

## Eras

An era is a named period with its own counter. It tracks how many completions of a given cycle have occurred while the era is active.

```yaml
eras:
  - name: age-of-the-empire
    format: "Year {count} AE"
    epoch_count: 298
    tracks: year
    start_condition:
      type: adventures_completed
      name: coronation
      gte: 1
    end_condition:
      type: game_calendar_era_is
      era: age-of-the-republic
      state: active
```

| Field             | Description                                                                                                |
| ----------------- | ---------------------------------------------------------------------------------------------------------- |
| `name`            | Unique identifier. Used in `game_calendar_era_is` conditions and the `ingame_time.eras` template variable. |
| `format`          | Python `str.format`-style string with `{count}`.                                                           |
| `epoch_count`     | Starting counter value, default 1.                                                                         |
| `tracks`          | Cycle name or alias whose completed cycles increment the counter.                                          |
| `start_condition` | When first true, sets `era_started_at_ticks` and activates the era. Absent → always active from tick 0.    |
| `end_condition`   | When first true after activation, deactivates the era permanently. Absent → era never ends.                |

Each condition fires **at most once per character iteration** (latch semantics). Once an era ends, it never restarts.

---

## Conditions

Three new condition predicates are available when the time system is configured. All return `false` with a warning if the time system is not configured.

### `game_calendar_time_is`

Numeric comparison against either the internal clock or the game clock:

```yaml
# True once 100 ticks have passed on the internal clock
- type: game_calendar_time_is
  clock: internal
  gte: 100

# True every 4 ticks on the game clock (e.g., at the start of each day)
- type: game_calendar_time_is
  clock: game
  mod:
    divisor: 4
    remainder: 0
```

Comparators: `gt`, `gte`, `lt`, `lte`, `eq`, `mod` (same as `character_stat` conditions).

### `game_calendar_cycle_is`

Tests the current label of a named cycle:

```yaml
- type: game_calendar_cycle_is
  cycle: day
  value: Dawn
```

### `game_calendar_era_is`

Tests whether a named era is currently active:

```yaml
- type: game_calendar_era_is
  era: age-of-the-empire
  state: active
```

---

## Effects

### `adjust_game_ticks`

Adjusts `game_ticks` by a signed integer delta. Does **not** affect `internal_ticks`.

```yaml
# Move the game clock forward by 8 ticks (e.g., skip two days)
- type: adjust_game_ticks
  delta: 8

# Move the game clock backward by 4 ticks (time-reversal effect)
- type: adjust_game_ticks
  delta: -4
```

Negative values move the clock backward. With `pre_epoch_behavior: clamp` (default), the result is floored at 0. With `pre_epoch_behavior: allow`, negative values are allowed.

---

## Templates

When the time system is configured, an `ingame_time` variable is available in all narrative templates. It is `None` when the time system is not configured — always guard with `{% if ingame_time %}`.

```jinja
{% if ingame_time %}
It is {{ ingame_time.cycles['day'].label }} on {{ ingame_time.cycles['week'].label }}.
The year is {{ ingame_time.eras['age-of-the-empire'].count }} AE.
{% endif %}
```

### `ingame_time` attributes

| Attribute        | Type                    | Description                                                      |
| ---------------- | ----------------------- | ---------------------------------------------------------------- |
| `internal_ticks` | `int`                   | Monotone tick counter (never adjusted by effects).               |
| `game_ticks`     | `int`                   | Narrative tick counter (may be adjusted by `adjust_game_ticks`). |
| `cycles`         | `dict[str, CycleState]` | All declared cycles, keyed by name and alias.                    |
| `eras`           | `dict[str, EraState]`   | All declared eras, keyed by name.                                |

### `CycleState` attributes

| Attribute  | Description                                                                |
| ---------- | -------------------------------------------------------------------------- |
| `name`     | Canonical cycle name.                                                      |
| `position` | 0-based index within the cycle's label list.                               |
| `label`    | Display string (label at `position`, or `"name N"` if no labels declared). |

### `EraState` attributes

| Attribute | Description                            |
| --------- | -------------------------------------- |
| `name`    | Era name.                              |
| `count`   | Current counter value.                 |
| `active`  | `true` if the era is currently active. |

---

## Adventure Tick Cost

Each adventure can declare its own tick cost, overriding the game-wide default:

```yaml
apiVersion: adventure/v1
kind: Adventure
metadata:
  name: long-journey
spec:
  displayName: Long Journey
  ticks: 3
  steps:
    - type: outcome
      outcome: success
```

When `time:` is not configured, `ticks` is ignored and no error is raised.

---

## Tick-Based Cooldowns

Two new cooldown fields use tick values rather than calendar days:

```yaml
apiVersion: adventure/v1
kind: Adventure
metadata:
  name: daily-training
spec:
  displayName: Daily Training
  # Require 4 internal ticks to pass (one full day at ticks_per_adventure: 1)
  cooldown_ticks: 4
  # Also require 4 game ticks — both must be satisfied simultaneously
  cooldown_game_ticks: 4
  steps:
    - type: outcome
      outcome: success
```

`cooldown_ticks` uses `internal_ticks` (monotone); `cooldown_game_ticks` uses `game_ticks` (adjustable). Both can be set simultaneously — the player must satisfy both cooldowns.

The deprecated `cooldown_adventures` field maps to `cooldown_ticks` at load time with a warning. When switching from `cooldown_adventures` to `cooldown_ticks`, the counting semantics are equivalent as long as `ticks_per_adventure = 1` (the default).

---

## Complete Minimal Example

```yaml
apiVersion: oscilla/v1
kind: Game
metadata:
  name: minimal-time-example
spec:
  displayName: "Minimal Time Example"
  xp_thresholds: [100, 300, 600]
  hp_formula:
    base_hp: 10
    hp_per_level: 5
  time:
    ticks_per_adventure: 1
    base_unit: tick
    cycles:
      - type: ticks
        name: tick
      - type: cycle
        name: day
        parent: tick
        count: 4
        labels:
          - Dawn
          - Noon
          - Dusk
          - Midnight
    eras:
      - name: age-of-discovery
        format: "Day {count}"
        tracks: day
```

With this config, each adventure costs 1 tick. After 4 adventures, one full day has passed (Dawn → Noon → Dusk → Midnight → Dawn) and the era counter increments.
