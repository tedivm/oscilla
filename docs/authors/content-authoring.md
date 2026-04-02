# Content Authoring Guide

This guide covers creating game content for Oscilla using YAML manifest files. Content authors define adventures, characters, items, and game rules through structured configuration files.

## Getting Started

### Game Library Structure

Oscilla supports a **multi-game library** where multiple game packages can coexist in a single library directory. Each game is a self-contained package with its own content and configuration:

```
content/                      # Game library root
├── the-kingdom/             # Game package directory
│   ├── game.yaml           # Game settings and configuration
│   ├── character_config.yaml  # Player stats and defaults
│   ├── regions/            # Geographic areas
│   ├── locations/          # Specific places within regions
│   ├── adventures/         # Interactive scenarios
│   ├── enemies/            # Combat opponents
│   ├── items/              # Equipment and consumables
│   ├── recipes/            # Crafting formulas
│   └── quests/             # Multi-stage storylines
├── testlandia/             # Another game package
│   ├── game.yaml
│   ├── character_config.yaml
│   └── regions/
└── other-games/            # Additional game packages
    └── ...
```

**Key Concepts:**

- **Library root**: The `content/` directory (configurable via `GAMES_PATH`)
- **Game package**: Each subdirectory containing a `game.yaml` file
- **Package isolation**: Each game has independent content, saves, and configuration
- **Game selection**: Players choose which game to play via the TUI or `--game` flag

### Single Package Structure (Legacy)

For simple setups with one game, you can place content directly in the library root:

```
content/                     # Game library root
├── game.yaml               # Game settings
├── character_config.yaml   # Player configuration
├── regions/                # Game content directories
├── locations/
├── adventures/
├── enemies/
├── items/
├── recipes/
└── quests/
```

**Validation**: Always run `uv run oscilla validate` to check for errors before testing your content.

## Manifest Envelope Format

All manifest files share a common structure:

```yaml
apiVersion: game/v1           # Required: API compatibility version
kind: ItemManifest           # Required: Type of content (Game, Region, Adventure, etc.)
metadata:
  name: unique-identifier    # Required: Reference name (lowercase, hyphens, no spaces)
spec:                        # Required: Type-specific configuration
  displayName: "Human Name"  # Usually required: Player-facing name
  description: "..."         # Usually required: Flavor text
  # ... kind-specific fields
```

**Naming Rule**: The `metadata.name` field must match the filename (without extension). For example, `healing-potion.yaml` must have `name: healing-potion`.

## Content Types

### Game Configuration (`game.yaml`)

Global game settings and progression rules:

```yaml
apiVersion: game/v1
kind: Game
metadata:
  name: my-game
spec:
  displayName: "My Adventure Game"
  description: "A thrilling text-based adventure."

  # XP required to reach each level (index 0 = level 2, index 1 = level 3, etc.)
  xp_thresholds: [100, 250, 500, 900, 1400, 2100, 3000, 4200, 5800, 8000]

  # Health point calculation
  hp_formula:
    base_hp: 20        # Starting health
    hp_per_level: 10   # Health gained per level

  base_adventure_count: null  # Optional: default adventure count per location
```

#### Experience and Leveling Mechanics

**XP Progression**: Players start at level 1 with 0 XP. Each `xp_thresholds` value represents the total XP needed to reach that level. For example:

- Level 1: 0 XP (starting level)
- Level 2: 100 XP total
- Level 3: 250 XP total
- Level 4: 500 XP total

**Level-Down Rules**: Negative XP can reduce player level but follows these constraints:

- **Level floor**: Players cannot go below level 1
- **XP floor**: XP cannot go below 0 (negative amounts are clamped)
- **HP adjustment**: When losing levels, max HP is recalculated and current HP is capped to the new maximum

**Example Level-Down**:

- Player at level 5 (900 XP) receives -600 XP
- New total: 300 XP → level 3 (next threshold is 500)
- Player loses levels 5 and 4, keeps level 3
- Max HP recalculated: base_hp + (new_level - 1) × hp_per_level

### Character Configuration (`character_config.yaml`)

Defines custom player statistics:

```yaml
apiVersion: game/v1
kind: CharacterConfig
metadata:
  name: default-character
spec:
  public_stats:    # Shown in status display
    - name: strength
      type: int
      default: 10
      description: "Physical power. Affects melee damage."

    - name: dexterity
      type: int
      default: 10
      description: "Agility. Reduces incoming damage."

    - name: gold
      type: int
      default: 0
      description: "Currency."

  hidden_stats:    # Used in conditions but not displayed (optional)
    - name: reputation
      type: int
      default: 0
      description: "Standing with various factions."
```

**Stat Types**: `int`, `bool`

**Stat Bounds** (optional, `int` stats only): Add a `bounds` key with `min` and/or `max` to restrict the range of an integer stat. The engine clamps out-of-range values automatically and notifies the player when this happens.

```yaml
- name: gold
  type: int
  default: 0
  bounds:
    min: 0       # gold cannot go below zero
    max: 999999  # gold cap
```

Omitting `bounds` (or omitting `min`/`max` individually) defaults to the full 64-bit signed integer range.

#### Equipment Slots

Define the equipment slots available to players using `equipment_slots` in the spec. If no slots are defined the inventory still works, but players cannot equip items.

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

  equipment_slots:
    - name: main_hand
      displayName: "Main Hand"
      accepts:               # Optional: only allow these categories (empty = accept all)
        - weapon
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

    - name: head
      displayName: "Head"
      requires:              # Optional: condition to unlock this slot
        type: level
        value: 5
      show_when_locked: true # Show slot in UI even when locked (so player knows it exists)
```

**SlotDefinition Fields**:

| Field | Type | Default | Description |
|---|---|---|---|
| `name` | `str` | required | Unique identifier used in item `equip.slots` lists |
| `displayName` | `str` | required | Player-facing label |
| `accepts` | list of `str` | `[]` | Item `category` values allowed in this slot; empty = no restriction |
| `requires` | Condition \| null | `null` | Condition that must pass before slot is usable |
| `show_when_locked` | `bool` | `false` | Whether to display the slot in the UI when it is locked |

### Regions (`regions/`)

Geographic areas that contain locations:

```yaml
apiVersion: game/v1
kind: Region
metadata:
  name: haunted-forest
spec:
  displayName: "The Haunted Forest"
  description: "Dark woods filled with ancient magic and lurking dangers."

  parent: wilderness    # Optional: parent region reference

  unlock:               # Optional: condition to access this region
    type: level
    value: 5
```

**Region Hierarchy**: Child regions inherit unlock conditions from their parents, creating an `all` condition chain.

### Locations (`locations/`)

Specific places within regions that contain adventures:

```yaml
apiVersion: game/v1
kind: Location
metadata:
  name: abandoned-mill
spec:
  displayName: "Abandoned Mill"
  description: "A decrepit watermill with a broken wheel."

  parent_region: haunted-forest    # Required: region reference

  unlock:                          # Optional: additional unlock condition
    type: milestone
    name: "found-mill-key"

  adventure_pool:                  # Required: list of available adventures
    - adventure: ghost-encounter   # Adventure reference
      weight: 60                   # Selection weight
    - adventure: treasure-search
      weight: 40
```

### Adventures (`adventures/`)

Interactive scenarios with steps and outcomes:

```yaml
apiVersion: game/v1
kind: Adventure
metadata:
  name: goblin-ambush
spec:
  displayName: "Goblin Ambush"
  description: "Goblins have set up an ambush on the forest road."

  requires:                        # Optional: condition to attempt this adventure
    type: level
    value: 2

  steps:                           # Required: ordered list of adventure steps
    - type: narrative
      text: |
        You hear rustling in the bushes. Three goblins leap out,
        brandishing crude weapons!

    - type: combat
      enemy: goblin-scout
      on_win:
        effects:
          - type: xp_grant
            amount: 50
          - type: milestone_grant
            milestone: "defeated-goblins"
        steps:
          - type: narrative
            text: "The goblins flee into the darkness."
      on_flee:
        effects:
          - type: end_adventure
            outcome: "fled"
```

### Items (`items/`)

Equipment, consumables, and other objects. Items can be stackable consumables, equippable gear, or passive materials.

#### Stackable Consumable (e.g., potion)

```yaml
apiVersion: game/v1
kind: Item
metadata:
  name: healing-potion
spec:
  displayName: "Healing Potion"
  description: "A bright red potion that restores health."

  category: consumable      # Required: free-form category label (weapon, armor, consumable, material, etc.)
  stackable: true           # Multiple copies share one inventory slot (default: true)
  consumed_on_use: true     # Removes one unit from the stack after use (default: true)
  value: 50                 # Optional: base gold value (default: 0)

  use_effects:              # Effects applied when the player uses this item
    - type: heal
      amount: 30
```

#### Equippable Gear (e.g., sword)

```yaml
apiVersion: game/v1
kind: Item
metadata:
  name: iron-sword
spec:
  displayName: "Iron Sword"
  description: "A well-made blade with a leather grip."

  category: weapon
  stackable: false          # Equippable items must NOT be stackable
  value: 150

  equip:                    # Equipment specification
    slots:                  # Required: one or more slot names (must match equipment_slots in character_config.yaml)
      - main_hand
    stat_modifiers:         # Optional: passive stat bonuses while equipped
      - stat: strength
        amount: 2
```

**Two-handed / multi-slot items** occupy multiple slots simultaneously by listing them all:

```yaml
equip:
  slots:
    - main_hand
    - off_hand             # Blocks both slots when equipped
  stat_modifiers:
    - stat: strength
      amount: 5
```

**Item Spec Fields**:

| Field | Type | Default | Description |
|---|---|---|---|
| `category` | `str` | required | Free-form label used for `accepts` filtering on slots |
| `displayName` | `str` | required | Player-facing name |
| `description` | `str` | `""` | Flavor text |
| `stackable` | `bool` | `true` | Multiple copies share one slot; must be `false` for equippable items |
| `droppable` | `bool` | `true` | Whether the item can be dropped |
| `value` | `int` | `0` | Base gold value (non-negative) |
| `use_effects` | list of Effects | `[]` | Effects applied when the player uses the item |
| `consumed_on_use` | `bool` | `true` | Removes the item after use (stack decremented or instance removed) |
| `equip` | EquipSpec \| null | `null` | If present, item is equippable rather than stackable |

**EquipSpec Fields**:

| Field | Type | Default | Description |
|---|---|---|---|
| `slots` | list of `str` | required (min 1) | Slot names the item occupies when equipped |
| `stat_modifiers` | list of StatModifier | `[]` | Passive stat bonuses while equipped |

**StatModifier Fields**:

| Field | Type | Description |
|---|---|---|
| `stat` | `str` | Stat name from `CharacterConfig` |
| `amount` | `int` or `float` | Bonus amount (positive or negative) |

### Enemies (`enemies/`)

Combat opponents with loot tables:

```yaml
apiVersion: game/v1
kind: Enemy
metadata:
  name: goblin-scout
spec:
  displayName: "Goblin Scout"
  description: "A small, aggressive humanoid with yellowed fangs."

  level: 2
  hp: 25
  damage: 8

  loot_table:              # Optional: items dropped on defeat
    - item: goblin-ear     # Item reference
      weight: 80           # Drop chance weight
    - item: shiny-button
      weight: 20
```

### Skills (`skills/`)

Skills are learnable, activatable abilities. They can be awarded by adventures, items, or created directly in character config. Full reference: [Skills and Buffs](./skills.md).

```yaml
apiVersion: game/v1
kind: Skill
metadata:
  name: arcane-shield
spec:
  displayName: Arcane Shield
  description: "Conjure a barrier absorbing 40% of incoming damage."
  contexts:
    - combat
  cost:
    stat: mana
    amount: 10
  use_effects:
    - type: apply_buff
      buff_ref: shielded
```

See [Skills and Buffs](./skills.md) for the complete field reference, cooldown options, and context rules.

### Buffs (`buffs/`)

Buffs are named, reusable timed combat effects. They are never granted directly — always through an `apply_buff` effect in a skill, item, or equipment grant. Full reference: [Skills and Buffs](./skills.md).

```yaml
apiVersion: game/v1
kind: Buff
metadata:
  name: shielded
spec:
  displayName: Arcane Shield
  description: "A shimmering barrier that absorbs 40% of incoming damage."
  duration_turns: 3
  modifiers:
    - type: damage_reduction
      percent: 40
      target: player
```

Buffs can have `per_turn_effects` (damage/heal each round), `modifiers` (passive damage arithmetic), or both. At least one must be non-empty. See [Skills and Buffs](./skills.md) for all modifier types and the buff variables system.

### Recipes (`recipes/`)

Crafting formulas that transform ingredients:

```yaml
apiVersion: game/v1
kind: Recipe
metadata:
  name: healing-salve
spec:
  displayName: "Healing Salve Recipe"
  description: "Combine herbs to create a basic healing item."

  ingredients:             # Required: items consumed
    - item: cave-mushroom
      quantity: 2
    - item: spring-water
      quantity: 1

  result:                  # Required: item produced
    item: healing-potion
    quantity: 1
```

### Quests (`quests/`)

Multi-stage storylines with milestone tracking:

```yaml
apiVersion: game/v1
kind: Quest
metadata:
  name: rescue-mission
spec:
  displayName: "Rescue the Lost Child"
  description: "A child has gone missing in the forest."

  stages:                  # Required: ordered quest progression
    - name: "Find Clues"
      description: "Search for signs of the missing child."
      advance_milestone: "found-child-tracks"

    - name: "Follow Trail"
      description: "Track the child deeper into the woods."
      advance_milestone: "located-child"

    - name: "Safe Return"
      description: "Escort the child back to safety."
      advance_milestone: "child-rescued"
```

## Conditions

Conditions control access to regions, locations, adventures, and choices. They can be simple requirements or complex logical expressions.

### Leaf Conditions

#### Level Requirements

```yaml
unlock:
  type: level
  value: 5        # Player must be level 5 or higher
```

#### Milestone Checks

```yaml
requires:
  type: milestone
  name: "defeated-boss"    # Player must have earned this milestone
```

#### Inventory Requirements

```yaml
unlock:
  type: item
  item_ref: ancient-key    # Item reference
  quantity: 1             # Required amount (default: 1)
```

#### Character Stat Comparisons

```yaml
requires:
  type: character_stat
  name: strength          # Stat name (must be defined in CharacterConfig)
  gte: 15                 # Greater than or equal to 15
```

**Stat Operators**: `gte` (≥), `lte` (≤), `eq` (=), `gt` (>), `lt` (<)

#### Statistics Tracking

```yaml
# Enemies defeated
requires:
  type: enemies_defeated
  name: goblin-scout      # Enemy reference
  gte: 3                  # Must have defeated 3 or more

# Locations visited
requires:
  type: locations_visited
  name: ancient-ruins
  gte: 1                  # Must have visited at least once

# Adventures completed
requires:
  type: adventures_completed
  name: tutorial-quest
  gte: 1                  # Must have completed successfully
```

#### Prestige Level

```yaml
requires:
  type: prestige_count
  gte: 2                  # Multiple prestige levels earned
```

#### Class Requirements (Placeholder)

```yaml
requires:
  type: class
  name: warrior           # Always passes (no-op condition)
```

#### Skill Requirements

Check whether the player has learned a skill or has a skill currently available (including from equipped items):

```yaml
requires:
  type: skill
  skill_ref: arcane-shield    # Skill manifest name
  mode: learned               # "learned" (default) or "available"
```

- **`learned`**: checks `known_skills` only — skills permanently owned by the player.
- **`available`**: checks the full set including skills granted by equipped or held items.

### Logical Operators

#### All (AND Logic)

All child conditions must pass:

```yaml
unlock:
  type: all
  conditions:
    - type: level
      value: 10
    - type: milestone
      name: "found-ancient-key"
    - type: item
      item_ref: magic-scroll
      quantity: 1
```

#### Any (OR Logic)

At least one child condition must pass:

```yaml
requires:
  type: any
  conditions:
    - type: character_stat
      name: strength
      gte: 20
    - type: item
      item_ref: lockpick-set
      quantity: 1
```

#### Not (Negation)

Inverts the child condition:

```yaml
unlock:
  type: not
  condition:
    type: milestone
    name: "village-destroyed"    # Unlocked only if village NOT destroyed
```

## Adventure Steps

Steps define the sequence of events in an adventure.

### Narrative Steps

Display text and wait for acknowledgment:

```yaml
- type: narrative
  text: |
    The ancient door creaks open, revealing a chamber filled with
    glowing crystals. The air hums with magical energy.
```

**Text Formatting**: Supports multi-line text with YAML's `|` syntax.

### Combat Steps

Turn-based battles with branching outcomes:

```yaml
- type: combat
  enemy: dragon           # Enemy reference
  label: final-boss       # Optional: target for goto effects

  on_win:                 # Player victory branch
    effects:
      - type: xp_grant
        amount: 500
      - type: item_drop
        loot:
          - item: dragon-scale
            weight: 100
    steps:
      - type: narrative
        text: "The mighty dragon falls!"

  on_defeat:              # Player defeat branch
    effects:
      - type: end_adventure
        outcome: "defeat"

  on_flee:                # Player flees branch
    effects:
      - type: end_adventure
        outcome: "fled"
```

### Choice Steps

Present options filtered by condition requirements:

```yaml
- type: choice
  prompt: "What do you do?"
  options:
    - text: "Break down the door"                    # Always available
      steps:
        - type: narrative
          text: "You smash through the wooden barrier."

    - text: "Pick the lock"
      requires:                                      # Conditional option
        type: item
        item_ref: lockpick-set
        quantity: 1
      steps:
        - type: narrative
          text: "You carefully work the lock mechanism."

    - text: "Cast magic missile"
      requires:
        type: character_stat
        name: wisdom
        gte: 15
      steps:
        - type: combat
          enemy: door-guardian
```

### Stat Check Steps

Test conditions and branch accordingly:

```yaml
- type: stat_check
  condition:
    type: character_stat
    name: dexterity
    gte: 12

  on_pass:                # Condition succeeds
    steps:
      - type: narrative
        text: "You nimbly dodge the falling rocks."

  on_fail:                # Condition fails
    effects:
      - type: xp_grant
        amount: -10       # XP penalty
    steps:
      - type: narrative
        text: "The rocks strike you as you stumble."
```

## Effects

Effects modify player state or control adventure flow.

### Experience Grants

```yaml
effects:
  - type: xp_grant
    amount: 100          # Positive for rewards, negative for penalties
```

**Automatic Leveling**: XP grants trigger level-up calculations based on game configuration. **Level-down mechanics**: Negative XP can reduce player level, but never below level 1. XP cannot go below 0.

### Stat Manipulation

#### Stat Change

Modify player stats by adding or subtracting integer amounts. Only works with `int` stats:

```yaml
effects:
  - type: stat_change
    stat: "strength"       # Stat name from character_config.yaml
    amount: 2             # Amount to add (positive) or subtract (negative)

  - type: stat_change
    stat: "gold"
    amount: -25           # Spend 25 gold
```

**Validation**: The stat must exist in `CharacterConfig` and be of type `int`. Attempting to use `stat_change` on `bool` stats will cause a content load error. The `amount` must be an integer.

**Bounds clamping**: If the stat has `bounds` defined, the result is clamped to `[min, max]` automatically. The player is notified via the TUI when clamping occurs.

#### Stat Set

Set player stats to specific values:

```yaml
effects:
  - type: stat_set
    stat: "is_blessed"
    value: true                   # Boolean assignment

  - type: stat_set
    stat: "strength"
    value: 20                     # Integer override
```

**Validation**: The value must match the stat type (`int` or `bool`). The stat must exist in `CharacterConfig`. String values are not accepted.

**Bounds clamping**: For `int` stats with `bounds` defined, the value is clamped to `[min, max]`. The player is notified via the TUI when clamping occurs.

### Item Drops

Weighted random item distribution:

```yaml
effects:
  - type: item_drop
    count: 2             # Number of rolls (default: 1)
    loot:
      - item: gold-coins
        weight: 60       # Relative probability
      - item: magic-gem
        weight: 30
      - item: rare-artifact
        weight: 10
```

**Drop Mechanics**: Each roll selects one item based on relative weights. Higher weights = higher chance. Equippable items (non-stackable) are added as individual instances; stackable items increment the player's stack count.

### Use Item

Trigger a specific item's `use_effects` directly from an adventure step:

```yaml
effects:
  - type: use_item
    item: healing-potion    # Item reference; the item must exist in the content package
```

The item's effects execute exactly as if the player pressed "Use" in the inventory. If the item has `consumed_on_use: true` the item is removed after use. Note that the player must already have the item in their inventory for this to do anything meaningful; for automated drops followed by instant use, pair this with an `item_drop` effect on the same step.

### Milestone Grants

Unlock story progress markers:

```yaml
effects:
  - type: milestone_grant
    milestone: "tower-explored"    # Milestone name
```

### Adventure Termination

```yaml
effects:
  - type: end_adventure
    outcome: "victory"    # Outcome message identifier
```

**Common Outcomes**: `"victory"`, `"defeat"`, `"fled"`, or custom strings.

## Advanced Features

### Labels and Goto

Create jump targets and navigation within adventures:

```yaml
steps:
  - type: narrative
    text: "You approach the crossroads."

  - type: choice
    label: crossroads-decision     # Jump target
    prompt: "Which path do you take?"
    options:
      - text: "Left path"
        steps:
          - type: narrative
            text: "The left path leads to danger!"
          - type: narrative
            text: "You return to the crossroads."
            effects:
              - type: goto
                target: crossroads-decision    # Jump back to choice

      - text: "Right path"
        steps:
          - type: narrative
            text: "The right path leads to treasure!"
            effects:
              - type: end_adventure
                outcome: "victory"
```

**Validation**: All `goto` targets must reference existing labels within the same adventure.

### Effect Placement

Effects can be attached to steps or outcome branches:

```yaml
# Effects on narrative steps
- type: narrative
  text: "You discover a hidden chest!"
  effects:                        # Applied when step executes
    - type: item_drop
      loot:
        - item: treasure-map
          weight: 100

# Effects on combat outcomes
- type: combat
  enemy: boss-monster
  on_win:
    effects:                      # Applied on victory
      - type: milestone_grant
        milestone: "boss-defeated"
    steps:                        # Additional steps after effects
      - type: narrative
        text: "The boss falls!"
```

## Common Patterns

### Progressive Difficulty

Gate content behind level requirements:

```yaml
# Early content
requires:
  type: level
  value: 1                # Levels 1-3

# Mid-game content
requires:
  type: level
  value: 5                # Levels 5-7

# End-game content
requires:
  type: all
  conditions:
    - type: level
      value: 10
    - type: milestone
      name: "completed-main-quest"
```

### Conditional Rewards

Vary outcomes based on player state:

```yaml
- type: combat
  enemy: merchant-bandit
  on_win:
    effects:
      - type: xp_grant
        amount: 30
    steps:
      - type: choice
        prompt: "What do you do with the bandit's goods?"
        options:
          - text: "Take everything"
            steps:
              - type: narrative
                text: "You claim the bandit's stolen merchandise."
                effects:
                  - type: item_drop
                    loot:
                      - item: gold-coins
                        weight: 100

          - text: "Return goods to rightful owners"
            requires:
              type: character_stat
              name: wisdom
              gte: 12
            steps:
              - type: narrative
                text: "You show mercy and earn the merchants' gratitude."
                effects:
                  - type: milestone_grant
                    milestone: "showed-mercy"
                  - type: character_stat
                    name: reputation
                    modifier: 5
```

### Equipment Progression

Create upgrade paths through item requirements:

```yaml
# Basic equipment (no requirements)
- text: "Pick up the rusty sword"
  steps:
    - type: narrative
      text: "Better than nothing."
      effects:
        - type: item_drop
          loot:
            - item: rusty-sword
              weight: 100

# Advanced equipment (conditional)
- text: "Forge a masterwork blade"
  requires:
    type: all
    conditions:
      - type: item
        item_ref: rare-metal
        quantity: 3
      - type: character_stat
        name: strength
        gte: 18
  steps:
    - type: narrative
      text: "Your skill produces a legendary weapon!"
      effects:
        - type: item_drop
          loot:
            - item: legendary-sword
              weight: 100
```

## Validation and Testing

### Content Validation

Run the validator frequently during development:

```bash
uv run oscilla validate
```

**Common Errors**:

- Broken references (misspelled item/enemy/adventure names)
- Invalid YAML syntax (indentation, quotes, structure)
- Schema violations (missing required fields, wrong types)
- Duplicate labels within adventures
- Circular region dependencies

### Testing Content

Use the interactive game mode to test your adventures:

```bash
uv run oscilla game
```

**Testing Checklist**:

- [ ] All adventure paths lead to valid outcomes
- [ ] Condition requirements work as expected
- [ ] Item drops use reasonable weights
- [ ] XP amounts feel balanced for difficulty
- [ ] Text is engaging and error-free
- [ ] Goto/label jumps work correctly

### Content Organization Tips

- **Incremental Development**: Start with simple adventures, add complexity gradually
- **Consistent Naming**: Use clear, descriptive reference names (avoid generic names like "item1")
- **Balanced Rewards**: Test XP/item drop amounts to maintain player progression
- **Condition Testing**: Verify unlock requirements work at different player levels
- **Cross-References**: Double-check all item, enemy, and adventure references for typos

## Reference

### Complete Manifest Kinds

- `Game`: Global settings and progression rules
- `CharacterConfig`: Player stat definitions
- `Region`: Geographic areas
- `Location`: Adventure sites within regions
- `Adventure`: Interactive scenarios
- `Enemy`: Combat opponents
- `Item`: Equipment and consumables
- `Skill`: Learnable, activatable abilities
- `Buff`: Named, reusable timed combat effects
- `Recipe`: Crafting formulas
- `Quest`: Multi-stage storylines
- `Class`: Character classes (placeholder)

### All Condition Types

**Leaf Conditions**: `level`, `milestone`, `item`, `character_stat`, `prestige_count`, `class`, `enemies_defeated`, `locations_visited`, `adventures_completed`, `skill`

**Logical Operators**: `all`, `any`, `not`

### All Step Types

**Interactive Steps**: `narrative`, `combat`, `choice`, `stat_check`

### All Effect Types

**State Changes**: `xp_grant`, `item_drop`, `use_item`, `milestone_grant`, `stat_change`, `stat_set`, `skill_grant`
**Combat Effects**: `apply_buff`, `dispel`
**Flow Control**: `end_adventure`, `goto`

---

## Dynamic Templates

Oscilla supports **Jinja2 template expressions** in narrative text and in numeric effect fields. Templates are validated at load time, so authoring errors are caught before the game is played.

### Where Templates Can Be Used

| Location | Example |
|---|---|
| Narrative step `text` | `"Hello, {{ player.name }}!"` |
| `xp_grant.amount` | `"{{ roll(10, 50) }}"` |
| `stat_change.amount` | `"{{ player.stats.luck }}"` |
| `item_drop.count` | `"{{ roll(1, 3) }}"` |

Templates are **opt-in**: plain strings without `{{` or `{%` pass through unchanged.

### Player Context

Inside a template you have access to:

```
player.name          — character name (str)
player.level         — current level (int)
player.hp            — current hit points (int)
player.max_hp        — maximum hit points (int)
player.stats.<name>  — any declared stat by name (int, float, bool, or str)
player.milestones.has("<name>")  — true if player holds the milestone (bool)
player.pronouns.subject          — e.g. "they" / "she" / "he"
player.pronouns.object           — e.g. "them" / "her" / "him"
player.pronouns.possessive       — e.g. "their" / "her" / "his"
player.pronouns.possessive_standalone  — e.g. "theirs" / "hers" / "his"
player.pronouns.reflexive        — e.g. "themselves" / "herself" / "himself"
player.pronouns.uses_plural_verbs — true for they/them (bool)
```

### Built-in Functions

| Function | Description | Example |
|---|---|---|
| `roll(low, high)` | Random integer between `low` and `high` inclusive | `{{ roll(1, 20) }}` |
| `choice(seq)` | Pick one element at random from a list | `{{ choice(["fire","ice","wind"]) }}` |
| `random()` | Float in [0.0, 1.0) | `{{ random() }}` |
| `sample(seq, n)` | Pick `n` elements at random (no repeats) | `{{ sample(items, 2) }}` |
| `now()` | Current UTC datetime | `{{ now().year }}` |
| `today()` | Current UTC date | `{{ today() }}` |
| `clamp(val, lo, hi)` | Clamp value to [lo, hi] | `{{ clamp(player.stats.strength, 0, 20) }}` |
| `min(a, b)` | Minimum of two values | `{{ min(10, player.stats.speed) }}` |
| `max(a, b)` | Maximum of two values | `{{ max(0, player.stats.gold) }}` |
| `round(n)` | Round to nearest integer | `{{ round(x) }}` |
| `floor(n)` | Round down | `{{ floor(x) }}` |
| `ceil(n)` | Round up | `{{ ceil(x) }}` |
| `abs(n)` | Absolute value | `{{ abs(player.stats.debt) }}` |
| `int(x)` | Convert to integer | `{{ int(x) }}` |
| `str(x)` | Convert to string | `{{ str(player.level) }}` |
| `len(seq)` | Length of a sequence | `{{ len(items) }}` |
| `range(n)` | Integer range | `{% for i in range(3) %}` |
| `sum(seq)` | Sum a sequence | `{{ sum(values) }}` |

**Calendar and astronomical functions** (all accept a `datetime.date` from `today()`):

| Function | Returns | Example |
|---|---|---|
| `season(date)` | `"spring"`, `"summer"`, `"autumn"`, or `"winter"` | `{{ season(today()) }}` |
| `month_name(date)` | Full month name | `{{ month_name(today()) }}` |
| `day_name(date)` | Day of week | `{{ day_name(today()) }}` |
| `week_number(date)` | ISO week number (1–53) | `{{ week_number(today()) }}` |
| `mean(values)` | Arithmetic mean | `{{ mean([10, 20, 30]) }}` |
| `zodiac_sign(date)` | Western zodiac sign | `{{ zodiac_sign(today()) }}` |
| `chinese_zodiac(date)` | Chinese zodiac animal | `{{ chinese_zodiac(today()) }}` |
| `moon_phase(date)` | Moon phase description | `{{ moon_phase(today()) }}` |

### Built-in Filters

| Filter | Description | Example |
|---|---|---|
| `stat_modifier` | Convert stat to `+n`/`-n` modifier | `{{ player.stats.strength \| stat_modifier }}` |
| `pluralize(singular, plural?)` | Returns `singular` if piped value is 1, else `plural` | `{{ count \| pluralize("wolf","wolves") }}` |
| `upper` | Uppercase the string | `{{ player.name \| upper }}` |
| `capitalize` | Capitalize first letter | `{{ player.pronouns.subject \| capitalize }}` |
| `lower` | Lowercase the string | `{{ player.name \| lower }}` |

### Pronoun Placeholders

Instead of writing Jinja2 expressions for pronouns, use the **shorthand placeholders**.
Capitalisation of the placeholder controls capitalisation of the output.

| Placeholder | Expands to | Example output (they/them) |
|---|---|---|
| `{they}` | subject pronoun | `they` |
| `{They}` | subject pronoun, capitalized | `They` |
| `{THEY}` | subject pronoun, uppercase | `THEY` |
| `{them}` | object pronoun | `them` |
| `{their}` | possessive adjective | `their` |
| `{is}` or `{are}` | `is`/`are` based on pronoun set | `are` |
| `{was}` or `{were}` | `was`/`were` based on pronoun set | `were` |
| `{has}` or `{have}` | `has`/`have` based on pronoun set | `have` |

Examples:

```yaml
text: "{They} {are} a brave adventurer named {{ player.name }}."
# they/them → "They are a brave adventurer named Hero."
# she/her   → "She is a brave adventurer named Hero."
# he/him    → "He is a brave adventurer named Hero."
```

### Template Conditionals

Use Jinja2 `{% if %}` blocks for conditional narrative:

```yaml
text: |
  {% if player.milestones.has('hero-of-the-realm') %}
  The crowd cheers as {{ player.name }} approaches!
  {% else %}
  A stranger enters the tavern.
  {% endif %}
```

### Validation

Run `oscilla validate` (or `uv run oscilla validate`) to check your content.
Template syntax errors and unknown context references are reported with the file and field where the error occurred.

---

*For more on pronouns and custom pronoun sets, see [Pronouns](./pronouns.md).*
*For engine implementation details, see [Game Engine Documentation](../dev/game-engine.md).*
