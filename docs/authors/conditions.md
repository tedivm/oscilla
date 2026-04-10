# Conditions

Conditions are the engine's universal gate. They let you express "this content is available when…" in one consistent syntax, and that syntax works everywhere: [adventure](./adventures.md) `requires`, [location](./world-building.md) `unlock`, choice option `requires`, [item equip requirements](./items.md#equip-requirements), [passive effects](./passive-effects.md), [skill](./skills.md) activation guards — the same vocabulary, the same rules, everywhere.

This means you learn conditions once, and everything clicks into place.

---

## Your First Conditions

Here's a simple adventure that requires the player to be at least level 3:

```yaml
apiVersion: oscilla/v1
kind: Adventure
metadata:
  name: haunted-cellar
spec:
  displayName: "The Haunted Cellar"
  description: "Strange sounds come from below."
  requires:
    type: level
    value: 3
  steps:
    - type: narrative
      text: "You descend into the darkness..."
```

That `requires` block is a condition. It evaluates true when the player's level is 3 or higher, and false otherwise. When false, the adventure won't appear in the location's adventure pool.

The same condition could appear on a location `unlock`, a choice option's `requires`, or an item's `equip.requires`. The syntax is identical.

You can also combine conditions from the start. Use `and` to require multiple things at once:

```yaml
requires:
  type: and
  conditions:
    - type: level
      value: 3
    - type: milestone
      name: "found-the-map"
```

This is true only when the player is level 3 **and** has the `found-the-map` milestone. Each entry in `conditions` is a full condition in its own right — `and` can even nest other `and` or `or` blocks.

---

## Checking What's True Right Now

### Level

The most common gate. True when the player's level meets or exceeds the value.

```yaml
requires:
  type: level
  value: 5
```

### Milestone

True when the player has earned a specific milestone. Milestones are permanent flags set by [`milestone_grant` effects](./effects.md#milestone-grant).

```yaml
requires:
  type: milestone
  name: "rescued-the-princess"
```

Use milestones to track story progress, gate story-sensitive content, and prevent adventures from triggering twice.

### Item in Inventory

True when the player holds a certain item — counting both stackable piles and individual instances.

```yaml
requires:
  type: item
  item_ref: ancient-key
  quantity: 1 # default is 1 if omitted
```

### Character Stat

True when a stat meets a numeric comparison. Works with any `int` [stat](./game-configuration.md#stats) defined in `character_config.yaml`.

```yaml
requires:
  type: character_stat
  stat: strength
  gte: 15
```

Available operators: `gte` (≥), `lte` (≤), `eq` (=), `gt` (>), `lt` (<).

By default this compares the **effective** stat — base value plus any bonuses from equipped items. To check the raw stat and ignore equipment bonuses, use `stat_source: base`:

```yaml
requires:
  type: character_stat
  stat: strength
  gte: 15
  stat_source: base
```

Use `stat_source: base` on item equip requirements when you want to enforce a true intrinsic-stat floor — so the requirement can only be met by the player's raw stat, not by bonuses from other gear they happen to be wearing or effects that are active.

> **Note:** An item's own stat bonus is always excluded from its own equip check by the engine, regardless of `stat_source`. Self-justification is not possible.

### Item Equipped

True when the player currently has a specific item occupying an equipment slot.

```yaml
requires:
  type: item_equipped
  item: enchanted-ring
```

### Item Held with a Label

True when any item in the player's inventory (equipped or not) carries a specific label. Labels are declared in [`game.yaml`](./game-configuration.md#item-labels).

```yaml
requires:
  type: item_held_label
  label: rare
```

> **Note:** This condition cannot be used in `passive_effects` — see [Passive Effects](./passive-effects.md) for why.

### Any Equipped Item Has a Label

True when any currently-equipped item carries a label.

```yaml
requires:
  type: any_item_equipped
  label: magic
```

> **Note:** This condition cannot be used in `passive_effects` either.

### Skill Known or Available

True when the player has learned a [skill](./skills.md), or has it available (including through item grants).

```yaml
# Must have permanently learned this skill
requires:
  type: skill
  skill_ref: arcane-shield
  mode: learned

# Skill is accessible right now (includes item grants)
requires:
  type: skill
  skill_ref: arcane-shield
  mode: available
```

### Enemies Defeated

True when the player has defeated a cumulative count of a specific enemy.

```yaml
requires:
  type: enemies_defeated
  name: goblin-scout
  gte: 10
```

### Locations Visited

True when the player has visited a location a certain number of times.

```yaml
requires:
  type: locations_visited
  name: ancient-ruins
  gte: 1
```

### Adventures Completed

True when the player has completed a specific adventure a certain number of times.

```yaml
requires:
  type: adventures_completed
  name: tutorial-quest
  gte: 1
```

### Prestige Count

True when the player has prestiged a certain number of times.

```yaml
requires:
  type: prestige_count
  gte: 1
```

### Milestone Ticks Elapsed

True when a milestone was granted at least (or at most) N adventure ticks ago. This lets you create content that unlocks after a story beat "settles" for a while, or expires if the player waits too long.

```yaml
requires:
  type: milestone_ticks_elapsed
  name: "completed-the-ritual"
  gte: 5 # adventure must be at least 5 ticks after milestone was granted
```

| Field  | Type | Description                                                                            |
| ------ | ---- | -------------------------------------------------------------------------------------- |
| `name` | str  | Name of the milestone to check. If the player doesn't hold it, the condition is false. |
| `gte`  | int  | Minimum number of ticks that must have elapsed since the milestone was granted.        |
| `lte`  | int  | Maximum number of ticks that may have elapsed since the milestone was granted.         |

At least one of `gte` or `lte` must be provided. Both can be combined to create a tick window:

```yaml
requires:
  type: milestone_ticks_elapsed
  name: "found-the-artifact"
  gte: 3
  lte: 10 # adventure is only available 3–10 ticks after the milestone
```

"Ticks" here are **internal adventure ticks** — each adventure you complete advances the counter by one. They are not real-world time. Use [calendar conditions](#real-world-calendar-conditions) for wall-clock gating.

---

## Real-World Calendar Conditions

Calendar conditions gate content on the real-world date and time. All eight predicates compose with `all`, `any`, and `not` the same way as every other condition type.

> **Server time and timezone:** By default, all calendar predicates evaluate against server local time. If your game has a specific audience timezone, set `timezone` in `game.yaml` (e.g. `timezone: "America/New_York"`) so that seasons, months, and time windows reflect your players' clock rather than the server's. See [Game Configuration](./game-configuration.md#timezone-configuration).

### season_is

True when the current real-world season matches. Uses meteorological seasons (not astronomical). The hemisphere is determined by `season_hemisphere` in `game.yaml` (default `northern`).

| Hemisphere | spring  | summer  | autumn  | winter  |
| ---------- | ------- | ------- | ------- | ------- |
| northern   | Mar–May | Jun–Aug | Sep–Nov | Dec–Feb |
| southern   | Sep–Nov | Dec–Feb | Mar–May | Jun–Aug |

```yaml
requires:
  type: season_is
  value: spring # spring | summer | autumn | winter
```

### moon_phase_is

True when the current lunar phase matches. Uses an approximate 29.5-day cycle. Accuracy is ±1 day, suitable for narrative flavor.

Valid values: `New Moon`, `Waxing Crescent`, `First Quarter`, `Waxing Gibbous`, `Full Moon`, `Waning Gibbous`, `Last Quarter`, `Waning Crescent`

```yaml
requires:
  type: moon_phase_is
  value: "Full Moon"
```

### zodiac_is

True when today's Western zodiac sign matches. Based on Sun-entry boundary dates.

Valid values: `Aries`, `Taurus`, `Gemini`, `Cancer`, `Leo`, `Virgo`, `Libra`, `Scorpio`, `Sagittarius`, `Capricorn`, `Aquarius`, `Pisces`

```yaml
requires:
  type: zodiac_is
  value: Scorpio
```

### chinese_zodiac_is

True when the current year's Chinese zodiac animal matches. Uses a 12-year cycle. Does not account for the Lunar New Year boundary (late January/February) — if that precision matters, combine with `month_is`.

Valid values: `Rat`, `Ox`, `Tiger`, `Rabbit`, `Dragon`, `Snake`, `Horse`, `Goat`, `Monkey`, `Rooster`, `Dog`, `Pig`

```yaml
requires:
  type: chinese_zodiac_is
  value: Dragon
```

### month_is

True when the current month matches. Accepts either an integer (1–12) or a full English month name. Abbreviated names (e.g. `Oct`) are not accepted.

```yaml
# Integer form
requires:
  type: month_is
  value: 10

# String form — same result
requires:
  type: month_is
  value: October
```

### day_of_week_is

True when the current day of the week matches. Accepts either an integer (0=Monday … 6=Sunday) or a full English weekday name. Abbreviated names (e.g. `Fri`) are not accepted.

```yaml
# String form
requires:
  type: day_of_week_is
  value: Friday

# Integer form — same result (4 = Friday)
requires:
  type: day_of_week_is
  value: 4
```

### date_is

True when the current date matches. `year` is optional — omit it to match the same date every year (annual events such as holidays). Include `year` for a one-off date.

```yaml
# Annual — matches every December 25
requires:
  type: date_is
  month: 12
  day: 25

# One-off — only April 5, 2026
requires:
  type: date_is
  month: April
  day: 5
  year: 2026
```

`month` accepts an integer or a full English name.

### date_between

True when the current date falls within a month/day range. Both `start` and `end` are objects with `month` and `day` fields. The range is **inclusive** on both ends. `month` accepts an integer or a full English name.

```yaml
# True during the summer months (June 1 through August 31)
requires:
  type: date_between
  start:
    month: June
    day: 1
  end:
    month: August
    day: 31
```

When `start` is later in the year than `end`, the range wraps the year boundary:

```yaml
# Winter holiday season: December 1 through January 31
requires:
  type: date_between
  start:
    month: December
    day: 1
  end:
    month: January
    day: 31
```

Setting `start` equal to `end` always evaluates to false and logs a warning. For a single specific date use `date_is` instead.

### time_between

True when the current time falls within the specified window. Times are in 24-hour `HH:MM` format. The window is inclusive on both ends.

```yaml
# Business hours
requires:
  type: time_between
  start: "09:00"
  end: "17:00"
```

When `start` is later in the day than `end`, the window wraps midnight:

```yaml
# Night hours: 22:00 or later, or 04:00 or earlier
requires:
  type: time_between
  start: "22:00"
  end: "04:00"
```

Setting `start` equal to `end` always evaluates to false and logs a warning.

### Composing calendar conditions

Calendar predicates compose freely with `all`, `any`, and `not`:

```yaml
# Full Moon in autumn
requires:
  type: all
  conditions:
    - type: season_is
      value: autumn
    - type: moon_phase_is
      value: "Full Moon"

# Autumn months (September, October, November) using any
requires:
  type: any
  conditions:
    - type: month_is
      value: 9
    - type: month_is
      value: 10
    - type: month_is
      value: 11

# Friday evening
requires:
  type: all
  conditions:
    - type: day_of_week_is
      value: Friday
    - type: time_between
      start: "18:00"
      end: "23:00"

# Not winter
requires:
  type: not
  condition:
    type: season_is
    value: winter
```

> **Calendar functions in templates:** All eight calendar predicates have matching template functions — `season(today())`, `moon_phase(today())`, `zodiac_sign(today())`, etc. — for use in narrative text. See [Templates §Calendar and Astronomical Functions](./templates.md#calendar-and-astronomical-functions).

---

## Archetype Conditions

[Archetypes](./archetypes.md) are persistent states held by a character — roles, ranks, or earned identities granted and revoked by effects. These conditions let you gate content on which archetypes a character holds, how many they hold, or how long ago one was granted.

### `has_archetype`

True when the character currently holds the named archetype.

```yaml
requires:
  type: has_archetype
  name: warrior
```

| Field  | Type  | Description                      |
| ------ | ----- | -------------------------------- |
| `name` | `str` | Archetype manifest name to check |

### `has_all_archetypes`

True when the character holds **every** archetype in the list. Useful for gating content behind a combination of earned states.

```yaml
requires:
  type: has_all_archetypes
  names:
    - warrior
    - guild-member
```

| Field   | Type        | Description                               |
| ------- | ----------- | ----------------------------------------- |
| `names` | `List[str]` | All of these archetype names must be held |

### `has_any_archetypes`

True when the character holds **at least one** archetype in the list. Useful for letting multiple paths unlock the same content.

```yaml
requires:
  type: has_any_archetypes
  names:
    - warrior
    - soldier
    - veteran
```

| Field   | Type        | Description                              |
| ------- | ----------- | ---------------------------------------- |
| `names` | `List[str]` | At least one of these names must be held |

### `archetype_count`

True when the number of archetypes currently held by the character satisfies the numeric comparison. At least one of `gte`, `lte`, or `eq` must be provided.

```yaml
requires:
  type: archetype_count
  gte: 2 # at least 2 archetypes held
```

```yaml
requires:
  type: archetype_count
  eq: 1 # exactly 1 archetype held
```

| Field | Type  | Description                                   |
| ----- | ----- | --------------------------------------------- |
| `gte` | `int` | Minimum number of held archetypes (inclusive) |
| `lte` | `int` | Maximum number of held archetypes (inclusive) |
| `eq`  | `int` | Exact number of held archetypes               |

### `archetype_ticks_elapsed`

True when a certain number of internal adventure ticks have elapsed since the named archetype was granted. Returns false if the archetype is not currently held. At least one of `gte` or `lte` must be provided.

```yaml
requires:
  type: archetype_ticks_elapsed
  name: warrior
  gte: 10 # held for at least 10 ticks
```

Both can be combined to create a tick window:

```yaml
requires:
  type: archetype_ticks_elapsed
  name: initiate
  gte: 5
  lte: 20 # held between 5 and 20 ticks
```

| Field  | Type  | Description                                                                     |
| ------ | ----- | ------------------------------------------------------------------------------- |
| `name` | `str` | Archetype to check. If not currently held, the condition is false.              |
| `gte`  | `int` | Minimum number of ticks that must have elapsed since the archetype was granted. |
| `lte`  | `int` | Maximum number of ticks that may have elapsed since the archetype was granted.  |

See [Archetypes](./archetypes.md) for how to define archetypes and grant them via effects.

---

## Combining Conditions

A single condition is useful, but the real power comes from composing them.

### All (AND) — every condition must pass

```yaml
requires:
  type: all
  conditions:
    - type: level
      value: 10
    - type: milestone
      name: "found-ancient-map"
    - type: item
      item_ref: explorer-lantern
      quantity: 1
```

This adventure is only available to level 10+ players who have found the map _and_ are carrying a lantern. All three must be true.

### Any (OR) — at least one must pass

```yaml
requires:
  type: any
  conditions:
    - type: character_stat
      stat: strength
      gte: 20
    - type: item
      item_ref: battering-ram
      quantity: 1
```

The door can be broken down by a strong character _or_ by anyone with a battering ram.

### Not — inverts the result

```yaml
unlock:
  type: not
  condition:
    type: milestone
    name: "village-destroyed"
```

The location is open only if the village has _not_ been destroyed. `not` takes a single `condition`, not a list.

### Nesting

Operators nest freely. Here's an adventure available to characters who haven't completed the intro quest yet, but only if they have enough XP to skip it:

```yaml
requires:
  type: all
  conditions:
    - type: not
      condition:
        type: milestone
        name: "intro-completed"
    - type: level
      value: 5
```

---

## Where Conditions Appear

| Location         | Field            | Purpose                                    |
| ---------------- | ---------------- | ------------------------------------------ |
| Adventure        | `requires`       | Gates whether the adventure appears at all |
| Location         | `unlock`         | Gates whether the location is accessible   |
| Region           | `unlock`         | Gates whether the region is accessible     |
| Choice option    | `requires`       | Hides the option unless condition passes   |
| Stat check step  | `condition`      | Determines which branch runs               |
| Item equip       | `equip.requires` | Prevents equipping unless condition passes |
| Skill activation | `requires`       | Blocks skill use if condition fails        |
| Passive effects  | `condition`      | Applies bonus only while condition holds   |

---

## Reference

### All Condition Types

| Type                      | Required fields            | Optional fields            | Notes                                                                                           |
| ------------------------- | -------------------------- | -------------------------- | ----------------------------------------------------------------------------------------------- |
| `level`                   | `value`                    | —                          | True when player level ≥ value                                                                  |
| `milestone`               | `name`                     | —                          | True when player holds the milestone                                                            |
| `item`                    | `item_ref`                 | `quantity` (default 1)     | Checks inventory count ≥ quantity                                                               |
| `character_stat`          | `stat`, one operator       | `stat_source`              | Operators: `gte`, `lte`, `eq`, `gt`, `lt`                                                       |
| `item_equipped`           | `item`                     | —                          | Checks a specific item is equipped                                                              |
| `item_held_label`         | `label`                    | —                          | Any inventory item has this label                                                               |
| `any_item_equipped`       | `label`                    | —                          | Any equipped item has this label                                                                |
| `skill`                   | `skill_ref`                | `mode` (default `learned`) | `mode`: `learned` or `available`                                                                |
| `enemies_defeated`        | `name`, one operator       | —                          | Operators: `gte`, `lte`, `eq`, `gt`, `lt`                                                       |
| `locations_visited`       | `name`, one operator       | —                          | Operators: `gte`, `lte`, `eq`, `gt`, `lt`                                                       |
| `adventures_completed`    | `name`, one operator       | —                          | Operators: `gte`, `lte`, `eq`, `gt`, `lt`                                                       |
| `prestige_count`          | one operator               | —                          | Operators: `gte`, `lte`, `eq`, `gt`, `lt`                                                       |
| `milestone_ticks_elapsed` | `name`, one of `gte`/`lte` | —                          | True when ticks since milestone grant meet the comparison; false if milestone not held          |
| `has_archetype`           | `name`                     | —                          | True when the character holds the named archetype                                               |
| `has_all_archetypes`      | `names`                    | —                          | True when the character holds **all** named archetypes                                          |
| `has_any_archetypes`      | `names`                    | —                          | True when the character holds **at least one** of the named archetypes                          |
| `archetype_count`         | one operator               | —                          | True when the number of held archetypes satisfies the comparison; operators: `gte`, `lte`, `eq` |
| `archetype_ticks_elapsed` | `name`, one of `gte`/`lte` | —                          | True when ticks since archetype grant meet the comparison; false if archetype not held          |
| `all`                     | `conditions`               | —                          | All child conditions must pass (AND)                                                            |
| `any`                     | `conditions`               | —                          | Any child condition must pass (OR)                                                              |
| `not`                     | `condition`                | —                          | Inverts the single child condition                                                              |
| `season_is`               | `value`                    | —                          | True when meteorological season matches; `spring` \| `summer` \| `autumn` \| `winter`           |
| `moon_phase_is`           | `value`                    | —                          | True when lunar phase matches (approximate ±1 day)                                              |
| `zodiac_is`               | `value`                    | —                          | True when Western zodiac sign matches today's date                                              |
| `chinese_zodiac_is`       | `value`                    | —                          | True when Chinese zodiac animal matches the current year                                        |
| `month_is`                | `value`                    | —                          | Integer 1–12 or full English month name                                                         |
| `day_of_week_is`          | `value`                    | —                          | Integer 0–6 (Mon=0) or full English weekday name                                                |
| `date_is`                 | `month`, `day`             | `year`                     | Annual when `year` omitted; one-off when `year` included                                        |
| `date_between`            | `start`, `end`             | —                          | Each has `month` + `day`; wraps year boundary when `start` > `end`                              |
| `time_between`            | `start`, `end`             | —                          | `HH:MM` 24-hour format; wraps midnight when `start` > `end`                                     |

### `stat_source` Values

| Value                 | Meaning                                         |
| --------------------- | ----------------------------------------------- |
| `effective` (default) | Base stat + all equipment bonuses               |
| `base`                | Raw stat only, ignoring equipped-item modifiers |

### Skill Condition `mode` Values

| Value               | Meaning                                                  |
| ------------------- | -------------------------------------------------------- |
| `learned` (default) | Skill is in the player's permanent `known_skills`        |
| `available`         | Skill is usable right now (includes item-granted skills) |

---

_Next: [Effects](./effects.md) — how to change game state._
