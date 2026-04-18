# Passive Effects

Passive effects are always-on or conditionally-active modifiers that apply automatically based on the player's state. They live in `game.yaml` rather than in adventure steps — the engine evaluates them continuously and applies any that match.

Use passive effects when a game-wide rule should apply without any authoring at the adventure level: a bonus unlocked by a milestone, a skill that appears at high level, a permanent stat that upgrades as the player progresses.

---

## Declaring Passive Effects

Add `passive_effects` to `game.yaml` under `spec`:

```yaml
apiVersion: oscilla/v1
kind: Game
metadata:
  name: my-game
spec:
  displayName: "My Adventure Game"

  passive_effects:
    - condition:
        type: milestone
        name: hero-of-the-realm
      stat_modifiers:
        - stat: charisma
          amount: 2
      skill_grants:
        - inspire
```

Each entry has three optional fields:

| Field            | Type                 | Description                                                                                     |
| ---------------- | -------------------- | ----------------------------------------------------------------------------------------------- |
| `condition`      | Condition \| null    | If set, the effect only applies when the condition is true. If null, the effect always applies. |
| `stat_modifiers` | list of StatModifier | Stat bonuses applied while the condition holds.                                                 |
| `skill_grants`   | list of string       | Skill manifest names granted while the condition holds.                                         |

---

## Condition Restrictions

Passive effects now receive the content registry at evaluation time, so most condition types work correctly. However, two condition types are **hard errors** (`LoadError`) at validation time because using them in a passive effect would cause infinite recursion:

- `character_stat` with `stat_source: effective` — computing effective stats requires effective stats
- `skill` — computing available skills depends on passive effect results

These restrictions also apply **transitively** through `type: custom` references: if a `CustomCondition`'s body (or any custom condition it references) contains a banned type, the loader rejects the passive effect with a hard error.

All other condition types work fully, including `item_held_label` and `any_item_equipped`:

```yaml
# ✓ Safe: milestone check
- condition:
    type: milestone
    name: dragon-slayer

# ✓ Safe: level check
- condition:
    type: level
    gte: 10

# ✓ Safe: item presence (checks stacks and instances)
- condition:
    type: item
    item_ref: lucky-coin
    quantity: 1

# ✓ Safe: specific item equipped
- condition:
    type: item_equipped
    item: amulet-of-power

# ✓ Safe: character stat (base)
- condition:
    type: character_stat
    stat: wisdom
    gte: 20
    stat_source: base

# ✓ Safe: item_held_label
- condition:
    type: item_held_label
    label: legendary

# ✓ Safe: custom condition (provided its body contains no banned types)
- condition:
    type: custom
    name: milestone-gate

# ✗ Hard error: stat_source: effective
- condition:
    type: character_stat
    stat: strength
    gte: 15
    stat_source: effective # triggers LoadError

# ✗ Hard error: skill condition
- condition:
    type: skill
    skill_ref: arcane-shield
    mode: available # triggers LoadError
```

---

## Stat Modifiers

Each `stat_modifier` entry adds a fixed amount to the named stat while the condition holds:

```yaml
stat_modifiers:
  - stat: strength
    amount: 3
  - stat: defense
    amount: -1 # negative amounts reduce the stat
```

Stats used here must be declared in [`character_config.yaml`](./game-configuration.md#stats). The modifier applies every time
`effective_stats()` is called — it does not permanently alter `player.stats`.

---

## Skill Grants

Each `skill_grant` entry adds a skill to the player's available skills while the condition holds.
The skill must be defined as a [`Skill` manifest](./skills.md#defining-a-skill) in the content package.

```yaml
skill_grants:
  - arcane-shield # Skill manifest name
  - mage-armor
```

Skills granted by passive effects appear in `available_skills()` but are not added to
`player.known_skills`. They disappear automatically when the condition is no longer met.

---

## Examples

### Unconditional Bonus

Always grant +1 to luck, no condition required:

```yaml
passive_effects:
  - stat_modifiers:
      - stat: luck
        amount: 1
```

### Milestone-Gated Skill

Grant a skill after the player earns a specific milestone:

```yaml
passive_effects:
  - condition:
      type: milestone
      name: guild-member
    skill_grants:
      - guild-discount
```

### Level Threshold Bonus

Apply a bonus once the player reaches level 10:

```yaml
passive_effects:
  - condition:
      type: level
      gte: 10
    stat_modifiers:
      - stat: max_hp_bonus
        amount: 20
```

### Multiple Effects

Multiple entries in `passive_effects` are evaluated independently.
Each one that matches adds its bonuses:

```yaml
passive_effects:
  - condition:
      type: level
      gte: 5
    stat_modifiers:
      - stat: strength
        amount: 1

  - condition:
      type: level
      gte: 10
    stat_modifiers:
      - stat: strength
        amount: 1 # stacks: level 10+ players get +2 total
```

---

_See [Game Configuration](./game-configuration.md) for where `passive_effects` lives in `game.yaml`._
_See [Conditions](./conditions.md) for the full condition syntax — and which condition types are safe to use here._
_See [Skills](./skills.md) for skill manifest syntax._
