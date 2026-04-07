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
  hp: 40
  attack: 12
  defense: 5
  xp_reward: 140
  loot:
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

The four core stats control how combat plays out:

| Stat        | Description                                           |
| ----------- | ----------------------------------------------------- |
| `hp`        | How many hit points the enemy starts with (minimum 1) |
| `attack`    | Base attack power each round                          |
| `defense`   | Reduces incoming player damage                        |
| `xp_reward` | XP granted to the player on defeat                    |

Damage per round is roughly `attacker.attack - defender.defense`, clamped to a minimum of 0. This means a well-armored enemy with high defense can soak small hits entirely.

Design enemies with meaningful tradeoffs:

- **Glass cannons**: high attack, low defense, low HP — hit hard but fall quickly
- **Tanks**: moderate attack, high defense or high HP — slow fights that drain resources
- **Bosses**: high across the board — require the player to come prepared

---

## Loot Tables

The `loot` list defines what the enemy can drop when defeated. It is a weighted pool — the engine picks one item using the relative weights.

```yaml
loot:
  - item: goblin-ear
    weight: 80 # most common drop
  - item: goblin-sword
    weight: 15
  - item: golden-ring
    weight: 5 # rare drop
```

The number of items dropped per kill is controlled by the [`item_drop` effect](./effects.md#dropping-items) on the combat step's `on_win` branch, **not** by the enemy manifest. The enemy just defines what items are available and their relative rarity. An `on_win` branch might reference the enemy's loot table or provide its own `item_drop` directly.

An empty `loot` list means the enemy drops nothing.

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
| `spec.loot`            | no       | `[]`    | Weighted loot table                         |
| `spec.skills`          | no       | `[]`    | Skill entries for automatic skill use       |
| `spec.skill_resources` | no       | `{}`    | Starting resource values for skill costs    |

### Loot entry fields

| Field    | Required | Description                                       |
| -------- | -------- | ------------------------------------------------- |
| `item`   | yes      | `metadata.name` of an [Item](./items.md) manifest |
| `weight` | yes      | Relative probability (min 1)                      |

### Skill entry fields

| Field               | Required | Default | Description                                                 |
| ------------------- | -------- | ------- | ----------------------------------------------------------- |
| `skill_ref`         | yes      | —       | `metadata.name` of a [Skill](./skills.md) manifest          |
| `use_every_n_turns` | no       | `0`     | Use frequency in combat turns; 0 = AI-only (not yet active) |

---

_See [Adventures](./adventures.md) for how enemies are referenced in `combat` steps._
_See [Skills](./skills.md) for skill and buff manifest syntax._
