# Loot Tables

A `LootTable` manifest describes a reusable pool of items that can be awarded to the player. Adventures reference a loot table by name so the same pool can be shared across many different locations and enemies.

---

## Anatomy of a Loot Table

```yaml
apiVersion: oscilla/v1
kind: LootTable
metadata:
  name: forest-chest
spec:
  displayName: "Forest Chest"
  description: "Miscellaneous gear found in woodland caches."
  groups:
    - count: 1
      method: weighted
      entries:
        - item: healing-herb
          weight: 60
          amount: 2
        - item: wooden-shield
          weight: 30
        - item: silver-coin
          weight: 10
          amount: 5
```

`metadata.name` is the identifier you use elsewhere: `loot_ref: forest-chest`.

---

## Groups and Entries

Loot is organized in two tiers:

- A **group** is an independent draw. All groups in a table fire on every use.
- An **entry** within a group is a candidate to be drawn. How many entries are drawn from a group is controlled by `count`.

```yaml
groups:
  - count: 1 # draw 1 entry from this group
    entries:
      - item: common-ore
        weight: 70
      - item: rare-gem
        weight: 30
  - count: 2 # draw 2 entries from this second group
    entries:
      - item: goblin-ear
        weight: 100
```

In the example above, every use of this table grants exactly one item from the first group **and** two items (possibly the same) from the second group.

---

## Count

`count` controls how many entries are drawn from a group. It defaults to `1`.

```yaml
- count: 3 # draw 3 entries
  entries:
    - item: silver-coin
      weight: 100
      amount: 1
```

`count` can also be a [Jinja2 template expression](./templates.md) so the draw count scales with player state:

```yaml
- count: "{{ [player.stats['level'], 1] | max }}"
  entries:
    - item: gold-coin
      weight: 100
```

Template values are clamped to `max(0, value)` — a negative template result is treated as `0` (no draws from that group).

---

## Method

`method` controls the sampling algorithm for a group:

| Value      | Behavior                                                                                                                               |
| ---------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| `weighted` | Draws **with** replacement. The same entry can appear multiple times. (default)                                                        |
| `unique`   | Draws **without** replacement. Each entry appears at most once. If `count` exceeds the pool size, `count` is clamped to the pool size. |

```yaml
- count: 2
  method: unique # guarantees two different items
  entries:
    - item: silver-dagger
      weight: 1
    - item: leather-gloves
      weight: 1
    - item: minor-potion
      weight: 1
```

Use `unique` when you want to reward a set of distinct items (e.g. a randomized starter pack) and `weighted` when repeated draws are fine (e.g. gathering materials).

---

## Amount

`amount` on an entry controls how many of that item are added per draw. It defaults to `1`.

```yaml
entries:
  - item: gold-coin
    weight: 100
    amount: 10 # granting 10 coins per draw
```

Like `count`, `amount` can be a template expression:

```yaml
entries:
  - item: gold-coin
    weight: 100
    amount: "{{ player.stats['level'] * 5 }}"
```

Template amounts are clamped to `max(0, value)`. An amount of `0` adds nothing but still counts as a draw.

---

## Conditions on Groups

A `requires` condition on a group gates the **entire group**. If the condition is not met, the group is skipped — no draws happen from it regardless of `count`.

```yaml
groups:
  - count: 1
    entries:
      - item: common-loot
        weight: 100
  - count: 1
    requires:
      type: milestone
      name: defeated-boss
    entries:
      - item: rare-reward
        weight: 100
```

The second group only fires after the player has earned the `defeated-boss` milestone. Any [condition type](./conditions.md) is supported.

---

## Conditions on Entries

A `requires` condition on an individual entry removes that entry from the draw pool **for this use**. Other entries in the same group are unaffected.

```yaml
groups:
  - count: 1
    entries:
      - item: basic-sword
        weight: 80
      - item: enchanted-sword
        weight: 20
        requires:
          type: item
          name: blacksmith-token # only available if player owns this item
```

If all entries in a group fail their conditions the group is silently skipped.

---

## Referencing a Loot Table from an Adventure

Use `loot_ref` on an `item_drop` effect:

```yaml
effects:
  - type: item_drop
    loot_ref: forest-chest
```

The loader validates that `forest-chest` exists and that all items referenced in its entries are loaded. Unknown refs produce a load error.

---

## Inline Groups in Adventures

You can skip the standalone manifest and supply groups inline on an `item_drop` effect. Useful for drops that are unique to one adventure:

```yaml
effects:
  - type: item_drop
    groups:
      - count: 1
        entries:
          - item: quest-key
            weight: 100
```

An `item_drop` effect must supply **exactly one** of `groups` (inline) or `loot_ref`. Providing both or neither is a validation error.

---

## Enemy Loot Drops

Enemy manifests declare their loot as a list of groups. The groups are resolved automatically when the player wins the combat encounter — no `item_drop` effect needed in the `on_win` branch.

```yaml
apiVersion: oscilla/v1
kind: Enemy
metadata:
  name: iron-golem
spec:
  displayName: "Iron Golem"
  hp: 80
  attack: 15
  defense: 10
  xp_reward: 200
  loot:
    - count: 1
      method: weighted
      entries:
        - item: iron-ingot
          weight: 70
          amount: 2
        - item: golem-core
          weight: 30
```

Enemy `loot` uses the same group/entry schema as `LootTableSpec.groups`. An empty `loot: []` means the enemy drops nothing. See [Enemies](./enemies.md) for full enemy documentation.

---

## Migration from the Old Flat `loot:` Syntax

Prior to the enhanced loot table system, adventures and enemies used a flat `loot:` list directly on `item_drop` effects:

```yaml
# Old — no longer valid
- type: item_drop
  count: 2
  loot:
    - item: healing-herb
      weight: 60
    - item: wooden-shield
      weight: 30
```

The new format wraps entries in a group:

```yaml
# New
- type: item_drop
  groups:
    - count: 2
      entries:
        - item: healing-herb
          weight: 60
        - item: wooden-shield
          weight: 30
```

For multi-count drops the `count` field moves from the effect level to the group. Amounts specified with `quantity:` on entries are now `amount:`.

---

## Worked Example: Multi-Pool Boss Drop

This loot table models a boss that always drops one guaranteed reward and one item from a large weighted pool:

```yaml
apiVersion: oscilla/v1
kind: LootTable
metadata:
  name: dragon-hoard
spec:
  displayName: "Dragon's Hoard"
  description: "Treasure from the ancient dragon's lair."
  groups:
    # Guaranteed group: always drops exactly 1 rare item
    - count: 1
      method: unique
      entries:
        - item: dragon-scale
          weight: 100
          amount: 3

    # Random bonus group: milestone-gated, drops 2 unique consolation items
    - count: 2
      method: unique
      requires:
        type: milestone
        name: cleared-dungeon-floor-3
      entries:
        - item: ruby-amulet
          weight: 40
        - item: silver-chalice
          weight: 35
        - item: enchanted-tome
          weight: 25
```

The first group always fires. The second only fires after the player reaches the third floor, and it samples `unique` so the player can't receive duplicate consolation prizes in a single run.

---

## Reference

### LootTable manifest fields

| Field              | Required | Default | Description                       |
| ------------------ | -------- | ------- | --------------------------------- |
| `metadata.name`    | yes      | —       | Identifier for `loot_ref` lookups |
| `spec.displayName` | yes      | —       | Human-readable name               |
| `spec.description` | no       | `""`    | Flavor text                       |
| `spec.groups`      | yes      | —       | One or more loot groups (min 1)   |

### LootGroup fields

| Field      | Required | Default      | Description                                                                 |
| ---------- | -------- | ------------ | --------------------------------------------------------------------------- |
| `count`    | no       | `1`          | Number of entries to draw; integer or Jinja2 template                       |
| `method`   | no       | `"weighted"` | Sampling algorithm: `"weighted"` (with replacement) or `"unique"` (without) |
| `requires` | no       | `null`       | Condition that gates the entire group                                       |
| `entries`  | yes      | —            | List of candidate items (min 1)                                             |

### LootEntry fields

| Field      | Required | Default | Description                                                  |
| ---------- | -------- | ------- | ------------------------------------------------------------ |
| `item`     | yes      | —       | `metadata.name` of an [Item](./items.md) manifest            |
| `weight`   | no       | `1`     | Relative draw probability (min 1)                            |
| `amount`   | no       | `1`     | Quantity added per draw; integer or Jinja2 template          |
| `requires` | no       | `null`  | Condition that removes this entry from the pool when not met |

---

_See [Effects](./effects.md) for the `item_drop` effect reference._
_See [Enemies](./enemies.md) for enemy loot syntax._
_See [Conditions](./conditions.md) for condition types that can be used in `requires`._
_See [Templates](./templates.md) for Jinja2 expression syntax used in `count` and `amount`._
