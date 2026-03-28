# Content Authoring Guide

This guide covers creating game content for Oscilla using YAML manifest files. Content authors define adventures, characters, items, and game rules through structured configuration files.

## Getting Started

Content is organized in a directory structure like:

```
content/
├── game.yaml                  # Global game settings
├── character_config.yaml      # Player stats and defaults
├── regions/                   # Geographic areas
├── locations/                 # Specific places within regions
├── adventures/                # Interactive scenarios
├── enemies/                   # Combat opponents
├── items/                     # Equipment and consumables
├── recipes/                   # Crafting formulas
├── quests/                    # Multi-stage storylines
└── classes/                   # Character classes (placeholder)
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

**Stat Types**: `int`, `float`, `str`, `bool`

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

Equipment, consumables, and other objects:

```yaml
apiVersion: game/v1
kind: Item
metadata:
  name: iron-sword
spec:
  displayName: "Iron Sword"
  description: "A well-made blade with a leather grip."

  kind: weapon              # Required: weapon, armor, consumable, quest, material, prestige
  stackable: false          # Can multiple copies share one inventory slot?

  equipment_slot: weapon    # Optional: slot name for equippable items
  value: 150                # Optional: base gold value
```

**Item Kinds**:

- `weapon`: Combat equipment
- `armor`: Protective gear
- `consumable`: Usable items (potions, food)
- `quest`: Story-related items
- `material`: Crafting components
- `prestige`: Special achievement items

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

**Automatic Leveling**: XP grants trigger level-up calculations based on game configuration.

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

**Drop Mechanics**: Each roll selects one item based on relative weights. Higher weights = higher chance.

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
- `Recipe`: Crafting formulas
- `Quest`: Multi-stage storylines
- `Class`: Character classes (placeholder)

### All Condition Types

**Leaf Conditions**: `level`, `milestone`, `item`, `character_stat`, `prestige_count`, `class`, `enemies_defeated`, `locations_visited`, `adventures_completed`

**Logical Operators**: `all`, `any`, `not`

### All Step Types

**Interactive Steps**: `narrative`, `combat`, `choice`, `stat_check`

### All Effect Types

**State Changes**: `xp_grant`, `item_drop`, `milestone_grant`
**Flow Control**: `end_adventure`, `goto`

---

*For engine implementation details, see [Game Engine Documentation](../dev/game-engine.md).*
