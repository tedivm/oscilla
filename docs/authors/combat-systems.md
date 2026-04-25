# Combat Systems

A **CombatSystem** manifest defines every aspect of how combat plays out in your game: who acts first, how damage is calculated, when combatants are defeated, what stats exist during a fight, and what happens at each lifecycle stage. Adventures reference enemies; the combat system determines how those encounters resolve.

---

## Overview

Before the combat system refactor, enemies carried hardcoded `hp`, `attack`, `defense`, and `xp_reward` stats. Combat resolution was fixed in the engine. Now, you declare a `CombatSystem` manifest and every game gets its own combat model — from simple HP-based brawls to dice-pool skirmishes to simultaneous-resolution card games.

A minimal combat system looks like this:

```yaml
apiVersion: oscilla/v1
kind: CombatSystem
metadata:
  name: standard-combat
spec:
  player_defeat_condition:
    type: character_stat
    name: hp
    lte: 0
  enemy_defeat_condition:
    type: enemy_stat
    stat: hp
    lte: 0
  turn_order: player_first
  player_turn_mode: auto
  player_damage_formulas:
    - formula: "{{ clamp(player.get('strength', 5) - enemy_stats.get('defense', 0), 1, 9999) * -1 }}"
      target_stat: hp
      target: enemy
      display: "Attack"
  enemy_damage_formulas:
    - formula: "{{ clamp(enemy_stats.get('attack', 0), 0, 9999) * -1 }}"
      target_stat: hp
      target: player
      display: "Enemy strikes"
```

Point your game at it by setting `default_combat_system` in `game.yaml`, or reference it directly on a `combat` step.

---

## Defeat Conditions

These two fields control when the fight ends:

```yaml
spec:
  player_defeat_condition:
    type: character_stat
    name: hp
    lte: 0
  enemy_defeat_condition:
    type: enemy_stat
    stat: hp
    lte: 0
```

`player_defeat_condition` uses any standard [condition](./conditions.md) that can evaluate against the player's character stats. `enemy_defeat_condition` uses an `enemy_stat` condition (see [Combat-Context Conditions](#combat-context-conditions)).

---

## Damage Formulas

Damage formulas are Jinja2 expressions that compute how much to change a stat each round. They live in three lists:

| Field                    | When it runs                  |
| ------------------------ | ----------------------------- |
| `player_damage_formulas` | During the player's turn      |
| `enemy_damage_formulas`  | During the enemy's turn       |
| `resolution_formulas`    | After both turns, every round |

Each entry is a `DamageFormulaEntry`:

```yaml
player_damage_formulas:
  - formula: "{{ clamp(player.get('strength', 5), 1, 9999) * -1 }}"
    target_stat: hp # which stat to modify
    target: enemy # whose stat dict — "player", "enemy", or "combat"
    display: "Attack" # optional label shown in combat log
    threshold_effects: [] # optional outcome bands (see below)
```

### Formula Context

Inside a formula string, you have access to:

| Variable       | Type             | Description                                                       |
| -------------- | ---------------- | ----------------------------------------------------------------- |
| `player`       | `dict[str, int]` | Player's effective stats (base + buffs)                           |
| `enemy_stats`  | `dict[str, int]` | Enemy stat dict from the enemy manifest                           |
| `combat_stats` | `dict[str, int]` | Ephemeral combat-scoped stats (see [Combat Stats](#combat-stats)) |
| `turn_number`  | `int`            | The current round (starts at 1)                                   |

Use `.get(key, default)` when a stat might be absent — this prevents rendering errors and also satisfies the load-time formula validator.

### Formula Globals

All [template math functions](./templates.md) are available, plus these combat-specific dice functions:

| Function                        | Signature               | Description                                                             |
| ------------------------------- | ----------------------- | ----------------------------------------------------------------------- |
| `rollpool(n, sides, threshold)` | `(int, int, int) → int` | Roll `n` dice of `sides` sides; return count where result ≥ `threshold` |
| `rollsum(n, sides)`             | `(int, int) → int`      | Roll `n` dice of `sides` sides; return their sum                        |
| `keephigh(n, sides, k)`         | `(int, int, int) → int` | Roll `n` dice; keep highest `k`; return their sum                       |
| `clamp(x, lo, hi)`              | `(int, int, int) → int` | Return `x` clamped to `[lo, hi]` inclusive                              |
| `roll(low, high)`               | `(int, int) → int`      | Return a random integer in `[low, high]`                                |
| `min(a, b)`                     | —                       | Standard minimum                                                        |
| `max(a, b)`                     | —                       | Standard maximum                                                        |
| `abs(x)`                        | —                       | Absolute value                                                          |

> **Damage is negative**: formulas must return a negative number to deal damage. `clamp(attack, 0, 9999) * -1` produces `-attack`.

### Threshold Effects

A `DamageFormulaEntry` can fire conditional effects based on the magnitude of the formula result:

```yaml
player_damage_formulas:
  - formula: "{{ rollsum(2, 6) * -1 }}"
    target_stat: hp
    target: enemy
    threshold_effects:
      - max: -10 # if result ≤ -10 (heavy hit)
        effects:
          - type: stat_change
            target: enemy
            stat: stun_turns
            amount: 1
      - min: -2 # if result ≥ -2 (glancing blow)
        max: -1
        effects:
          - type: narrative
            text: "A glancing blow."
```

Bands are checked in order; the first match fires. Both `min` and `max` are inclusive bounds against the raw formula result (before being applied to stats). At least one of `min` or `max` is required per band.

---

## Turn Order

The `turn_order` field controls who acts first each round:

| Value          | Behavior                                                   |
| -------------- | ---------------------------------------------------------- |
| `player_first` | Player acts, then enemy (default)                          |
| `enemy_first`  | Enemy acts, then player                                    |
| `simultaneous` | Both act at the same time; defeat checked after resolution |
| `initiative`   | Compared at start of each round; higher result goes first  |

### Initiative Mode

When `turn_order: initiative`, both combatants roll before acting:

```yaml
spec:
  turn_order: initiative
  player_initiative_formula: "{{ player.get('dexterity', 5) + roll(1, 6) }}"
  enemy_initiative_formula: "{{ enemy_stats.get('speed', 5) }}"
  initiative_tie: player_first # or "enemy_first" or "simultaneous"
```

Both formula strings run in a `CombatFormulaContext`. The higher result determines who acts first that round.

### Simultaneous Mode

When `turn_order: simultaneous`, both actors always complete their turns. Defeat is checked only after `resolution_formulas` and `on_round_end`. When both combatants are defeated on the same round, `simultaneous_defeat_result` decides the outcome:

```yaml
spec:
  turn_order: simultaneous
  simultaneous_defeat_result: player_wins # or "enemy_wins" or "draw"
```

---

## Player Turn Mode

| Value    | Behavior                                                          |
| -------- | ----------------------------------------------------------------- |
| `auto`   | Engine runs all `player_damage_formulas` automatically each round |
| `choice` | Player selects from a menu of skills and items each round         |

In `choice` mode, `player_damage_formulas` must be empty — move damage to skill manifests with `combat_damage_formulas` instead. The menu is built from:

1. **System skills** — entries in `system_skills`, optionally filtered by `condition`
2. **Player skills** — skills where `contexts` intersects `skill_contexts`
3. **Combat items** — usable items in the player's inventory where `contexts` intersects `skill_contexts`
4. **Do Nothing** — always present

```yaml
spec:
  player_turn_mode: choice
  skill_contexts:
    - combat
  system_skills:
    - skill: basic-attack
    - skill: power-strike
      condition:
        type: character_stat
        name: rage
        gte: 5
```

`system_skills` entries fire their skill's effects directly; they are not skills the player permanently owns.

---

## Combat Stats

`combat_stats` declares ephemeral stats that exist only for the duration of a single combat encounter. They live in `combat_stats[name]` and are discarded when combat ends — they are never written to the player's permanent stats.

```yaml
spec:
  combat_stats:
    - name: rage
      default: 0
    - name: focus_stacks
      default: 0
```

Access them in formulas as `combat_stats.get('rage', 0)`. Modify them with `stat_change target='combat'`.

---

## Lifecycle Hooks

Effect lists that fire automatically at key points in a combat encounter:

| Hook                | When it fires                                                                   |
| ------------------- | ------------------------------------------------------------------------------- |
| `on_combat_start`   | Once at the very start, before the first round (new combat only, not on resume) |
| `on_combat_end`     | Once when combat ends for any reason                                            |
| `on_combat_victory` | After `on_combat_end`, when the player wins                                     |
| `on_combat_defeat`  | After `on_combat_end`, when the player is defeated                              |
| `on_round_end`      | At the end of every round, after all action phases                              |

```yaml
spec:
  on_combat_start:
    - type: stat_change
      target: combat
      stat: rage
      amount: 0 # reset rage

  on_round_end:
    - type: stat_change
      target: combat
      stat: rage
      amount: 1 # gain 1 rage per round
```

---

## Resolution Formulas

`resolution_formulas` run after both actor phases every round. In sequential modes they only run when neither combatant was defeated mid-round; in simultaneous mode they always run.

```yaml
spec:
  resolution_formulas:
    - formula: "{{ combat_stats.get('burn_stacks', 0) * -2 }}"
      target_stat: hp
      target: enemy
      display: "Burn damage"
```

---

## Per-Step Overrides

A `combat` adventure step can override any `CombatSystemSpec` field for that encounter only:

```yaml
steps:
  - type: combat
    enemy: dragon-boss
    combat_system: boss-combat # use a different system for this fight
    combat_overrides:
      turn_order: enemy_first # the dragon always goes first
      on_combat_start:
        - type: stat_change
          target: enemy
          stat: rage
          amount: 10 # boss starts enraged
```

Fields not listed in `combat_overrides` are taken from the base `CombatSystem` manifest unchanged.

---

## Full Field Reference

### `CombatSystemSpec`

| Field                        | Type      | Default          | Description                                                            |
| ---------------------------- | --------- | ---------------- | ---------------------------------------------------------------------- |
| `player_defeat_condition`    | Condition | required         | When this is true, the player loses                                    |
| `enemy_defeat_condition`     | Condition | required         | When this is true, the enemy is defeated                               |
| `player_damage_formulas`     | list      | `[]`             | Formula entries run during the player's turn                           |
| `enemy_damage_formulas`      | list      | `[]`             | Formula entries run during the enemy's turn                            |
| `resolution_formulas`        | list      | `[]`             | Formula entries run after both turns each round                        |
| `player_turn_mode`           | string    | `"auto"`         | `"auto"` or `"choice"`                                                 |
| `turn_order`                 | string    | `"player_first"` | `"player_first"`, `"enemy_first"`, `"simultaneous"`, or `"initiative"` |
| `player_initiative_formula`  | string    | `null`           | Required when `turn_order: initiative`                                 |
| `enemy_initiative_formula`   | string    | `null`           | Required when `turn_order: initiative`                                 |
| `initiative_tie`             | string    | `"player_first"` | `"player_first"`, `"enemy_first"`, or `"simultaneous"`                 |
| `skill_contexts`             | list      | `[]`             | Context strings used to filter player skills in choice mode            |
| `system_skills`              | list      | `[]`             | Built-in skills shown in the choice menu                               |
| `combat_stats`               | list      | `[]`             | Ephemeral per-combat stat declarations                                 |
| `simultaneous_defeat_result` | string    | `"player_wins"`  | Outcome when both sides are defeated simultaneously                    |
| `on_combat_start`            | list      | `[]`             | Effects fired once at combat start                                     |
| `on_combat_end`              | list      | `[]`             | Effects fired when combat ends                                         |
| `on_combat_victory`          | list      | `[]`             | Effects fired on player victory                                        |
| `on_combat_defeat`           | list      | `[]`             | Effects fired on player defeat                                         |
| `on_round_end`               | list      | `[]`             | Effects fired at the end of every round                                |

### `DamageFormulaEntry`

| Field               | Type   | Default  | Description                                                                         |
| ------------------- | ------ | -------- | ----------------------------------------------------------------------------------- |
| `formula`           | string | required | Jinja2 expression returning an int                                                  |
| `target_stat`       | string | `null`   | Stat name to apply the result to (required unless `threshold_effects` is non-empty) |
| `target`            | string | `null`   | `"player"`, `"enemy"`, or `"combat"` — whose stat dict to modify                    |
| `display`           | string | `null`   | Label shown in the combat log                                                       |
| `threshold_effects` | list   | `[]`     | Outcome bands; the first matching band fires                                        |

### `CombatStatEntry`

| Field     | Type   | Default  | Description                   |
| --------- | ------ | -------- | ----------------------------- |
| `name`    | string | required | Stat name                     |
| `default` | int    | `0`      | Initial value at combat start |

### `SystemSkillEntry`

| Field       | Type      | Default  | Description                                             |
| ----------- | --------- | -------- | ------------------------------------------------------- |
| `skill`     | string    | required | Skill manifest name                                     |
| `condition` | Condition | `null`   | If set, the skill is hidden when the condition is false |

---

## Combat-Context Conditions

Two conditions are only meaningful inside combat. Using them outside combat returns `false` with a warning.

### `enemy_stat`

True when a named enemy stat satisfies a comparison. Used in `enemy_defeat_condition`.

```yaml
enemy_defeat_condition:
  type: enemy_stat
  stat: hp
  lte: 0
```

Operators: `gte`, `lte`, `gt`, `lt`, `eq`.

### `combat_stat`

True when a named combat stat satisfies a comparison. Use this in `player_defeat_condition` when your game uses a custom defeat mechanic.

```yaml
player_defeat_condition:
  type: combat_stat
  stat: willpower
  lte: 0
```

---

## Assigning a Combat System

### Default for the whole game

Set `default_combat_system` in `game.yaml`:

```yaml
spec:
  default_combat_system: standard-combat
```

Every `combat` step that doesn't specify `combat_system` uses this.

### Auto-promotion

If your game registers exactly one `CombatSystem` manifest and sets no `default_combat_system`, the engine auto-promotes that single system. This is the easiest setup for games with only one combat style.

### Per-step override

Specify `combat_system` directly on a `combat` step to use a different system for that encounter:

```yaml
steps:
  - type: combat
    enemy: dungeon-boss
    combat_system: boss-rules
```

---

_Next: [Enemies](./enemies.md) — how to define enemy stats and defeat rewards._
