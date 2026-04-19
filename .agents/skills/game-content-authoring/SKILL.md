---
name: game-content-authoring
description: "Write or modify Oscilla game content YAML manifests for any game package. Use when: creating a new game package, writing adventures, enemies, items, quests, regions, locations, skills, buffs, archetypes, recipes, loot tables, or conditions; designing progression systems; configuring game.yaml or character_config.yaml; authoring template expressions; setting up cooldowns or passive effects; validating content with the CLI; or any task that touches files under a content/ game package directory."
---

# Game Content Authoring

Oscilla games are defined entirely by YAML manifests. There is no code to write — every adventure, enemy, item, skill, and region is a `.yaml` file. The engine discovers manifests by recursively scanning your package directory. Folder names and nesting depth are conventions, not requirements (the one exception: `game.yaml` must be at the package root).

> **Use the `oscilla-content-cli` skill** for CLI validation, schema generation, content inspection, and scaffolding commands. This skill covers what to write; that skill covers how to validate and inspect it.

All commands run via `uv run oscilla ...` from the project root.

---

## Role of the Agent

Your job is to help authors get their story **into the right format** — not to write the story for them.

**Never invent narrative or story content.** The text that players read — `displayName`, `description`, step `text`, option labels, quest stage descriptions, era names, item flavor text, and any other field that appears in the game UI — must come from the author. Do not generate, fill in, or embellish these fields on your own.

**Do** translate what the author provides into correct, valid YAML. **Do** ask the author questions when information is missing:

- Which steps does this adventure have?
- What text should appear in this narrative step?
- What options should the player see at this choice?
- What should the item description say?

When the author gives you a rough description of what they want, convert the structure and mechanics into YAML while leaving blank placeholders (e.g. `displayName: "TODO"`, `text: "TODO"`) for any narrative content they haven't written yet. Then ask them to fill in each placeholder.

In short: you own the **structure**; the author owns the **words**.

---

## Package Layout

A game package is a directory under `GAMES_PATH` (default: `content/`). The directory name is the game identifier.

```
content/
└── my-kingdom/
    ├── game.yaml             ← required
    ├── character_config.yaml ← required
    ├── regions/
    │   └── the-forest/
    │       ├── the-forest.yaml
    │       └── locations/
    │           └── hunters-camp/
    │               ├── hunters-camp.yaml
    │               └── adventures/
    │                   └── wolf-ambush.yaml
    ├── items/
    │   ├── weapons.yaml      ← multiple manifests per file is fine
    │   └── potions.yaml
    ├── enemies/
    ├── quests/
    ├── skills/
    └── archetypes/
```

A manifest file may contain one manifest or multiple manifests as a YAML list — the engine handles both. Every manifest follows the same envelope:

```yaml
apiVersion: oscilla/v1
kind: <Kind>
metadata:
  name: kebab-case-identifier   # used everywhere for cross-references
spec:
  # kind-specific fields
```

`metadata.name` is the identifier used for all cross-references. It must be unique within its kind across the package. Use lowercase kebab-case.

---

## Conditions

Conditions appear in `requires`, `unlock`, choice option `requires`, passive effect `condition`, and item `equip.requires`. The syntax is identical everywhere.

```yaml
# Single condition
requires:
  type: level
  value: 5

# Combine with and/or/not
requires:
  type: all          # all conditions must be true (AND)
  conditions:
    - type: level
      value: 5
    - type: milestone
      name: found-the-dungeon

requires:
  type: any          # at least one must be true (OR)
  conditions:
    - type: milestone
      name: path-a-complete
    - type: milestone
      name: path-b-complete

requires:
  type: not          # negation
  condition:
    type: milestone
    name: quest-failed
```

**Logical combinators** (nest freely at any depth):

| Type   | Key fields            | True when…                              |
| ------ | --------------------- | --------------------------------------- |
| `all`  | `conditions: [...]`   | All sub-conditions are true (AND)       |
| `any`  | `conditions: [...]`   | At least one sub-condition is true (OR) |
| `not`  | `condition: {...}`    | The single sub-condition is false       |

**Progression leaf conditions**:

| Type                   | Key fields                                       | True when…                                        |
| ---------------------- | ------------------------------------------------ | ------------------------------------------------- |
| `prestige_count`       | `gte/lte/eq/gt/lt` (at least one required)       | Prestige count satisfies the comparison           |
| `adventures_completed` | `name: str`, `gte/lte/eq/gt/lt`                  | Named adventure completed N or more times         |
| `enemies_defeated`     | `name: str`, `gte/lte/eq/gt/lt`                  | Named enemy defeated N or more times              |
| `locations_visited`    | `name: str`, `gte/lte/eq/gt/lt`                  | Named location visited N or more times            |

**Milestone leaf conditions**:

| Type                      | Key fields                       | True when…                                                |
| ------------------------- | -------------------------------- | --------------------------------------------------------- |
| `milestone`               | `name: str`                      | Player holds the named milestone                          |
| `milestone_ticks_elapsed` | `name: str`, `gte/lte`           | N adventure ticks have elapsed since the milestone was granted |

**Stat leaf conditions**:

| Type             | Key fields                                                           | True when…                                                    |
| ---------------- | -------------------------------------------------------------------- | ------------------------------------------------------------- |
| `character_stat` | `name: str`, `gte/lte/eq/gt/lt`, `stat_source: "base"\|"effective"` | Named stat satisfies the comparison; `effective` (default) includes equipped gear bonuses, `base` ignores them |

**Item leaf conditions**:

| Type               | Key fields           | True when…                                        |
| ------------------ | -------------------- | ------------------------------------------------- |
| `item`             | `name: str`          | Player holds at least one of the named item       |
| `item_equipped`    | `name: str`          | The specific non-stackable item is equipped       |
| `item_held_label`  | `label: str`         | Any item in inventory carries the label           |
| `any_item_equipped`| `label: str`         | Any currently-equipped item carries the label     |

> **Note:** `item_held_label` and `any_item_equipped` cannot be used inside `passive_effects`.

**Archetype leaf conditions**:

| Type                   | Key fields                               | True when…                                      |
| ---------------------- | ---------------------------------------- | ----------------------------------------------- |
| `has_archetype`        | `name: str`                              | Player currently holds the named archetype      |
| `has_all_archetypes`   | `names: [str, ...]`                      | Player holds every archetype in the list        |
| `has_any_archetypes`   | `names: [str, ...]`                      | Player holds at least one archetype in the list |
| `archetype_count`      | `gte/lte/eq/gt/lt` (at least one)        | Number of held archetypes satisfies comparison  |
| `archetype_ticks_elapsed` | `name: str`, `gte/lte`               | N ticks have elapsed since the named archetype was granted |

**Skill leaf conditions**:

| Type    | Key fields                                        | True when…                                                              |
| ------- | ------------------------------------------------- | ----------------------------------------------------------------------- |
| `skill` | `name: str`, `mode: "available"\|"learned"`       | Player has the skill; `available` (default) includes item-granted skills, `learned` checks only permanently learned skills |

**Quest leaf conditions**:

| Type          | Key fields                    | True when…                                         |
| ------------- | ----------------------------- | -------------------------------------------------- |
| `quest_stage` | `quest: str`, `stage: str`    | The named quest is active and at the named stage   |

**Character identity leaf conditions**:

| Type          | Key fields    | True when…                                           |
| ------------- | ------------- | ---------------------------------------------------- |
| `pronouns`    | `set: str`    | Player uses the named pronoun set (e.g. `they_them`) |
| `name_equals` | `value: str`  | Player name exactly matches (case-sensitive)         |

**Custom condition** (references a `CustomCondition` manifest by name):

| Type     | Key fields   | True when…                                        |
| -------- | ------------ | ------------------------------------------------- |
| `custom` | `name: str`  | The referenced `CustomCondition` body evaluates true |

**Real-world calendar conditions** (evaluate the server's wall-clock time):

| Type                | Key fields                             | True when…                                   |
| ------------------- | -------------------------------------- | -------------------------------------------- |
| `season_is`         | `value: spring\|summer\|autumn\|winter`| Current meteorological season matches        |
| `moon_phase_is`     | `value: str`                           | Current lunar phase matches (e.g. `Full Moon`) |
| `zodiac_is`         | `value: str`                           | Current Western zodiac sign matches          |
| `chinese_zodiac_is` | `value: str`                           | Current Chinese zodiac year animal matches   |
| `month_is`          | `value: int\|str`                      | Current month matches (1–12 or full name)    |
| `day_of_week_is`    | `value: int\|str`                      | Current day matches (0=Mon…6=Sun or name)    |
| `date_is`           | `month, day`, optional `year`          | Current date matches; omit `year` for annual |
| `date_between`      | `start: {month,day}`, `end: {month,day}` | Current date falls in range (wraps year boundary if start > end) |
| `time_between`      | `start: "HH:MM"`, `end: "HH:MM"`      | Current time is in the window (wraps midnight if start > end) |

---

## Effects

Effects fire in adventure step outcomes, `on_win`/`on_defeat`/`on_flee` branches, item `use_effects`, archetype `gain_effects`/`lose_effects`, and passive effects in `game.yaml`.

```yaml
effects:
  - type: stat_change
    stat: xp
    amount: 150            # can be a template expression: "{{ roll(50, 200) }}"

  - type: stat_set
    stat: hp
    value: 20              # set to exact value; also accepts templates

  - type: heal
    amount: 25             # HP restored; respects max_hp bound

  - type: milestone_grant
    milestone: defeated-the-dragon

  - type: item_drop
    loot:
      - item: gold-coins
        weight: 80
      - item: rare-gem
        weight: 20
    count: 2               # number of separate rolls (default: 1)

  - type: item_drop
    loot_ref: forest-drops  # reference a LootTable manifest

  - type: item_grant
    item: ancient-key       # add exactly this item, no roll

  - type: item_remove
    item: ancient-key       # remove one instance

  - type: skill_grant
    skill: quick-heal       # grant a skill permanently

  - type: archetype_grant
    archetype: warrior

  - type: archetype_revoke
    archetype: cursed

  - type: quest_activate
    quest: missing-merchant

  - type: apply_buff
    buff_ref: berserk-state
    duration: 3            # combat turns (for combat buffs)

  - type: emit_trigger
    trigger: special-event  # fire a trigger_adventure from game.yaml

  - type: adjust_game_ticks
    amount: 24             # advance in-game time (requires time system enabled)
```

---

## Templates

Any `text` field in adventure steps and some numeric effect values accept Jinja2 template expressions. Templates are sandboxed.

```yaml
text: |
  Welcome back, {{ player.name }}!
  You are level {{ player.stats['level'] }} with {{ player.stats['hp'] }} HP.

  {% if player.milestones.has('hero-of-the-realm') %}
  The crowd parts for you.
  {% else %}
  You pass through unnoticed.
  {% endif %}

effects:
  - type: stat_change
    stat: xp
    amount: "{{ roll(50, 150) }}"    # dynamic reward
```

**Useful globals**:

| Expression                           | Result                                           |
| ------------------------------------ | ------------------------------------------------ |
| `{{ player.name }}`                  | Character name                                   |
| `{{ player.stats['stat_name'] }}`    | Any stat value                                   |
| `{{ player.milestones.has('name') }}`| True/false milestone check                       |
| `{{ player.pronouns.subject }}`      | Pronoun (they/she/he or custom)                  |
| `{{ roll(low, high) }}`              | Random int in range, inclusive                   |
| `{{ choice(['a', 'b', 'c']) }}`      | Random element from list                         |
| `{{ SECONDS_PER_HOUR }}`             | 3600; also `SECONDS_PER_DAY`, `SECONDS_PER_WEEK` |

---

## In-Game Time System

The in-game time system lets you define a calendar — hours, days, seasons, years — that advances as players complete adventures. It is entirely **opt-in**: games that don't configure `time:` in `game.yaml` are completely unaffected.

### How it works

Every adventure completed advances two clocks:

- **`internal_ticks`** — monotone, never adjustable. Used for cooldowns and milestones. Never goes backward.
- **`game_ticks`** — narrative clock. Can be moved forward or backward with the `adjust_game_ticks` effect.

Both clocks advance by `ticks_per_adventure` (default: `1`) per completed adventure. Adventures can declare `ticks: N` in their spec to override the game-wide default.

### Enabling the system

Add a `time:` block to `game.yaml`:

```yaml
spec:
  time:
    ticks_per_adventure: 1       # how many ticks each adventure costs
    base_unit: tick              # display name for a single tick
    pre_epoch_behavior: clamp    # "clamp" (floor at 0) or "allow" (permit negative game_ticks)
    cycles:
      - type: ticks              # required root cycle — one per game
        name: tick
      - type: cycle              # derived cycle: 4 ticks = 1 day
        name: day
        parent: tick
        count: 4
        labels:
          - Dawn
          - Noon
          - Dusk
          - Midnight
      - type: cycle              # derived cycle: 7 days = 1 week
        name: week
        parent: day
        count: 7
        labels:
          - Monday
          - Tuesday
          - Wednesday
          - Thursday
          - Friday
          - Saturday
          - Sunday
    epoch:
      day: Dawn                  # calendar shows "Dawn" at game_ticks = 0
      year: 1                    # year counter starts at 1
    eras:
      - name: age-of-the-empire
        format: "Year {count} AE"
        epoch_count: 298         # counter starts at 298 instead of 1
        tracks: year             # increments when a "year" cycle completes
        start_condition:
          type: milestone
          name: empire-founded
        end_condition:
          type: milestone
          name: empire-fallen
```

### Cycles

Cycles form a hierarchy. The **root cycle** (`type: ticks`) is the base unit — all other cycles derive from it. Each derived cycle declares a `parent` and a `count` (how many parent units equal one of this cycle). Cycles can chain to arbitrary depth (`tick → hour → day → month → year`).

- `labels` is optional. If provided, the count must match the number of labels exactly.
- `epoch` shifts the display calendar so `game_ticks = 0` shows the named starting position. Values are label strings or 1-based integers.

### Eras

An era is a named counter that activates under a condition and increments whenever a tracked cycle completes.

| Field             | Description                                                                                          |
| ----------------- | ---------------------------------------------------------------------------------------------------- |
| `name`            | Identifier — used in `game_calendar_era_is` conditions and `ingame_time.eras` in templates.          |
| `format`          | Python `str.format`-style string with `{count}` — e.g. `"Year {count} AE"`.                         |
| `epoch_count`     | Starting counter value (default: 1). Use `298` to begin at "Year 298 AE".                           |
| `tracks`          | Name of the cycle whose completions increment the counter.                                            |
| `start_condition` | Condition that activates the era (latch: fires at most once). Absent → active from tick 0.           |
| `end_condition`   | Condition that permanently deactivates the era (latch: fires at most once). Absent → never ends.     |

### Time-based conditions

Three condition types are available when the time system is configured. They return `false` with a warning if the system is not enabled.

```yaml
# True once 100 internal ticks have passed
requires:
  type: game_calendar_time_is
  clock: internal      # "internal" | "game"
  gte: 100

# True every 4 game ticks (e.g., at the start of each new day)
requires:
  type: game_calendar_time_is
  clock: game
  mod:
    divisor: 4
    remainder: 0

# True when the current day label is "Dawn"
requires:
  type: game_calendar_cycle_is
  cycle: day
  value: Dawn

# True when a named era is active
requires:
  type: game_calendar_era_is
  era: age-of-the-empire
  state: active         # "active" | "inactive"
```

### `adjust_game_ticks` effect

Moves `game_ticks` forward or backward. Does **not** affect `internal_ticks`.

```yaml
effects:
  - type: adjust_game_ticks
    delta: 8     # skip forward 8 ticks (e.g., two days at ticks_per_day: 4)

  - type: adjust_game_ticks
    delta: -4    # rewind 4 ticks (with pre_epoch_behavior: allow)
```

With `pre_epoch_behavior: clamp` (default), backward adjustments are floored at 0.

### Templates

When the time system is configured, `ingame_time` is available in all narrative templates. It is `None` when the system is not enabled — always guard with `{% if ingame_time %}`.

```jinja
{% if ingame_time %}
It is {{ ingame_time.cycles['day'].label }} of {{ ingame_time.cycles['week'].label }}.
{{ ingame_time.eras['age-of-the-empire'].count }} AE
Internal ticks: {{ ingame_time.internal_ticks }}
{% endif %}
```

| Attribute                     | Description                                                   |
| ----------------------------- | ------------------------------------------------------------- |
| `ingame_time.internal_ticks`  | Monotone tick counter (never adjusted by effects).            |
| `ingame_time.game_ticks`      | Narrative tick counter (adjustable by `adjust_game_ticks`).   |
| `ingame_time.cycles['name']`  | `CycleState` with `.name`, `.position` (0-based), `.label`.  |
| `ingame_time.eras['name']`    | `EraState` with `.name`, `.count`, `.active` (bool).          |

---

## Cooldowns

A `cooldown:` block can be placed on `Adventure` or `Skill` manifests. All fields are optional but at least one must be present.

```yaml
cooldown:
  ticks: 5           # internal ticks (one per adventure completed)
  game_ticks: 10     # in-game calendar ticks (requires time system)
  seconds: 3600      # real-world seconds; supports templates ({{ SECONDS_PER_HOUR * 6 }})
  # Skills only:
  scope: turn
  turns: 1           # requires scope: turn; per-combat cooldown
```

`ticks`, `game_ticks`, and `seconds` cannot be combined with `scope: turn`.

---

## Passive Effects

Declare passive effects in `game.yaml` under `spec.passive_effects`. They apply automatically while the condition is true.

```yaml
passive_effects:
  - condition:
      type: milestone
      name: hero-of-the-realm
    stat_modifiers:
      - stat: charisma
        amount: 2
    skill_grants:
      - inspire

  # No condition = always applies
  - stat_modifiers:
      - stat: max_hp
        amount: 5
```

**Restrictions**: do not use `character_stat` with `stat_source: effective` or `skill` conditions in passive effects — they cause circular evaluation errors at load time.

---


## Manifest Reference

> **Before writing any manifest, you MUST retrieve its JSON Schema.**
> Field names, required fields, and allowed values vary by kind and are the authoritative source of truth. Do not rely on examples alone — pull the schema from the CLI:
>
> ```bash
> uv run oscilla content schema <kind>   # single kind, printed to stdout
> uv run oscilla content schema          # all kinds as a combined JSON object
> ```
>
> Examples: `uv run oscilla content schema adventure`, `uv run oscilla content schema item`, `uv run oscilla content schema character-config`
>
> To enable live inline validation in VS Code (flags invalid fields as you type):
> ```bash
> uv run oscilla content schema --output schemas/ --vscode
> ```
> See the `oscilla-content-cli` skill for full schema and editor setup instructions.

Every manifest uses the same envelope:

```yaml
apiVersion: oscilla/v1
kind: <Kind>
metadata:
  name: kebab-case-identifier   # unique within its kind across the package
spec:
  # kind-specific fields — always check the schema first
```

`metadata.name` is the identifier used for **all** cross-references across the package. Use lowercase kebab-case.

Multiple manifests of any kind may share a single `.yaml` file, separated by `---`.

### Kind Quick Reference

| Kind              | CLI schema name    | When to create one                                                                               |
| ----------------- | ------------------ | ------------------------------------------------------------------------------------------------ |
| `Game`            | `game`             | **Required.** Once per package. Defines triggers, item categories, passive effects, time system. |
| `CharacterConfig` | `character-config` | **Required.** Once per package. Defines all stats, equipment slots, and pronoun sets.            |
| `Region`          | `region`           | Any named area of the world. Regions can nest; all locations belong to a region.                 |
| `Location`        | `location`         | Any place where the player can land and have adventures. Holds a weighted adventure pool.        |
| `Adventure`       | `adventure`        | Any interactive encounter: NPC dialogue, exploration, combat setup, multi-step choices.          |
| `Enemy`           | `enemy`            | Any named opponent used in a `combat` adventure step.                                            |
| `Item`            | `item`             | Any inventory object: consumable, weapon, armor, crafting material, quest token.                 |
| `Skill`           | `skill`            | Any activatable ability the player can use in combat or the overworld.                           |
| `Buff`            | `buff`             | A temporary effect applied by `apply_buff`. Modifies stats for a number of combat turns.         |
| `Archetype`       | `archetype`        | A persistent character state. Grants passives and skills on acquisition; reversed on removal.    |
| `Quest`           | `quest`            | A multi-stage storyline tracked on the character. Stages advance on milestone grants.            |
| `LootTable`       | `loot-table`       | A reusable weighted drop pool shared by multiple enemies or adventures.                          |
| `Recipe`          | `recipe`           | A crafting formula: consume N items as inputs, receive output items.                             |
| `CustomCondition` | `custom-condition` | A named reusable condition referenced as `type: custom, name: <name>`.                           |

---

### `Game` — `game.yaml`

Required. Defines game rules: progression triggers, item categories, passive effects, in-game time.

```yaml
apiVersion: oscilla/v1
kind: Game
metadata:
  name: my-kingdom         # must match the package directory name
spec:
  displayName: "My Kingdom"
  description: "A text-based medieval adventure."

  # Fire adventures when a stat crosses a threshold
  triggers:
    on_stat_threshold:
      - stat: xp
        threshold: 100
        trigger: level-2-reached   # name of a trigger_adventure
      - stat: xp
        threshold: 300
        trigger: level-3-reached

  # Adventures run automatically for triggers
  trigger_adventures:
    level-2-reached: level-up-2
    level-3-reached: level-up-3

  # Run an adventure automatically when a new character is created
  on_character_create: initialize-character

  # Game-wide passive modifiers (see Passive Effects section)
  passive_effects: []

  # Vocabulary of valid item category strings (optional; validated on items)
  item_categories:
    - weapon
    - armor
    - consumable
    - quest
```

XP thresholds and HP are not special engine fields — they are implemented entirely through the stat and trigger systems. See [game-configuration.md](../../docs/authors/game-configuration.md) for a complete worked example.

---

### `CharacterConfig` — `character_config.yaml`

Required. Defines player stats, equipment slots, and pronoun options.

```yaml
apiVersion: oscilla/v1
kind: CharacterConfig
metadata:
  name: my-kingdom-character
spec:
  public_stats:
    - name: level
      type: int
      default: 1
      bounds:
        min: 1
      description: "Character level."

    - name: xp
      type: int
      default: 0
      bounds:
        min: 0

    - name: hp
      type: int
      default: 20
      bounds:
        min: 0

    - name: max_hp
      type: int
      derived: "{{ 10 + player.stats['level'] * 5 }}"
      description: "Computed from level."

    - name: strength
      type: int
      default: 10

    - name: gold
      type: int
      default: 0
      bounds:
        min: 0

  equipment_slots:
    - name: weapon
      label: "Weapon"
    - name: armor
      label: "Armor"

  pronoun_sets:
    - name: they
      subject: they
      object: them
      possessive: their
      possessive_standalone: theirs
      reflexive: themselves
    - name: she
      subject: she
      object: her
      possessive: her
      possessive_standalone: hers
      reflexive: herself
    - name: he
      subject: he
      object: him
      possessive: his
      possessive_standalone: his
      reflexive: himself
```

**Stat types**: `int`, `float`, `str`, `bool`. Use `derived:` for computed stats — it is a Jinja2 expression string with `{{ }}` brackets required. Access other stats via `player.stats['name']`. Example: `derived: "{{ 10 + player.stats['level'] * 5 }}"`. `bool` stats cannot be derived.

**String stats must have an explicit `default` value** (even `""`) — a null default means the stat is not present in the character's stats dict, which causes runtime errors when adventures reference it.

---

### `Region`

A named area containing locations. Regions can nest with `parent`.

```yaml
apiVersion: oscilla/v1
kind: Region
metadata:
  name: the-forest
spec:
  displayName: "The Forest"
  description: "Ancient woodland that hides many dangers."
  # Optional: lock the region behind a condition
  unlock:
    type: milestone
    name: found-the-forest
  # Optional: nest inside another region
  # parent: wilderness
```

---

### `Location`

A place within a region where adventures happen. Each location has an adventure pool — weighted entries that the engine draws from when the player arrives.

```yaml
apiVersion: oscilla/v1
kind: Location
metadata:
  name: hunters-camp
spec:
  displayName: "Hunter's Camp"
  description: "A rough camp at the forest edge."
  region: the-forest       # must match a Region metadata.name

  adventures:
    - ref: wolf-ambush     # Adventure metadata.name
      weight: 60
    - ref: lost-traveler
      weight: 30
    - ref: quiet-night
      weight: 10

  # Optional: starting location for new characters
  # starting_location: true

  # Optional: lock behind a condition
  # unlock:
  #   type: level
  #   value: 3
```

The engine selects one adventure at random (weighted) each time the player enters the location. Adventures not in any pool will produce an orphaned-adventure warning on validation.

---

### `Adventure`

An interactive encounter. Adventures are sequences of steps.

```yaml
apiVersion: oscilla/v1
kind: Adventure
metadata:
  name: wolf-ambush
spec:
  displayName: "Wolf Ambush"
  description: "A pack of wolves blocks the trail."

  # Optional: condition required to appear in pool
  requires:
    type: level
    value: 2

  # Optional: allow the adventure to repeat
  repeatable: true
  max_completions: 10    # optional cap on repeats
  cooldown:
    ticks: 3             # adventures that must complete before this can repeat

  steps:
    - type: narrative
      text: |
        Three wolves emerge from the undergrowth, growling.
      effects:
        - type: milestone_grant
          milestone: encountered-wolves

    - type: choice
      prompt: "What do you do?"
      options:
        - text: "Fight"
          effects:
            - type: stat_change
              stat: xp
              amount: 10
        - text: "Run"
          requires:
            type: character_stat
            stat: agility
            value: 8
          effects:
            - type: stat_change
              stat: hp
              amount: -5

    - type: combat
      enemy: forest-wolf
      on_win:
        effects:
          - type: stat_change
            stat: xp
            amount: 75
        steps:
          - type: narrative
            text: "The wolves scatter. You catch your breath."
      on_defeat:
        steps:
          - type: narrative
            text: "The wolves overwhelm you."
      on_flee:
        steps:
          - type: narrative
            text: "You sprint back to the road."

    - type: ack
      text: "The forest falls quiet again."
```

**Step types**:

| Type         | Purpose                                                      |
| ------------ | ------------------------------------------------------------ |
| `narrative`  | Display text; optional effects fire on player acknowledgment |
| `choice`     | Branching menu; each option has text, optional `requires`, and effects |
| `combat`     | Turn-based fight; branches `on_win`, `on_defeat`, `on_flee`  |
| `ack`        | Display text and wait for player to continue; no branching   |
| `text_input` | Collect free-text from the player; store via effects         |
| `skill_menu` | Show combat skill grid (used inside combat sub-steps)        |

---

### `Enemy`

A combat opponent referenced by `combat` steps.

```yaml
apiVersion: oscilla/v1
kind: Enemy
metadata:
  name: forest-wolf
spec:
  displayName: "Forest Wolf"
  description: "A lean, grey wolf with yellow eyes."
  hp: 25
  attack: 8
  defense: 2
  xp_reward: 75
  loot:
    - count: 1
      method: weighted
      entries:
        - item: wolf-pelt
          weight: 60
        - item: wolf-fang
          weight: 30
        - item: nothing         # use an item with no value for "empty" drops
          weight: 10
  # Optional: skills the enemy can use in combat
  skills:
    - savage-bite
```

Combat damage per round: roughly `attacker.attack - defender.defense`, minimum 1.

---

### `Item`

Anything the player can carry, use, equip, or trade.

```yaml
# Consumable
apiVersion: oscilla/v1
kind: Item
metadata:
  name: healing-potion
spec:
  displayName: "Healing Potion"
  description: "A red vial that mends wounds."
  category: consumable
  stackable: true
  consumed_on_use: true
  value: 50
  use_effects:
    - type: heal
      amount: 30

---
# Equipment
apiVersion: oscilla/v1
kind: Item
metadata:
  name: iron-sword
spec:
  displayName: "Iron Sword"
  description: "A serviceable blade."
  category: weapon
  stackable: false
  value: 120
  equip:
    slot: weapon
    stat_modifiers:
      - stat: strength
        amount: 3
    requires:              # optional equip gate
      type: level
      value: 3
```

**Key item fields**:

| Field              | Purpose                                           |
| ------------------ | ------------------------------------------------- |
| `stackable`        | Multiple copies share one inventory slot          |
| `consumed_on_use`  | Item is removed after `use_effects` fire          |
| `charges`          | Item has N uses before being removed (not stackable) |
| `use_effects`      | Effects that fire when the player uses the item   |
| `equip.slot`       | Which equipment slot the item occupies            |
| `equip.stat_modifiers` | Passive stat bonuses while equipped           |

---

### `Skill`

An activatable ability usable in combat, the overworld, or both.

```yaml
apiVersion: oscilla/v1
kind: Skill
metadata:
  name: quick-heal
spec:
  displayName: "Quick Heal"
  description: "Bind minor wounds mid-battle."
  contexts:
    - combat       # "combat" | "overworld" | both
  cost:
    stat: mana
    amount: 15
  cooldown:
    scope: turn
    turns: 1       # once per combat turn
  use_effects:
    - type: heal
      amount: 25
      target: player
```

Skill `requires` is evaluated every time the player attempts to activate it — not just at grant time. Use it to gate skills behind stat thresholds or milestones.

---

### `Archetype`

A named persistent state attached to a character. Grants passive bonuses and skills while held.

```yaml
apiVersion: oscilla/v1
kind: Archetype
metadata:
  name: warrior
spec:
  displayName: "Warrior"
  description: "A trained combatant."
  # Effects fire once when archetype is granted
  gain_effects:
    - type: stat_change
      stat: strength
      amount: 5
  # Effects fire once when archetype is removed
  lose_effects:
    - type: stat_change
      stat: strength
      amount: -5
  # Always-on modifiers while held
  passive_effects:
    - stat_modifiers:
        - stat: strength
          amount: 2
      skill_grants:
        - power-attack
```

Grant archetypes with the `archetype_grant` effect; revoke with `archetype_revoke`.

---

### `Quest`

A multi-stage storyline tracked on the player. Stages advance when the player earns specific milestones.

```yaml
apiVersion: oscilla/v1
kind: Quest
metadata:
  name: missing-merchant
spec:
  displayName: "The Missing Merchant"
  description: "Old Gregor hasn't returned from the wilderness."
  entry_stage: search-begun
  stages:
    - name: search-begun
      description: "Head into the wilderness and look for clues."
      advance_on:
        - found-gregor-camp
      next_stage: camp-found

    - name: camp-found
      description: "Gregor's camp was ransacked. Find who did it."
      advance_on:
        - defeated-bandit-leader
      next_stage: complete

    - name: complete
      description: "Justice served. Report back to the village."
      terminal: true
```

Activate a quest with the `quest_activate` effect. The engine validates the stage graph at load time — no orphan stages, no missing `next_stage` on non-terminal stages, no `next_stage` on terminal stages.

---

### `LootTable`

A reusable drop pool referenced by name. Useful when multiple enemies or adventures share the same reward pool.

```yaml
apiVersion: oscilla/v1
kind: LootTable
metadata:
  name: forest-drops
spec:
  displayName: "Forest Drops"
  description: "Common woodland loot."
  groups:
    - count: 1
      method: weighted
      entries:
        - item: healing-herb
          weight: 60
          amount: 2
        - item: wolf-pelt
          weight: 30
        - item: silver-coin
          weight: 10
          amount: 5
```

Reference with `loot_ref: forest-drops` in an `item_drop` effect.

---

### `Recipe`

A crafting formula: consume ingredient items, receive an output item.

```yaml
apiVersion: oscilla/v1
kind: Recipe
metadata:
  name: brew-healing-potion
spec:
  displayName: "Brew Healing Potion"
  description: "Combine herbs and water into a restorative draught."
  inputs:
    - item: healing-herb
      quantity: 2
    - item: water-flask
      quantity: 1
  output:
    item: healing-potion
    quantity: 1
```

All items in `inputs` and `output` must match loaded Item manifest names.


---

## Examples

The examples below form a single cohesive game package — **Ironvale** — where goblin incursions have disrupted an iron mining operation. Every manifest cross-references the others: enemies use shared loot tables, adventures activate quests and grant archetypes, archetypes unlock skills, and conditions gate content on quest stage and player level.

Read through all of these before writing manifests for a new package. Run `uv run oscilla content schema <kind>` to get exact field details for any kind shown here.

---

### Foundation

These two files are **required** at the package root.

**`content/ironvale/game.yaml`** — global rules, triggers, item categories:

```yaml
apiVersion: oscilla/v1
kind: Game
metadata:
  name: ironvale
spec:
  displayName: "Ironvale"
  description: "A mining town beset by goblin incursions."

  on_character_create: new-arrival

  triggers:
    on_stat_threshold:
      - stat: xp
        threshold: 100
        trigger: reached-level-2
      - stat: xp
        threshold: 300
        trigger: reached-level-3

  trigger_adventures:
    reached-level-2: level-up-2
    reached-level-3: level-up-3

  item_categories:
    - weapon
    - armor
    - consumable
    - material
    - quest
```

`on_character_create` names an adventure that runs automatically for every new character (here, `new-arrival` — which should grant the `arrived-in-ironvale` milestone that unlocks the region). `trigger_adventures` maps trigger names to adventure names; all referenced adventures must exist in the package.

---

**`content/ironvale/character_config.yaml`** — stats, equipment slots, pronoun sets:

```yaml
apiVersion: oscilla/v1
kind: CharacterConfig
metadata:
  name: ironvale-character
spec:
  public_stats:
    - name: level
      type: int
      default: 1
      bounds:
        min: 1

    - name: xp
      type: int
      default: 0
      bounds:
        min: 0

    - name: hp
      type: int
      default: 20
      bounds:
        min: 0

    - name: max_hp
      type: int
      derived: "{{ 10 + player.stats['level'] * 5 }}"

    - name: strength
      type: int
      default: 8

    - name: defense
      type: int
      default: 3

    - name: gold
      type: int
      default: 0
      bounds:
        min: 0

  equipment_slots:
    - name: weapon
      label: "Weapon"
    - name: armor
      label: "Armor"

  pronoun_sets:
    - name: they
      subject: they
      object: them
      possessive: their
      possessive_standalone: theirs
      reflexive: themselves
    - name: she
      subject: she
      object: her
      possessive: her
      possessive_standalone: hers
      reflexive: herself
    - name: he
      subject: he
      object: him
      possessive: his
      possessive_standalone: his
      reflexive: himself
```

`max_hp` is derived — no `default:` needed; the formula runs on every stat access. `bounds.min: 0` on `hp` prevents the value going below zero.

---

### World Structure

**`content/ironvale/regions/the-mines/the-mines.yaml`** — the mine region, locked until the player arrives in town:

```yaml
apiVersion: oscilla/v1
kind: Region
metadata:
  name: the-mines
spec:
  displayName: "The Mines"
  description: "A network of tunnels beneath Ironvale, rich in iron ore — and recently, goblins."
  unlock:
    type: milestone
    name: arrived-in-ironvale
```

The region is locked until `arrived-in-ironvale` is granted, which the `new-arrival` adventure (fired by `on_character_create`) should do.

---

**`content/ironvale/regions/the-mines/locations/mine-entrance/mine-entrance.yaml`** — starting location:

```yaml
apiVersion: oscilla/v1
kind: Location
metadata:
  name: mine-entrance
spec:
  displayName: "Mine Entrance"
  description: "The main shaft opening. Lanterns flicker in the draft from below."
  region: the-mines
  adventures:
    - ref: meet-the-foreman
      weight: 80
    - ref: tunnel-patrol
      weight: 60
    - ref: vault-discovery
      weight: 20
```

`meet-the-foreman` has `repeatable: false` — it drops out of the pool automatically after the first completion. `vault-discovery` has a `requires` condition (milestone `met-foreman`) so it is filtered from the pool until that milestone is held.

---

**`content/ironvale/regions/the-mines/locations/deep-tunnels/deep-tunnels.yaml`** — high-level locked location:

```yaml
apiVersion: oscilla/v1
kind: Location
metadata:
  name: deep-tunnels
spec:
  displayName: "Deep Tunnels"
  description: "The lower shafts. Reinforced goblin barricades block the main passage."
  region: the-mines
  unlock:
    type: level
    value: 3
  adventures:
    - ref: rescue-the-miners
      weight: 40
    - ref: tunnel-patrol
      weight: 60
```

The location is locked until level 3. `rescue-the-miners` has a `requires` condition (quest stage) so it is filtered until the quest is active. `tunnel-patrol` is the same adventure manifest referenced in both locations — the same adventure can appear in any number of location pools.

---

### Enemies

**`content/ironvale/enemies/enemies.yaml`** — two enemies in one file:

```yaml
apiVersion: oscilla/v1
kind: Enemy
metadata:
  name: mine-goblin
spec:
  displayName: "Mine Goblin"
  description: "A wiry goblin that has claimed the upper tunnels as its territory."
  hp: 18
  attack: 6
  defense: 1
  xp_reward: 40

---

apiVersion: oscilla/v1
kind: Enemy
metadata:
  name: goblin-warchief
spec:
  displayName: "Goblin Warchief"
  description: "Twice the size of a standard goblin, wielding a stolen iron maul."
  hp: 55
  attack: 14
  defense: 4
  xp_reward: 200
  loot:
    - count: 2
      method: weighted
      entries:
        - item: iron-ore
          weight: 40
          amount: 2
        - item: goblin-tooth
          weight: 35
        - item: miner-potion
          weight: 25
```

`mine-goblin` has no inline loot — drops are handled by the adventure's `on_win` effects (using `loot_ref: mine-drops`). `goblin-warchief` has inline loot that fires automatically when the enemy is defeated in combat, in addition to any `item_grant` effects in the adventure's `on_win` block.

---

### Items

**`content/ironvale/items/items.yaml`** — all items in one file:

```yaml
apiVersion: oscilla/v1
kind: Item
metadata:
  name: iron-ore
spec:
  displayName: "Iron Ore"
  description: "Rough chunks of iron-rich rock. Required for forging."
  category: material
  stackable: true
  value: 5

---

apiVersion: oscilla/v1
kind: Item
metadata:
  name: goblin-tooth
spec:
  displayName: "Goblin Tooth"
  description: "A worn fang. The village tooth-collector pays well for these."
  category: material
  stackable: true
  value: 8

---

apiVersion: oscilla/v1
kind: Item
metadata:
  name: miner-potion
spec:
  displayName: "Miner's Potion"
  description: "A bitter brew that restores stamina and stitches minor wounds."
  category: consumable
  stackable: true
  consumed_on_use: true
  value: 25
  use_effects:
    - type: heal
      amount: 20

---

apiVersion: oscilla/v1
kind: Item
metadata:
  name: miners-pick
spec:
  displayName: "Miner's Pick"
  description: "A heavy iron pick, repurposed as a weapon by necessity."
  category: weapon
  stackable: false
  value: 40
  equip:
    slot: weapon
    stat_modifiers:
      - stat: strength
        amount: 3

---

apiVersion: oscilla/v1
kind: Item
metadata:
  name: forged-sword
spec:
  displayName: "Forged Iron Sword"
  description: "A proper sword, smelted from ore recovered in the mines. Requires training to wield."
  category: weapon
  stackable: false
  value: 150
  equip:
    slot: weapon
    stat_modifiers:
      - stat: strength
        amount: 7
    requires:
      type: level
      value: 3

---

apiVersion: oscilla/v1
kind: Item
metadata:
  name: ancient-sigil
spec:
  displayName: "Ancient Sigil"
  description: "A palm-sized obsidian tablet carved with symbols no one in Ironvale can read."
  category: quest
  stackable: false
  value: 0
```

`miners-pick` has no equip requirements — any level can use it. `forged-sword` uses `requires:` nested under `equip:` to set a level gate. `ancient-sigil` is a quest item with no `use_effects` — it just sits in the inventory.

---

### Loot Tables

**`content/ironvale/loot-tables/mine-drops.yaml`** — shared drop pool referenced by `tunnel-patrol`:

```yaml
apiVersion: oscilla/v1
kind: LootTable
metadata:
  name: mine-drops
spec:
  displayName: "Mine Drops"
  description: "Common loot found on goblin patrols."
  groups:
    - count: 1
      method: weighted
      entries:
        - item: iron-ore
          weight: 55
          amount: 2
        - item: goblin-tooth
          weight: 30
        - item: miner-potion
          weight: 15
```

Referenced via `loot_ref: mine-drops` in adventure `on_win` effects. Multiple adventures and enemies can share this table. The `amount: 2` on `iron-ore` means two ore are granted when that entry is selected.

---

### Adventures

**`content/ironvale/regions/the-mines/locations/mine-entrance/adventures/meet-the-foreman.yaml`** — one-time adventure that activates the quest:

```yaml
apiVersion: oscilla/v1
kind: Adventure
metadata:
  name: meet-the-foreman
spec:
  displayName: "The Foreman's Warning"
  description: "The mine foreman flags you down at the shaft entrance."
  repeatable: false

  steps:
    - type: narrative
      text: |
        Torvar pulls you aside, his face lined with worry. "Thank the gods — a capable-looking
        sort. We've had miners go missing in the lower tunnels. Three men, two days ago.
        The goblins have gotten bold."
      effects:
        - type: milestone_grant
          milestone: met-foreman

    - type: choice
      prompt: "How do you respond?"
      options:
        - text: "I'll look into it."
          effects:
            - type: quest_activate
              quest: lost-miners
            - type: stat_change
              stat: xp
              amount: 10
        - text: "Sounds like someone else's problem."

    - type: ack
      text: "Torvar watches you go with uncertainty in his eyes."
```

The `narrative` step fires `milestone_grant` effects when the player acknowledges it — before the choice appears. The second choice option has no `effects:` — the player can decline and the quest is never activated. `repeatable: false` ensures this adventure disappears from the pool after the first completion.

---

**`content/ironvale/regions/the-mines/locations/mine-entrance/adventures/tunnel-patrol.yaml`** — repeatable combat shared across both locations:

```yaml
apiVersion: oscilla/v1
kind: Adventure
metadata:
  name: tunnel-patrol
spec:
  displayName: "Tunnel Patrol"
  description: "A routine sweep through the mine shafts."
  repeatable: true
  cooldown:
    ticks: 1

  steps:
    - type: narrative
      text: |
        Lantern held high, you move through the carved stone passages.
        The air smells of sulfur and wet rock. Then — the scrape of claws.

    - type: combat
      enemy: mine-goblin
      on_win:
        effects:
          - type: stat_change
            stat: xp
            amount: 40
          - type: item_drop
            loot_ref: mine-drops
        steps:
          - type: ack
            text: "The goblin crumples. You search its pack."
      on_defeat:
        steps:
          - type: narrative
            text: |
              The goblin's blade finds a gap in your guard. You break away and retreat
              up the shaft, battered but alive.
      on_flee:
        steps:
          - type: ack
            text: "You fall back to safer ground."

    - type: ack
      text: "The tunnel is clear — for now."
```

`cooldown: ticks: 1` means one other adventure must complete before this one is available again. `loot_ref: mine-drops` pulls from the shared loot table. This adventure file is referenced in **both** `mine-entrance` and `deep-tunnels` location pools — the same manifest, no duplication.

---

**`content/ironvale/regions/the-mines/locations/deep-tunnels/adventures/rescue-the-miners.yaml`** — quest-gated boss fight with archetype grant:

```yaml
apiVersion: oscilla/v1
kind: Adventure
metadata:
  name: rescue-the-miners
spec:
  displayName: "The Missing Miners"
  description: "Deep in the tunnels, you hear voices — and snarling."
  requires:
    type: quest_stage
    quest: lost-miners
    stage: searching
  repeatable: false

  steps:
    - type: narrative
      text: |
        Rounding a corner in the deep tunnels, you find three miners huddled in a dead end,
        a massive goblin blocking the only way out. The warchief — it has to be.

    - type: combat
      enemy: goblin-warchief
      on_win:
        effects:
          - type: milestone_grant
            milestone: rescued-miners
          - type: archetype_grant
            archetype: ironworker
          - type: stat_change
            stat: xp
            amount: 200
          - type: item_grant
            item: miners-pick
        steps:
          - type: ack
            text: |
              The warchief crashes to the ground. The miners scramble to their feet.
              One of them presses a pick into your hands. "Take it. You've earned it."
      on_defeat:
        steps:
          - type: narrative
            text: |
              The warchief drives you back with a crushing blow. You retreat to the surface;
              the miners' cries echo behind you. You can try again.
      on_flee:
        steps:
          - type: ack
            text: "You break for the exit. The warchief lets out a rattling war cry behind you."
```

The `requires` condition (`quest_stage`) filters this adventure from the pool until the quest is active at stage `searching`. On winning: `milestone_grant` advances the quest (the quest's `searching` stage lists `rescued-miners` in `advance_on`); `archetype_grant` gives the `ironworker` archetype; `item_grant` guarantees `miners-pick` as a reward on top of the warchief's inline loot.

---

**`content/ironvale/regions/the-mines/locations/mine-entrance/adventures/vault-discovery.yaml`** — milestone-gated discovery with a stat-gated choice option:

```yaml
apiVersion: oscilla/v1
kind: Adventure
metadata:
  name: vault-discovery
spec:
  displayName: "The Carved Door"
  description: "A door unlike anything the miners made, set into the stone."
  requires:
    type: milestone
    name: met-foreman
  repeatable: false

  steps:
    - type: narrative
      text: |
        Behind a partially-collapsed section of the east tunnel, you find a door of
        carved obsidian — far older than any mine. Strange symbols run along its frame.

    - type: choice
      prompt: "What do you do?"
      options:
        - text: "Force it open."
          requires:
            type: character_stat
            name: strength
            gte: 12
          effects:
            - type: milestone_grant
              milestone: opened-vault
            - type: item_grant
              item: ancient-sigil
            - type: stat_change
              stat: xp
              amount: 75
        - text: "Mark the location and move on."
          effects:
            - type: milestone_grant
              milestone: found-vault-door

    - type: ack
      text: "You continue through the tunnels."
```

`requires: milestone: met-foreman` prevents this adventure from appearing until `meet-the-foreman` has been completed. The first choice option is gated on `strength ≥ 12` — the option is **hidden** from players who don't meet the condition, not just disabled. The second option is always available as a fallback.

---

### Quest

**`content/ironvale/quests/lost-miners.yaml`** — two-stage quest activated by `meet-the-foreman`:

```yaml
apiVersion: oscilla/v1
kind: Quest
metadata:
  name: lost-miners
spec:
  displayName: "Lost in the Dark"
  description: "Three of Torvar's miners went missing in the lower tunnels two days ago."
  entry_stage: searching
  stages:
    - name: searching
      description: "The missing miners were last seen heading toward the deep tunnels. Find them and deal with whatever took them."
      advance_on:
        - rescued-miners
      next_stage: complete

    - name: complete
      description: "The missing miners have been found and the goblin threat driven back."
      terminal: true
```

Activated by `quest_activate` in `meet-the-foreman`. Advances when the `rescued-miners` milestone is granted — which happens in `rescue-the-miners` on_win. `terminal: true` marks a stage as an endpoint; it must not have a `next_stage`.

---

### Archetype

**`content/ironvale/archetypes/ironworker.yaml`** — granted on quest completion, provides permanent bonuses and unlocks a skill:

```yaml
apiVersion: oscilla/v1
kind: Archetype
metadata:
  name: ironworker
spec:
  displayName: "Ironworker"
  description: "Forged by the trials beneath Ironvale. You carry the weight of the mines — and its strength."
  gain_effects:
    - type: stat_change
      stat: defense
      amount: 3
    - type: stat_change
      stat: strength
      amount: 2
  lose_effects:
    - type: stat_change
      stat: defense
      amount: -3
    - type: stat_change
      stat: strength
      amount: -2
  passive_effects:
    - skill_grants:
        - power-strike
      stat_modifiers:
        - stat: defense
          amount: 1
```

`gain_effects` fire once when the archetype is granted. `lose_effects` reverse those permanent stat changes if the archetype is ever revoked. `passive_effects` are always-on while the archetype is held: `skill_grants` makes `power-strike` available to the player, and the `stat_modifiers` add +1 defense on top of the `gain_effects` boost.

---

### Skills and Buffs

**`content/ironvale/skills/power-strike.yaml`** — combat skill unlocked by the `ironworker` archetype:

```yaml
apiVersion: oscilla/v1
kind: Skill
metadata:
  name: power-strike
spec:
  displayName: "Power Strike"
  description: "Channel your strength into a single devastating blow."
  contexts:
    - combat
  cooldown:
    scope: turn
    turns: 2
  use_effects:
    - type: apply_buff
      buff_ref: focused-strike
      duration: 1
```

`contexts: [combat]` means this skill can only be activated inside a `combat` step. `cooldown: scope: turn, turns: 2` allows use once every two combat turns. The effect applies the `focused-strike` buff for 1 turn.

---

**`content/ironvale/buffs/focused-strike.yaml`** — temporary stat buff applied by `power-strike`:

```yaml
apiVersion: oscilla/v1
kind: Buff
metadata:
  name: focused-strike
spec:
  displayName: "Focused Strike"
  description: "Your next strike hits with unusual force."
  stat_modifiers:
    - stat: strength
      amount: 5
```

The `Buff` manifest defines what the buff does; the `apply_buff` effect in the skill controls how long it lasts (`duration: 1` combat turn). Always run `uv run oscilla content schema buff` to verify the exact buff spec fields.

---

### Recipe

**`content/ironvale/recipes/forge-iron-sword.yaml`** — converts dropped ore into a craftable weapon:

```yaml
apiVersion: oscilla/v1
kind: Recipe
metadata:
  name: forge-iron-sword
spec:
  displayName: "Forge Iron Sword"
  description: "Smelt down iron ore in Ironvale's forge to produce a serviceable blade."
  inputs:
    - item: iron-ore
      quantity: 4
  output:
    item: forged-sword
    quantity: 1
```

`iron-ore` drops from `mine-goblin` combat via the `mine-drops` loot table. After accumulating 4, the player can craft `forged-sword` — the level-3 weapon with +7 strength. All `item` names in `inputs` and `output` must match existing Item manifest names.

---

### Custom Condition

**`content/ironvale/conditions/is-on-rescue-quest.yaml`** — reusable named condition for checking quest state:

```yaml
apiVersion: oscilla/v1
kind: CustomCondition
metadata:
  name: is-on-rescue-quest
spec:
  displayName: "Rescue Quest Active"
  condition:
    type: quest_stage
    quest: lost-miners
    stage: searching
```

Reference this anywhere as `type: custom, name: is-on-rescue-quest` instead of repeating the full `quest_stage` condition inline. Useful when the same gate is needed across multiple adventures, item requirements, or passive effects.

---

## Validation Workflow

Always validate before considering content complete:

```bash
# Validate all packages
uv run oscilla validate

# Validate one package only (pass the game name, not a file path)
uv run oscilla validate --game my-kingdom

# Treat warnings as errors (recommended before shipping)
uv run oscilla validate --game my-kingdom --strict
```

> **IMPORTANT:** `oscilla validate` accepts **no positional arguments**. Always use `--game <name>` (or `-g <name>`). Passing a path (e.g. `content/my-kingdom`) will fail.

A clean run looks like:

```
✓ my-kingdom: 3 regions, 8 locations, 12 adventures, 4 enemies, 10 items, 2 quests
```

Errors must be fixed. Warnings (like orphaned adventures) are advisory but worth addressing. See the `oscilla-content-cli` skill for the full validation, inspection, and scaffolding command reference.

---

## Common Gotchas

- **`metadata.name` must match the package directory name** in `game.yaml` only — everywhere else, names are cross-references and have no path requirement.
- **String stats need explicit defaults** — `default: ""` not `default:` (null). Null defaults mean the stat is missing from the character dict at runtime.
- **Adventures must be in a location pool to appear** — referencing an adventure manifest in `location.adventures` (by `ref:`) is what makes it available. Having the file on disk is not enough.
- **Effect amounts can be templates** — `amount: "{{ roll(10, 30) }}"` is valid on `stat_change`, `heal`, cooldown fields, and others.
- **Conditions nest freely** — `all`, `any`, and `not` can contain each other at any depth.
- **`loot_ref` vs inline `loot`** — use `loot_ref` to share a `LootTable` manifest; use inline `loot` for a single-use pool.

---

## Further Reading

- [Getting Started tutorial](../../docs/authors/getting-started.md) — build a complete minimal game from scratch
- [Game Configuration](../../docs/authors/game-configuration.md) — full `game.yaml` and `character_config.yaml` reference
- [World Building](../../docs/authors/world-building.md) — regions, locations, adventure pools
- [Adventures](../../docs/authors/adventures.md) — all step types and branching patterns
- [Conditions](../../docs/authors/conditions.md) — complete condition type reference
- [Effects](../../docs/authors/effects.md) — complete effect type reference
- [Items](../../docs/authors/items.md) — consumables, equipment, charged items
- [Enemies](../../docs/authors/enemies.md) — combat stats, loot, enemy skills
- [Skills and Buffs](../../docs/authors/skills.md) — activatable abilities and buff manifests
- [Archetypes](../../docs/authors/archetypes.md) — persistent character states
- [Quests](../../docs/authors/quests.md) — multi-stage storylines
- [Loot Tables](../../docs/authors/loot-tables.md) — reusable drop pools
- [Recipes](../../docs/authors/recipes.md) — crafting formulas
- [Templates](../../docs/authors/templates.md) — Jinja2 template reference and all globals
- [Cooldowns](../../docs/authors/cooldowns.md) — adventure and skill cooldown schema
- [Passive Effects](../../docs/authors/passive-effects.md) — game-wide always-on modifiers
- [In-Game Time](../../docs/authors/ingame-time.md) — optional calendar system
- [oscilla-content-cli skill](../oscilla-content-cli/SKILL.md) — CLI validation, inspection, and scaffolding
