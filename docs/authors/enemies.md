# Enemies

An enemy manifest defines everything needed to run a combat encounter: the combatant's name, stats, what skills it uses (if any), and what loot it drops on defeat. Adventures reference enemies by name in `combat` steps.

---

## Basic Structure

```yaml
apiVersion: oscilla/v1
kind: Enemy
metadata:
  name: dungeon-skeleton
spec:
  displayName: "Dungeon Skeleton"
  description: "The animated remains of a long-dead adventurer. Still wearing its gear."
  stats:
    hp: 40
    attack: 12
    defense: 5
  on_defeat_effects:
    - type: stat_change
      stat: xp
      amount: 140
  loot:
    - count: 1
      method: weighted
      entries:
        - item: bone-fragment
          weight: 60
        - item: rusty-dagger
          weight: 25
        - item: ancient-coin
          weight: 15
```

`metadata.name` is what you use in adventure `combat` steps: `enemy: dungeon-skeleton`.

---

## Combat Stats

Enemy stats are declared as a free-form dictionary under `spec.stats`. The key names you use must match whatever stat names your [CombatSystem](./combat-systems.md) formulas reference.

```yaml
spec:
  stats:
    hp: 40
    attack: 12
    defense: 5
    speed: 8
```

The stat names and their values are entirely yours to define. A combat system that uses `enemy_stats.get('hp', 0)` in its formulas expects an `hp` stat. One using a dice-pool system might only need `attack_dice: 4`. You are not locked into any particular vocabulary.

Design enemies with meaningful tradeoffs:

- **Glass cannons**: high attack, low defense, low HP — hit hard but fall quickly
- **Tanks**: moderate attack, high defense or high HP — slow fights that drain resources
- **Bosses**: high across the board — require the player to come prepared

The semantic validator warns you at load time if an enemy is missing a stat that the applicable CombatSystem's formulas reference by name.

---

## Defeat Effects

`on_defeat_effects` lists effects that fire when the enemy is defeated, before loot is awarded and before the `on_win` branch runs. Use it for XP grants, story milestones, or any other reward effects:

```yaml
spec:
  on_defeat_effects:
    - type: stat_change
      stat: xp
      amount: 140
    - type: milestone_grant
      milestone: skeleton-slain
```

Any [effect](./effects.md) is valid here. For XP, `stat_change` targeting a character XP stat is the standard approach.

---

## Migrating from the Old Schema

If your manifests use the old `hp`, `attack`, `defense`, and `xp_reward` top-level fields:

```yaml
# Old format (no longer valid)
spec:
  hp: 40
  attack: 12
  defense: 5
  xp_reward: 140
```

Replace them with the new format:

```yaml
# New format
spec:
  stats:
    hp: 40
    attack: 12
    defense: 5
  on_defeat_effects:
    - type: stat_change
      stat: xp
      amount: 140
```

The stat key names in `stats:` must match what your `CombatSystem` formulas expect. You also need a `CombatSystem` manifest in your game package — see [Combat Systems](./combat-systems.md).

---

## Loot

The `loot` field defines what items the enemy drops when defeated. It uses the same group-based structure as standalone [Loot Tables](./loot-tables.md).

```yaml
loot:
  - count: 1
    method: weighted
    entries:
      - item: goblin-ear
        weight: 80 # most common drop
      - item: goblin-sword
        weight: 15
      - item: golden-ring
        weight: 5 # rare drop
```

The engine resolves all groups automatically when the player wins the combat — no `item_drop` effect needed in the `on_win` branch.

An empty `loot: []` means the enemy drops nothing.

Multiple groups can be combined for enemies that always drop certain items alongside a randomized pool:

```yaml
loot:
  # Fixed drop every kill
  - count: 1
    entries:
      - item: enemy-essence
        weight: 100
  # Bonus item from a weighted pool
  - count: 1
    method: weighted
    entries:
      - item: common-material
        weight: 70
      - item: rare-core
        weight: 30
```

See [Loot Tables](./loot-tables.md) for complete documentation on groups, entries, `count`, `method`, `amount`, conditional groups, and template expressions.

---

## Enemy Skills

Enemies can use skills automatically during combat. This allows enemies to heal, apply debuffs, or trigger special attacks on a schedule.

```yaml
spec:
  displayName: "Goblin Shaman"
  description: "A small green figure clutching a bone staff."
  stats:
    hp: 35
    attack: 8
    defense: 3
  on_defeat_effects:
    - type: stat_change
      stat: xp
      amount: 90
  skills:
    - skill_ref: poison-spit
      use_every_n_turns: 2 # uses the skill at the start of every 2nd turn
    - skill_ref: minor-heal
      use_every_n_turns: 0 # 0 = reserved for future AI logic; currently unused
  skill_resources:
    mana: 10 # starting resource value for skill costs
```

`use_every_n_turns: 2` means the skill fires on turn 2, 4, 6, and so on. `use_every_n_turns: 1` fires every single turn.

Skills referenced by `skill_ref` must match the name of a loaded Skill manifest. The validator catches unknown refs at load time.

`skill_resources` sets non-persisted starting values for resource stats (like mana or stamina). These reset at the start of each combat encounter — enemies don't carry resource state between fights. Resource stats are defined in [Game Configuration §stats](./game-configuration.md#stats).

---

## Enemy Placement

A common convention is to place enemy manifests in `enemies/` directories near the region or location they serve:

```
regions/dungeon/enemies/dungeon-lich.yaml                     ← dungeon enemies, by convention
regions/dungeon/locations/vault/enemies/vault-guardian.yaml   ← vault enemies, by convention
```

Because the engine discovers manifests by scanning all `.yaml` files recursively, enemies can live anywhere in your package. An enemy being present in a folder doesn't mean it appears automatically — adventures reference enemies by name in their `combat` steps:

```yaml
- type: combat
  enemy: vault-guardian
  on_win:
    effects:
      - type: end_adventure
        outcome: completed
```

---

## Reference

### Enemy manifest fields

| Field                    | Required | Default | Description                                  |
| ------------------------ | -------- | ------- | -------------------------------------------- |
| `metadata.name`          | yes      | —       | Identifier used in adventure `combat` steps  |
| `spec.displayName`       | yes      | —       | Name shown to the player during combat       |
| `spec.description`       | no       | `""`    | Flavor text                                  |
| `spec.stats`             | no       | `{}`    | Free-form dict of stat name → starting value |
| `spec.on_defeat_effects` | no       | `[]`    | Effects fired when this enemy is defeated    |
| `spec.loot`              | no       | `[]`    | Loot groups resolved on enemy defeat         |
| `spec.skills`            | no       | `[]`    | Skill entries for automatic skill use        |
| `spec.skill_resources`   | no       | `{}`    | Starting resource values for skill costs     |

### Skill entry fields

| Field               | Required | Default | Description                                                 |
| ------------------- | -------- | ------- | ----------------------------------------------------------- |
| `skill_ref`         | yes      | —       | `metadata.name` of a [Skill](./skills.md) manifest          |
| `use_every_n_turns` | no       | `0`     | Use frequency in combat turns; 0 = AI-only (not yet active) |

---

_See [Combat Systems](./combat-systems.md) for how damage formulas and defeat conditions are declared._
_See [Adventures](./adventures.md) for how enemies are referenced in `combat` steps._
_See [Skills](./skills.md) for skill and buff manifest syntax._

---

## Loot

The `loot` field defines what items the enemy drops when defeated. It uses the same group-based structure as standalone [Loot Tables](./loot-tables.md).

```yaml
loot:
  - count: 1
    method: weighted
    entries:
      - item: goblin-ear
        weight: 80 # most common drop
      - item: goblin-sword
        weight: 15
      - item: golden-ring
        weight: 5 # rare drop
```

The engine resolves all groups automatically when the player wins the combat — no `item_drop` effect needed in the `on_win` branch.

An empty `loot: []` means the enemy drops nothing.

Multiple groups can be combined for enemies that always drop certain items alongside a randomized pool:

```yaml
loot:
  # Fixed drop every kill
  - count: 1
    entries:
      - item: enemy-essence
        weight: 100
  # Bonus item from a weighted pool
  - count: 1
    method: weighted
    entries:
      - item: common-material
        weight: 70
      - item: rare-core
        weight: 30
```

See [Loot Tables](./loot-tables.md) for complete documentation on groups, entries, `count`, `method`, `amount`, conditional groups, and template expressions.

---

## Enemy Skills

Enemies can use skills automatically during combat. This allows enemies to heal, apply debuffs, or trigger special attacks on a schedule.

```yaml
spec:
  displayName: "Goblin Shaman"
  description: "A small green figure clutching a bone staff."
  hp: 35
  attack: 8
  defense: 3
  xp_reward: 90
  skills:
    - skill_ref: poison-spit
      use_every_n_turns: 2 # uses the skill at the start of every 2nd turn
    - skill_ref: minor-heal
      use_every_n_turns: 0 # 0 = reserved for future AI logic; currently unused
  skill_resources:
    mana: 10 # starting resource value for skill costs
```

`use_every_n_turns: 2` means the skill fires on turn 2, 4, 6, and so on. `use_every_n_turns: 1` fires every single turn.

Skills referenced by `skill_ref` must match the name of a loaded Skill manifest. The validator catches unknown refs at load time.

`skill_resources` sets non-persisted starting values for resource stats (like mana or stamina). These reset at the start of each combat encounter — enemies don't carry resource state between fights. Resource stats are defined in [Game Configuration §stats](./game-configuration.md#stats).

---

## Enemy Placement

A common convention is to place enemy manifests in `enemies/` directories near the region or location they serve:

```
regions/dungeon/enemies/dungeon-lich.yaml                     ← dungeon enemies, by convention
regions/dungeon/locations/vault/enemies/vault-guardian.yaml   ← vault enemies, by convention
```

Because the engine discovers manifests by scanning all `.yaml` files recursively, enemies can live anywhere in your package. An enemy being present in a folder doesn't mean it appears automatically — adventures reference enemies by name in their `combat` steps:

```yaml
- type: combat
  enemy: vault-guardian
  on_win:
    effects:
      - type: xp_grant
        amount: 300
```

---

## Reference

### Enemy manifest fields

| Field                  | Required | Default | Description                                 |
| ---------------------- | -------- | ------- | ------------------------------------------- |
| `metadata.name`        | yes      | —       | Identifier used in adventure `combat` steps |
| `spec.displayName`     | yes      | —       | Name shown to the player during combat      |
| `spec.description`     | no       | `""`    | Flavor text                                 |
| `spec.hp`              | yes      | —       | Starting hit points (min 1)                 |
| `spec.attack`          | yes      | —       | Attack power per round (min 0)              |
| `spec.defense`         | yes      | —       | Damage reduction (min 0)                    |
| `spec.xp_reward`       | yes      | —       | XP granted to player on defeat (min 0)      |
| `spec.loot`            | no       | `[]`    | Loot groups resolved on enemy defeat        |
| `spec.skills`          | no       | `[]`    | Skill entries for automatic skill use       |
| `spec.skill_resources` | no       | `{}`    | Starting resource values for skill costs    |

### Loot group and entry fields

See [Loot Tables §reference](./loot-tables.md#reference) for the complete field reference for `LootGroup` and `LootEntry`.

### Skill entry fields

| Field               | Required | Default | Description                                                 |
| ------------------- | -------- | ------- | ----------------------------------------------------------- |
| `skill_ref`         | yes      | —       | `metadata.name` of a [Skill](./skills.md) manifest          |
| `use_every_n_turns` | no       | `0`     | Use frequency in combat turns; 0 = AI-only (not yet active) |

---

_See [Adventures](./adventures.md) for how enemies are referenced in `combat` steps._
_See [Skills](./skills.md) for skill and buff manifest syntax._
