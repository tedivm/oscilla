# Game Configuration

Every Oscilla content package starts with two configuration files: `game.yaml` defines the rules of your game world: XP progression, HP scaling, item category vocabulary, and game-wide stat bonuses. `character_config.yaml` defines who the player is: what stats they have, what equipment slots exist, and what pronoun options are available.

Together these two files establish the foundation everything else builds on.

---

## Package Structure

A game package is a directory anywhere under your library root (set by `GAMES_PATH`, defaulting to `content/`). The engine discovers packages by finding directories that contain a `game.yaml` file.

```
content/
└── my-kingdom/               ← your package
    ├── game.yaml             ← required
    ├── character_config.yaml ← required
    ├── regions/
    ├── adventures/
    ├── items/
    └── ...
```

The directory name becomes the package identifier players select when starting a new game.

---

## game.yaml

### Minimal Example

```yaml
apiVersion: oscilla/v1
kind: Game
metadata:
  name: my-kingdom
spec:
  displayName: "My Kingdom"
  description: "A text-based adventure in a medieval realm."
  xp_thresholds: [100, 250, 500, 900, 1400, 2100, 3000]
  hp_formula:
    base_hp: 20
    hp_per_level: 10
```

`metadata.name` must match the directory name.

### XP and Leveling

The `xp_thresholds` list defines how much total XP is required to reach each level above 1. Index 0 is level 2, index 1 is level 3, and so on.

```yaml
xp_thresholds: [100, 250, 500, 900, 1400]
```

This means:

- Level 1: 0 XP (starting level)
- Level 2: 100 XP total
- Level 3: 250 XP total
- Level 4: 500 XP total
- Level 5: 900 XP total
- Level 6: 1400 XP total

The number of entries determines the maximum level. A player who reaches the last threshold is at the game's level cap.

**Level-down mechanics:** Negative XP from effects can reduce the player's level. The engine enforces a floor of level 1 and an XP floor of 0. When a level change occurs, max HP is recalculated and current HP is capped if needed.

### HP Formula

```yaml
hp_formula:
  base_hp: 20 # HP at level 1
  hp_per_level: 10 # HP gained per level
```

Max HP = `base_hp + (level - 1) × hp_per_level`. At level 5: 20 + 4 × 10 = 60 HP.

### Item Labels

Item labels are classification tags you define — the engine never prescribes them. They appear on items, can be queried by conditions, and affect how items display in inventory.

```yaml
item_labels:
  - name: consumable
    description: "Items that are used up"
    color: "green"
    sort_priority: 1
  - name: rare
    description: "Hard to find items"
    color: "gold1"
    sort_priority: 2
  - name: magic
    description: "Imbued with magical properties"
    color: "blue"
    sort_priority: 3
```

| Field           | Required | Description                                      |
| --------------- | -------- | ------------------------------------------------ |
| `name`          | yes      | Identifier used in item manifests and conditions |
| `description`   | no       | Human-readable description                       |
| `color`         | no       | Rich terminal color name for inventory display   |
| `sort_priority` | no       | Lower numbers sort first in inventory            |

Items reference labels by name. The validator warns if an item uses an undeclared label. Labels can be queried by [conditions](./conditions.md#item-held-label) to gate content.

### Passive Effects

Declare game-wide, always-active or conditionally-active stat bonuses and skill grants. These apply automatically to any character playing this game.

```yaml
passive_effects:
  - condition:
      type: milestone
      name: guild-champion
    stat_modifiers:
      - stat: charisma
        amount: 2
    skill_grants:
      - skill: inspire
        slot: passive_1
```

See [Passive Effects](./passive-effects.md) for the full system.

---

## Timezone Configuration

### season_hemisphere

Add `season_hemisphere` to your `game.yaml` spec to flip the seasons for a Southern Hemisphere or Southern-inspired setting. This field affects both `season_is` conditions and the `{{ season(today()) }}` template function.

```yaml
spec:
  season_hemisphere: southern # default is "northern"
```

| Hemisphere           | spring  | summer  | autumn  | winter  |
| -------------------- | ------- | ------- | ------- | ------- |
| `northern` (default) | Mar–May | Jun–Aug | Sep–Nov | Dec–Feb |
| `southern`           | Sep–Nov | Dec–Feb | Mar–May | Jun–Aug |

### timezone

Set `timezone` to an IANA timezone name so that all calendar conditions and the `now()`/`today()` template functions evaluate against your players' local time rather than the server's.

```yaml
spec:
  timezone: "America/New_York" # Eastern US
  # Other examples:
  # timezone: "Europe/London"
  # timezone: "Asia/Tokyo"
  # timezone: "Australia/Sydney"
  # timezone: null    # (default) — use server local time
```

Without `timezone`, calendar predicates such as `time_between`, `month_is`, and `season_is` all use server local time. For games with time-sensitive content or a global audience, setting this field ensures consistency. If the value is not a recognized IANA key (typo, etc.), the engine logs a warning and falls back to server local time — the adventure will not crash.

---

## character_config.yaml

### Minimal Example

```yaml
apiVersion: oscilla/v1
kind: CharacterConfig
metadata:
  name: default-character
spec:
  public_stats:
    - name: strength
      type: int
      default: 10
      description: "Physical power."
```

### Stats

Stats are the numbers (and flags) that define a character. There are two kinds:

- `public_stats` — displayed in the character status panel
- `hidden_stats` — available for conditions and effects but not shown to the player

```yaml
spec:
  public_stats:
    - name: strength
      type: int
      default: 10
      description: "Physical power. Affects melee damage."

    - name: gold
      type: int
      default: 0
      description: "Currency."

    - name: is_blessed
      type: bool
      default: false
      description: "Whether the character has been blessed."

  hidden_stats:
    - name: reputation
      type: int
      default: 0
      description: "Standing with the kingdom."
```

**Stat types:** `int` for numbers, `bool` for true/false flags.

**Naming:** Use lowercase with underscores. The name is what you use in conditions (`stat: strength`) and effects (`stat: gold`).

### Stat Bounds

Restrict the range of any `int` stat. The engine clamps values automatically and notifies the player.

```yaml
- name: gold
  type: int
  default: 0
  bounds:
    min: 0 # gold cannot go negative
    max: 999999 # soft cap
```

Omitting `bounds` entirely means the stat has no enforced limits.

### Equipment Slots

Define the equipment slots available to players. If you don't define any slots, the inventory still works but players can't equip items.

```yaml
equipment_slots:
  - name: main_hand
    displayName: "Main Hand"
    accepts:
      - weapon # only items with category: weapon fit here
    show_when_locked: false

  - name: off_hand
    displayName: "Off Hand"
    accepts:
      - weapon
      - shield
    show_when_locked: false

  - name: armor
    displayName: "Armor"
    accepts:
      - armor
    show_when_locked: false

  - name: ring
    displayName: "Ring Finger"
    requires:
      type: level
      value: 5 # this slot unlocks at level 5
    show_when_locked: true # show it in the UI even before unlocked
```

| Field              | Required | Default    | Description                                                |
| ------------------ | -------- | ---------- | ---------------------------------------------------------- |
| `name`             | yes      | —          | Identifier used in item `equip.slots` lists                |
| `displayName`      | yes      | —          | Player-facing label                                        |
| `accepts`          | no       | `[]` (any) | Item `category` values allowed; empty means no restriction |
| `requires`         | no       | `null`     | [Condition](./conditions.md) to unlock this slot           |
| `show_when_locked` | no       | `false`    | Display the slot in UI before it's unlocked                |

### Skill Resources

If your game uses skills with resource costs (mana, stamina, etc.), define the resource stats in the normal `public_stats` or `hidden_stats` list. Then reference the stat name in skill `cost` fields. See [Skills](./skills.md).

### Custom Pronoun Sets

The engine ships with three built-in pronoun sets: `they_them`, `she_her`, and `he_him`. You can add custom sets to offer players more choices.

```yaml
extra_pronoun_sets:
  - name: ze_zir # unique key — must not clash with built-ins
    display_name: "Ze/Zir" # shown in character creation
    subject: ze
    object: zir
    possessive: zir
    possessive_standalone: zirs
    reflexive: zirself
    uses_plural_verbs: false # false = singular verb forms (is, was, has)
```

**Rules:**

- `name` must be unique and must not be `they_them`, `she_her`, or `he_him`
- All six string fields are required
- `uses_plural_verbs: true` produces `are`, `were`, `have` for verb placeholders; `false` produces `is`, `was`, `has`

Custom pronoun sets are immediately available during character creation alongside the built-in three. See [Templates §Pronouns](./templates.md#pronouns) for how to write pronoun-aware narrative text.

> **Coming in a future release:** The engine will support letting players define their own custom pronoun sets at character creation, without any author configuration required.

---

## In-Game Time System

The engine includes an optional calendar and dual-clock system that lets you define in-world cycles (hours, seasons, moon phases), named eras, and tick-based cooldowns. When enabled, adventures advance one or more time units on completion, conditions can gate content on the current cycle position or active era, and template expressions can display the current time state.

To enable the system, add a `time:` block to your `game.yaml` spec. See the [In-Game Time](./ingame-time.md) guide for the full reference.

```yaml
spec:
  time:
    base_unit: hour
    ticks_per_adventure: 1
    pre_epoch_behavior: clamp
    cycles:
      - name: hour
        count: 24
        labels: [Dawn, Morning, Noon, Dusk, ...]
      - name: day
        parent: hour
        count: 7
        labels: [Monday, Tuesday, Wednesday, Thursday, Friday, Saturday, Sunday]
    epoch:
      hour: 1
    eras:
      - name: age-of-heroes
        format: "Year {count} of Heroes"
        epoch_count: 1
        tracks: day
```

---

## Reference

### `game.yaml` spec fields

| Field                     | Required | Description                                                                                      |
| ------------------------- | -------- | ------------------------------------------------------------------------------------------------ |
| `displayName`             | yes      | Player-facing game title                                                                         |
| `description`             | no       | One or two sentence description                                                                  |
| `xp_thresholds`           | yes      | List of total XP values for levels 2, 3, 4, …                                                    |
| `hp_formula.base_hp`      | yes      | HP at level 1                                                                                    |
| `hp_formula.hp_per_level` | yes      | HP gained per level                                                                              |
| `item_labels`             | no       | List of label definitions (see above)                                                            |
| `passive_effects`         | no       | List of game-wide passive effect entries                                                         |
| `season_hemisphere`       | no       | `northern` (default) or `southern` — flips which months are which season                         |
| `timezone`                | no       | IANA timezone name (e.g. `"America/New_York"`); defaults to server local time                    |
| `time`                    | no       | In-game time system configuration — cycles, eras, epoch. See [In-Game Time](./ingame-time.md).   |
| `triggers`                | no       | Trigger declarations: `custom`, `on_game_rejoin`, `on_stat_threshold`, `max_trigger_queue_depth` |
| `trigger_adventures`      | no       | Maps trigger keys to ordered adventure ref lists (see Triggered Adventures above)                |

### `character_config.yaml` spec fields

| Field                | Required                | Description                                          |
| -------------------- | ----------------------- | ---------------------------------------------------- |
| `public_stats`       | yes (can be empty list) | Stats shown in character panel                       |
| `hidden_stats`       | no                      | Stats hidden from player but usable in conditions    |
| `equipment_slots`    | no                      | Equip slot definitions                               |
| `extra_pronoun_sets` | no                      | Additional pronoun options beyond the built-in three |

### Stat definition fields

| Field         | Required | Description                         |
| ------------- | -------- | ----------------------------------- |
| `name`        | yes      | Identifier (lowercase, underscores) |
| `type`        | yes      | `int` or `bool`                     |
| `default`     | yes      | Starting value                      |
| `description` | no       | Displayed to player                 |
| `bounds.min`  | no       | Minimum value (int stats only)      |
| `bounds.max`  | no       | Maximum value (int stats only)      |

### Built-in pronoun sets

| Key         | Display name | Subject | Object | Possessive | Reflexive  | Plural verbs |
| ----------- | ------------ | ------- | ------ | ---------- | ---------- | ------------ |
| `they_them` | They/Them    | they    | them   | their      | themselves | yes          |
| `she_her`   | She/Her      | she     | her    | her        | herself    | no           |
| `he_him`    | He/Him       | he      | him    | his        | himself    | no           |

---

## Triggered Adventures

Triggered adventures fire automatically in response to game events — no location or player choice required. The trigger system is made up of two co-operating blocks in `game.yaml`: `triggers` (declaration) and `trigger_adventures` (routing).

### `triggers` block

```yaml
triggers:
  # Custom trigger names that adventures can emit with emit_trigger effects.
  custom:
    - my-custom-event

  # Fire when a returning player reopens the game after a long absence.
  on_game_rejoin:
    absence_hours: 4 # minimum hours away before the trigger fires

  # Fire when a stat crosses a threshold upward (not on downward movement).
  on_stat_threshold:
    - stat: reputation
      threshold: 100
      name: reputation-reached # unique name used as the trigger key below
    - stat: reputation
      threshold: 500
      name: fame-cap

  # Control the max queue depth — drops triggers that exceed the limit.
  max_trigger_queue_depth: 6 # default; raise if you have deep event chains
```

All fields are optional. An empty `triggers:` block is valid.

#### `on_stat_threshold` rules

- Only fires on **upward crossings**: stat going from below the threshold to at-or-above.
- Does **not** de-duplicate: if the stat dips below and rises again, it fires again.
- Each entry must have a unique `name`; duplicate names produce a load warning.
- Use `repeatable: false` or `max_completions: 1` on the triggered adventure itself if you only want it to fire once per character.

### `trigger_adventures` block

Maps trigger keys to ordered lists of adventure refs. All adventures in the list run in order each time the trigger fires.

```yaml
trigger_adventures:
  # Lifecycle triggers:
  on_character_create:
    - new-player-intro

  on_game_rejoin:
    - welcome-back-scene

  on_level_up:
    - level-up-fanfare

  # Outcome triggers (fires after an adventure ends with that outcome):
  on_outcome_defeated:
    - defeat-recovery

  on_outcome_completed:
    - completion-bonus

  # Stat threshold triggers (use the name from triggers.on_stat_threshold):
  reputation-reached:
    - reputation-milestone-scene

  # Custom triggers (use the name from triggers.custom):
  my-custom-event:
    - custom-event-scene
```

#### Valid trigger keys

| Key                   | When it fires                                                                                                                                |
| --------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| `on_character_create` | Once, immediately after a new character is created                                                                                           |
| `on_level_up`         | Once per level gained (fires multiple times on multi-level jumps)                                                                            |
| `on_game_rejoin`      | When the player returns after `absence_hours` or more                                                                                        |
| `on_outcome_<name>`   | After any adventure ends with outcome `<name>` (built-ins: `completed`, `defeated`, `fled`; declare custom outcomes in `game.yaml outcomes`) |
| `<threshold.name>`    | When the named stat crosses its threshold upward                                                                                             |
| `<custom>`            | When an `emit_trigger` effect fires with that name                                                                                           |

#### Multiple adventures per trigger

When a trigger maps to multiple adventure refs, they run in order. Each one respects `requires`, `repeatable`, and cooldown settings. If any adventure is gated, only that one is skipped; the others still run.

```yaml
trigger_adventures:
  on_level_up:
    - level-up-fanfare # narrative scene, always
    - level-up-bonus-chest # repeatable loot, always
    - class-advancement-scene # requires: {type: level, value: 10}
```

### Condition and repeat controls on triggered adventures

Triggered adventures use exactly the same manifest structure as pool adventures. `requires`, `repeatable`, `max_completions`, `cooldown_days`, and `cooldown_ticks` all apply and are enforced by the drain loop before running.

```yaml
# content/adventures/one-time-intro.yaml
spec:
  displayName: "Welcome to the Realm"
  repeatable: false # fire at most once per character
  steps:
    - type: narrative
      text: "A herald announces your arrival."
```

### Load warnings

A `trigger_adventures` key that does not match a known trigger name produces a **load warning** (non-fatal). The same applies to adventure refs that cannot be resolved. Check `oscilla validate` output after editing this block.

---

## Character Creation Defaults

The optional `character_creation:` block lets you set game-wide defaults for new characters. These are applied at character creation and can be overridden during gameplay (e.g., by a `set_name` or `set_pronouns` effect in a creation adventure).

```yaml
spec:
  character_creation:
    default_name: "Protagonist" # optional; bypasses UUID placeholder
    default_pronouns: they_them # optional; one of: they_them, she_her, he_him
```

| Field              | Type             | Description                                                                                                                                                                        |
| ------------------ | ---------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `default_name`     | `string \| null` | Fixed protagonist name. If set, `SetNameEffect` skips its prompt because the name is not a placeholder. Useful for single-protagonist games.                                       |
| `default_pronouns` | `string \| null` | Key of the pronoun set to use by default (e.g. `they_them`). If absent, the engine defaults to `they_them`. An unrecognized key generates a warning and falls back to `they_them`. |

### When to use `default_name`

For games where every player controls the same named protagonist (e.g. "Elara"), set `default_name` here so no prompt ever appears. For games where players name their own character, leave it unset and use a `set_name` effect in a character creation adventure.

### When to use `default_pronouns`

If your narrative never varies by pronoun (all static text) or you want a specific default before the player makes a choice, set a value here. Players can still override it mid-game with `set_pronouns` effects.

---

## Prestige

The optional `prestige:` block enables a prestige/new-game-plus system. When an adventure runs a `type: prestige` effect, the character's progression is reset to level 1 defaults and a new DB character iteration is opened — but stats, skills, and milestones listed in the carry lists are preserved.

**Important:** if any adventure in your package uses `type: prestige` but `prestige:` is absent from `game.yaml`, content loading will fail with a validation error.

```yaml
spec:
  prestige:
    carry_stats:
      - legacy_power # stat values listed here survive the reset
    carry_skills: [] # skill refs whose learned status carries forward
    carry_milestones: [] # milestone refs that are re-granted after the reset
    pre_prestige_effects:
      - type: stat_change
        stat: legacy_power
        amount: 1 # runs against the OLD state; captured into the carry
    post_prestige_effects: [] # runs against the NEW (reset + carried) state
```

| Field                   | Type           | Description                                                                                                                                                  |
| ----------------------- | -------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `carry_stats`           | `list[string]` | Stat names whose current values are copied to the new iteration.                                                                                             |
| `carry_skills`          | `list[string]` | Skill refs whose membership in `known_skills` carries forward.                                                                                               |
| `carry_milestones`      | `list[string]` | Milestone refs that are re-granted on the new iteration if held at prestige time.                                                                            |
| `pre_prestige_effects`  | `list[Effect]` | Effects applied to the **old** character state immediately before the carry snapshot. Use this to grant legacy bonuses (e.g. `stat_change` on a carry stat). |
| `post_prestige_effects` | `list[Effect]` | Effects applied to the **new** (reset + carried) state after the carry is applied.                                                                           |

### Execution order

1. `pre_prestige_effects` run against old state.
2. Carry snapshot is taken (after pre-effects, so bonuses are included).
3. Character state resets to config defaults.
4. Carry values overwrite the defaults.
5. `prestige_count` increments by 1.
6. `post_prestige_effects` run against the new state.
7. `prestige_pending` is set on the character; the session layer opens a new DB iteration at adventure end.

### Wiring prestige to a trigger

The recommended pattern is to fire a prestige ceremony adventure from a stat threshold trigger rather than placing it in a location pool:

```yaml
spec:
  triggers:
    on_stat_threshold:
      - stat: level
        threshold: 10
        name: max-level-reached

  trigger_adventures:
    max-level-reached:
      - prestige-ceremony
```

The ceremony adventure then uses `type: prestige` and `type: end_adventure` options so the player can confirm or decline.

### Checking prestige count in conditions

Use the `prestige_count` condition to gate content behind at least one prestige:

```yaml
# Location unlock requiring at least one prestige
unlock:
  type: prestige_count
  gte: 1
```

See [Conditions](./conditions.md#prestige-count-condition) for full syntax.

---

_Next: [World Building](./world-building.md) — regions, locations, and adventure pools._
_See [Templates](./templates.md#pronouns) for using pronoun placeholders in narrative text._
_See [Passive Effects](./passive-effects.md) for the full `passive_effects` syntax._
_See [Effects](./effects.md#emit-trigger) for the `emit_trigger` effect that fires custom triggers._
