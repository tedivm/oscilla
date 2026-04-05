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
apiVersion: game/v1
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
  base_hp: 20        # HP at level 1
  hp_per_level: 10   # HP gained per level
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

| Field | Required | Description |
|---|---|---|
| `name` | yes | Identifier used in item manifests and conditions |
| `description` | no | Human-readable description |
| `color` | no | Rich terminal color name for inventory display |
| `sort_priority` | no | Lower numbers sort first in inventory |

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
  season_hemisphere: southern   # default is "northern"
```

| Hemisphere | spring | summer | autumn | winter |
|---|---|---|---|---|
| `northern` (default) | Mar–May | Jun–Aug | Sep–Nov | Dec–Feb |
| `southern` | Sep–Nov | Dec–Feb | Mar–May | Jun–Aug |

### timezone

Set `timezone` to an IANA timezone name so that all calendar conditions and the `now()`/`today()` template functions evaluate against your players' local time rather than the server's.

```yaml
spec:
  timezone: "America/New_York"   # Eastern US
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
apiVersion: game/v1
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
    min: 0        # gold cannot go negative
    max: 999999   # soft cap
```

Omitting `bounds` entirely means the stat has no enforced limits.

### Equipment Slots

Define the equipment slots available to players. If you don't define any slots, the inventory still works but players can't equip items.

```yaml
equipment_slots:
  - name: main_hand
    displayName: "Main Hand"
    accepts:
      - weapon       # only items with category: weapon fit here
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
      value: 5       # this slot unlocks at level 5
    show_when_locked: true   # show it in the UI even before unlocked
```

| Field | Required | Default | Description |
|---|---|---|---|
| `name` | yes | — | Identifier used in item `equip.slots` lists |
| `displayName` | yes | — | Player-facing label |
| `accepts` | no | `[]` (any) | Item `category` values allowed; empty means no restriction |
| `requires` | no | `null` | [Condition](./conditions.md) to unlock this slot |
| `show_when_locked` | no | `false` | Display the slot in UI before it's unlocked |

### Skill Resources

If your game uses skills with resource costs (mana, stamina, etc.), define the resource stats in the normal `public_stats` or `hidden_stats` list. Then reference the stat name in skill `cost` fields. See [Skills](./skills.md).

### Custom Pronoun Sets

The engine ships with three built-in pronoun sets: `they_them`, `she_her`, and `he_him`. You can add custom sets to offer players more choices.

```yaml
extra_pronoun_sets:
  - name: ze_zir             # unique key — must not clash with built-ins
    display_name: "Ze/Zir"   # shown in character creation
    subject: ze
    object: zir
    possessive: zir
    possessive_standalone: zirs
    reflexive: zirself
    uses_plural_verbs: false  # false = singular verb forms (is, was, has)
```

**Rules:**

- `name` must be unique and must not be `they_them`, `she_her`, or `he_him`
- All six string fields are required
- `uses_plural_verbs: true` produces `are`, `were`, `have` for verb placeholders; `false` produces `is`, `was`, `has`

Custom pronoun sets are immediately available during character creation alongside the built-in three. See [Templates §Pronouns](./templates.md#pronouns) for how to write pronoun-aware narrative text.

> **Coming in a future release:** The engine will support letting players define their own custom pronoun sets at character creation, without any author configuration required.

---

## Reference

### `game.yaml` spec fields

| Field | Required | Description |
|---|---|---|
| `displayName` | yes | Player-facing game title |
| `description` | no | One or two sentence description |
| `xp_thresholds` | yes | List of total XP values for levels 2, 3, 4, … |
| `hp_formula.base_hp` | yes | HP at level 1 |
| `hp_formula.hp_per_level` | yes | HP gained per level |
| `item_labels` | no | List of label definitions (see above) |
| `passive_effects` | no | List of game-wide passive effect entries |
| `season_hemisphere` | no | `northern` (default) or `southern` — flips which months are which season |
| `timezone` | no | IANA timezone name (e.g. `"America/New_York"`); defaults to server local time |

### `character_config.yaml` spec fields

| Field | Required | Description |
|---|---|---|
| `public_stats` | yes (can be empty list) | Stats shown in character panel |
| `hidden_stats` | no | Stats hidden from player but usable in conditions |
| `equipment_slots` | no | Equip slot definitions |
| `extra_pronoun_sets` | no | Additional pronoun options beyond the built-in three |

### Stat definition fields

| Field | Required | Description |
|---|---|---|
| `name` | yes | Identifier (lowercase, underscores) |
| `type` | yes | `int` or `bool` |
| `default` | yes | Starting value |
| `description` | no | Displayed to player |
| `bounds.min` | no | Minimum value (int stats only) |
| `bounds.max` | no | Maximum value (int stats only) |

### Built-in pronoun sets

| Key | Display name | Subject | Object | Possessive | Reflexive | Plural verbs |
|---|---|---|---|---|---|---|
| `they_them` | They/Them | they | them | their | themselves | yes |
| `she_her` | She/Her | she | her | her | herself | no |
| `he_him` | He/Him | he | him | his | himself | no |

---

*Next: [World Building](./world-building.md) — regions, locations, and adventure pools.*
*See [Templates](./templates.md#pronouns) for using pronoun placeholders in narrative text.*
*See [Passive Effects](./passive-effects.md) for the full `passive_effects` syntax.*
