# Cookbook: In-Game Time Patterns

The in-game time system is a flexible foundation for a wide range of storytelling techniques. This recipe collection shows several patterns — from seasonal events to time-manipulation puzzles — that can be adapted for your game.

All examples assume you have configured a `time:` block in your `game.yaml`. See the [In-Game Time](../ingame-time.md) guide for the full reference.

---

## Seasonal Events

Gate content on the current season cycle to create a living calendar of recurring events.

**Setup** — a year cycle with four seasons:

```yaml
time:
  ticks_per_adventure: 1
  base_unit: day
  cycles:
    - type: ticks
      name: day
    - type: cycle
      name: season
      parent: day
      count: 90
      labels:
        - Spring
        - Summer
        - Autumn
        - Winter
    - type: cycle
      name: year
      parent: season
      count: 4
```

**Location pool** — show each festival adventure only during its season:

```yaml
adventures:
  - ref: spring-planting-festival
    weight: 50
    requires:
      type: game_calendar_cycle_is
      cycle: season
      value: Spring
  - ref: summer-solstice-rite
    weight: 50
    requires:
      type: game_calendar_cycle_is
      cycle: season
      value: Summer
  - ref: autumn-harvest-fair
    weight: 50
    requires:
      type: game_calendar_cycle_is
      cycle: season
      value: Autumn
  - ref: winter-vigil
    weight: 50
    requires:
      type: game_calendar_cycle_is
      cycle: season
      value: Winter
```

**Narrative text** that always describes the current season:

```yaml
- type: narrative
  text: |
    {% if ingame_time %}
    {% set s = ingame_time.cycles['season'].label %}
    {% if s == 'Spring' %}
    Blossoms drift through the air and the world feels newly born.
    {% elif s == 'Summer' %}
    Heat shimmers above the packed-earth roads. The days stretch long.
    {% elif s == 'Autumn' %}
    Leaves gild the canopy. Harvest smoke drifts from the valleys.
    {% else %}
    Snow muffles the kingdom. Fires burn in every hearth.
    {% endif %}
    {% endif %}
```

---

## Age Counters in Narrative

Era `format` strings let you embed a living age counter directly in prose.

**Setup** — an era that starts at the beginning and tracks realm years:

```yaml
eras:
  - name: realm-age
    format: "Year {count} of the Realm"
    epoch_count: 247
    tracks: year
    # No start_condition means always active from tick 0
```

**Template usage:**

```yaml
- type: narrative
  text: |
    {% if ingame_time %}
    The royal herald proclaims it Year {{ ingame_time.eras['realm-age'].count }} of the Realm.
    {% endif %}
```

`ingame_time.eras['realm-age'].count` starts at 247 and increments each time a full `year` cycle completes — automatically, without any author intervention.

---

## Unlocking a New Era via Milestone

Eras can activate on any condition, including milestones. This lets a story beat — defeating a boss, founding a city, ending a war — trigger an era transition.

**Setup:**

```yaml
eras:
  - name: before-cataclysm
    format: "Year {count} BC"
    epoch_count: 1
    tracks: year
    # No start_condition: active from tick 0
    end_condition:
      type: milestone
      name: cataclysm-triggered
  - name: after-cataclysm
    format: "Year {count} AC"
    epoch_count: 1
    tracks: year
    start_condition:
      type: milestone
      name: cataclysm-triggered
    # No end_condition: this era never ends
```

**In an adventure outcome:**

```yaml
- type: narrative
  text: |
    The ancient seal shatters. The sky tears open.
    A new age has begun.
  effects:
    - type: milestone_grant
      milestone: cataclysm-triggered
```

The moment the player grants that milestone, `before-cataclysm` deactivates and `after-cataclysm` becomes active on the next character state save. Both era counters stop at their last recorded values. Narrative text can reference either:

```yaml
- type: narrative
  text: |
    {% if ingame_time %}
    {% if ingame_time.eras['after-cataclysm'].active %}
    Historians write it as Year {{ ingame_time.eras['after-cataclysm'].count }} AC —
    since the Cataclysm reshaped the world.
    {% else %}
    Scribes record it as Year {{ ingame_time.eras['before-cataclysm'].count }} BC —
    an age of fragile peace before the storm.
    {% endif %}
    {% endif %}
```

---

## Lunar-Gated Encounters

A lunar cycle with 8 moon phases lets you gate rare encounters on the full moon.

**Setup:**

```yaml
time:
  ticks_per_adventure: 1
  base_unit: day
  cycles:
    - type: ticks
      name: day
    - type: cycle
      name: lunar_month
      parent: day
      count: 8
      labels:
        - New Moon
        - Waxing Crescent
        - First Quarter
        - Waxing Gibbous
        - Full Moon
        - Waning Gibbous
        - Last Quarter
        - Waning Crescent
```

**Pool entry** — a wolf encounter that spawns only under the Full Moon:

```yaml
adventures:
  - ref: silver-wolf-encounter
    weight: 30
    requires:
      type: game_calendar_cycle_is
      cycle: moon
      value: Full Moon
```

**Narrative introduction** that always names the current phase:

```yaml
- type: narrative
  text: |
    {% if ingame_time %}
    A {{ ingame_time.cycles['moon'].label }} hangs overhead.
    {% if ingame_time.cycles['moon'].label == 'Full Moon' %}
    Brilliant silver light floods the forest floor. Something stirs in the undergrowth.
    {% elif ingame_time.cycles['moon'].label == 'New Moon' %}
    The sky is moonless and absolute. The forest is pitch dark.
    {% else %}
    Pale shadows stretch between the trees.
    {% endif %}
    {% endif %}
```

---

## Time-Skip Adventure

Give players an explicit "rest and wait" adventure that advances `game_ticks` forward to skip ahead in the calendar.

```yaml
apiVersion: adventure/v1
kind: Adventure
metadata:
  name: rest-and-wait
spec:
  displayName: "Rest and Wait"
  description: "Settle in and let time pass."
  ticks: 24
  steps:
    - type: narrative
      text: |
        You make camp and wait. Days blur into one another.
        {% if ingame_time %}
        When you rouse yourself, it is {{ ingame_time.cycles['season'].label }}.
        {% endif %}
    - type: outcome
      outcome: success
```

The `ticks: 24` field charges 24 game ticks to their budget on completion. Because `game_ticks` drives the calendar, the season, moon phase, and era counters all update accordingly. `internal_ticks` also advances by 24 — cooldowns still tick down, so this isn't a free pass on everything.

---

## Reversing Time — The Undo Puzzle

`adjust_game_ticks` lets you move `game_ticks` backward. Combine with milestones to create a one-time "turn back the clock" moment — useful for time-travel or prophecy mechanics.

```yaml
apiVersion: adventure/v1
kind: Adventure
metadata:
  name: shatter-the-hourglass
spec:
  displayName: "Shatter the Hourglass"
  description: "Use the Hourglass of Ages to reverse time."
  repeatable: false
  requires:
    type: milestone
    name: holds-hourglass-of-ages
  steps:
    - type: narrative
      text: |
        You smash the hourglass against the altar stone. The shards dissolve into light.
        Time unravels. The world lurches backward by a full season.
      effects:
        - type: milestone_grant
          milestone: used-time-reversal
        - type: adjust_game_ticks
          delta: -90
    - type: outcome
      outcome: success
```

`internal_ticks` is not affected by `adjust_game_ticks`, so cooldown-gated abilities still advance normally — the reversal only changes what the calendar displays, not how much real play-time has elapsed.

---

## Corruption Creep — A Slow Disaster

Use `game_calendar_time_is` on the `game` clock to trigger escalating narrative warnings as the game approaches a deadline.

**Setup** — a clock-based disaster that intensifies over time:

```yaml
adventures:
  # Ominous rumbling — appears from tick 30 to just before the deadline
  - ref: corruption-distant-warning
    weight: 20
    requires:
      type: all
      conditions:
        - type: game_calendar_time_is
          clock: game
          gte: 30
        - type: game_calendar_time_is
          clock: game
          lt: 60

  # Intensifying dread — after tick 60
  - ref: corruption-urgent-warning
    weight: 40
    requires:
      type: all
      conditions:
        - type: game_calendar_time_is
          clock: game
          gte: 60
        - type: game_calendar_time_is
          clock: game
          lt: 90

  # Final catastrophe — fires once the deadline tick is reached
  - ref: corruption-catastrophe
    weight: 100
    requires:
      type: game_calendar_time_is
      clock: game
      gte: 90
```

This pattern creates a pressure curve: the player can slow the clock by spending `adjust_game_ticks` reversals (if available), but the game eventually catches up. Because `game_ticks` can be rewound but `internal_ticks` cannot, a player who "cheats" by reversing time still experiences playtime-honest cooldowns — they can't spam reversals infinitely without spending play-time.

---

## Honest Cooldowns With `internal_ticks`

Cycle conditions run on `game_ticks`, which is the adjustable narrative clock. If a player uses the time-reversal mechanic above, the season rolls back — but you may not want cooldowns to reset along with it.

Always wire adventure cooldowns to `cooldown_ticks` (which uses `internal_ticks`) rather than to calendar gates:

```yaml
apiVersion: adventure/v1
kind: Adventure
metadata:
  name: rare-herb-harvest
spec:
  displayName: "Harvest Moonpetal Herb"
  description: "Gather a rare herb that regrows slowly."
  # 48 internal ticks must pass — rewinding game_ticks won't reset this
  cooldown_ticks: 48
  steps:
    - type: narrative
      text: |
        You carefully harvest the moonpetal herb.
        It will take many days to regrow.
      effects:
        - type: item_drop
          loot:
            - item: moonpetal-herb
              weight: 1
    - type: outcome
      outcome: success
```

Rewinding `game_ticks` to go back in the narrative calendar does not reduce `internal_ticks`, so the 48-tick cooldown stays intact. The player sees an earlier season but can't re-harvest the herb early.

---

## Multi-Clock Stat Check

You can write a single `stat_check` that gates on both clocks simultaneously — useful for time-locked content that also resists rewind abuse:

```yaml
- type: stat_check
  condition:
    type: all
    conditions:
      # At least 365 internal ticks must have elapsed (rewind-proof)
      - type: game_calendar_time_is
        clock: internal
        gte: 365
      # The narrative calendar must currently be in Winter
      - type: game_calendar_cycle_is
        cycle: season
        value: Winter
  on_pass:
    steps:
      - type: narrative
        text: |
          The stars are aligned. The ancient rite may proceed.
  on_fail:
    steps:
      - type: narrative
        text: |
          The conditions are not right. You must wait for a true winter
          with enough years of journey behind you.
```

The `internal` clock gate prevents a brand-new player from resetting `game_ticks` to Winter on tick 1. The `season` gate prevents a veteran from performing the ritual outside of winter even with plenty of play hours behind them.

---

## Astrological Signs — The Thirteen Houses of the Void

A long cycle with 13 named signs lets you build a full astrological calendar. Each sign spans a fixed number of game ticks; adventurers born (or playing) under different signs encounter different flavor text, unique pool entries, and even mechanical bonuses.

This example uses a root tick cycle of 365 days (one "solar year") and divides it across 13 signs of 28 days each — 364 days total. The solar year and the zodiac round stay slightly out of phase with each other, which is a deliberate calendar quirk.

**Setup** — define the root day cycle, an intermediate 28-day sign period, the sign cycle derived from that, and a solar year cycle derived independently from the same root:

```yaml
time:
  ticks_per_adventure: 1
  base_unit: day
  cycles:
    - type: ticks
      name: day
    # Intermediate: 28-day sign period (364 days = 13 signs)
    - type: cycle
      name: sign-period
      parent: day
      count: 28
    # The 13 astrological signs — aliases lunar_year (same 364-day span)
    - type: cycle
      name: astro_sign
      parent: sign-period
      count: 13
      aliases:
        - lunar_year
      labels:
        - The Wanderer
        - The Serpent
        - The Crown
        - The Veil
        - The Ember
        - The Tide
        - The Witness
        - The Wound
        - The Gate
        - The Mirror
        - The Chain
        - The Eye
        - The Void
    # Solar year: 365 days — intentionally 1 day longer than the zodiac round
    - type: cycle
      name: solar_year
      parent: day
      count: 365
```

**Pool entry** — rare encounters that only appear under a specific sign:

```yaml
adventures:
  - ref: void-herald-encounter
    weight: 5
    requires:
      type: game_calendar_cycle_is
      cycle: astro_sign
      value: The Void
  - ref: wanderer-vision
    weight: 10
    requires:
      type: game_calendar_cycle_is
      cycle: astro_sign
      value: The Wanderer
```

**Narrative horoscope** — a location that always tells the player their current sign:

```yaml
apiVersion: adventure/v1
kind: Adventure
metadata:
  name: astrologer-reading
spec:
  displayName: "Consult the Astrologer"
  description: "Learn which sign governs your fate today."
  steps:
    - type: narrative
      text: |
        {% if ingame_time %}
        The astrologer traces the star charts with a weathered finger.
        "You walk beneath {{ ingame_time.cycles['astro_sign'].label }}."
        {% endif %}
    - type: outcome
      outcome: success
```

**Era counter** — track how many full zodiac years have passed since the founding of the realm:

```yaml
eras:
  - name: zodiac-age
    format: "Zodiac Age {count}"
    epoch_count: 194
    tracks: solar_year
    # No start_condition: active from the very first tick
```

After each completed `solar_year` cycle (365 ticks), `ingame_time.eras['zodiac-age'].count` increments automatically. `lunar_year` is an alias for `astro_sign` — both refer to the same 364-day zodiac round — and `solar_year` derives independently from `day`. The 1-day difference between the 364-day lunar year and the 365-day solar year is a deliberate quirk of this calendar, not a mistake. Each solar year, the zodiac slips one day further out of phase.

```yaml
- type: narrative
  text: |
    {% if ingame_time %}
    The heavens declare it Zodiac Age {{ ingame_time.eras['zodiac-age'].count }},
    under the sign of {{ ingame_time.cycles['astro_sign'].label }}.
    {% endif %}
```

---

_See also: [In-Game Time](../ingame-time.md) for the full system reference, and [Day-Night Narrative](./day-night-narrative.md) for the real-world clock equivalent of these patterns._
