# Items

Items are the physical objects of your world — weapons, armor, potions, keys, tokens, and anything else players can carry, use, equip, or trade. An item manifest describes what an item is and how it behaves. The engine handles inventory tracking, stacking, weight, and equipping automatically from this specification.

---

## Basic Structure

```yaml
apiVersion: oscilla/v1
kind: Item
metadata:
  name: healing-potion
spec:
  displayName: "Healing Potion"
  description: "A bubbling red liquid. Tastes like cherries and regret."
  category: consumable
  stackable: true
  value: 50
```

Items can live under any `items/` directory in your package — inside a region folder, a location folder, or a top-level `items/` directory. The engine finds them all.

`metadata.name` is what you use everywhere else: in [`item_drop` effects](./effects.md#dropping-items), [`item_ref` conditions](./conditions.md#item-in-inventory), [`use_item` effects](./effects.md#use-item), [recipe](./recipes.md) ingredients, and so on.

---

## Consumables

A consumable is an item the player activates from inventory. When used, its `use_effects` fire. Set `consumed_on_use: true` to remove the item after use.

```yaml
spec:
  displayName: "Healing Potion"
  description: "Restores 30 HP."
  category: consumable
  stackable: true
  consumed_on_use: true
  use_effects:
    - type: heal
      amount: 30
  value: 50
```

Any [effect](./effects.md) is valid in `use_effects`. You can heal, change stats, grant milestones, grant skills, or apply buffs — all from a single use.

```yaml
# A berserker draught that boosts strength but costs HP
use_effects:
  - type: stat_change
    stat: strength
    amount: 5
  - type: stat_change
    stat: hp
    amount: -10
  - type: apply_buff
    buff_ref: berserk-state
```

### Charged Items

A charged item is consumed one charge at a time. Use `charges` instead of `stackable: true` + `consumed_on_use: true` for items that are single instances with multiple uses.

```yaml
spec:
  displayName: "Wand of Frost"
  description: "Three icy bolts remain."
  category: magic
  stackable: false
  charges: 3 # item instance starts with 3 uses
  use_effects:
    - type: apply_buff
      buff_ref: frost-bolt
  value: 180
```

When charges reach 0, the item is removed from inventory automatically. `charges` is mutually exclusive with `stackable: true` and `consumed_on_use: true`.

---

## Equippable Gear

Gear is equipped into named slots (defined in `character_config.yaml`). While equipped, its `stat_modifiers` apply to the player's effective stats.

```yaml
spec:
  displayName: "Iron Sword"
  description: "Heavier than it looks."
  category: weapon
  stackable: false
  equip:
    slots:
      - main_hand
    stat_modifiers:
      - stat: strength
        amount: 2
  value: 120
```

The `slots` list names which equipment slots this item occupies. If you define two-handed weapons, list two slots.

`stat_modifiers` is a list of `{stat, amount}` pairs. Amounts may be negative (debuffs). All `stat` names must exist in `character_config.yaml`; all `slot` names must exist in `CharacterConfig.equipment_slots`. The loader validates both and raises an error if they don't match.

### Equip Requirements

An item can refuse to be equipped until the player meets a condition:

```yaml
equip:
  slots:
    - main_hand
  requires:
    type: character_stat
    name: strength
    gte: 15 # cannot equip until strength reaches 15
  stat_modifiers:
    - stat: strength
      amount: 5
```

The `requires` field accepts any [condition](./conditions.md). See [Conditions §stat_source](./conditions.md#character-stat) for how `stat_source` controls whether other gear bonuses count toward the requirement.

### Skills Granted by Equipment

Gear can grant skills while equipped or while held in inventory:

```yaml
equip:
  slots:
    - main_hand
  stat_modifiers: []
grants_skills_equipped:
  - battle-cry # skill is available only while this item is equipped
grants_skills_held:
  - appraise-item # skill is available whenever the item is in the inventory
```

`grants_skills_equipped` grants are ephemeral — they disappear the moment the item is unequipped. `grants_skills_held` grants are active whenever the player has even one copy in inventory, regardless of whether it's equipped.

Granted skills are not added to the player's permanent skill list.

### Buffs Granted by Equipment

Gear can automatically apply [combat buffs](./skills.md#defining-a-buff) at the start of every fight:

```yaml
grants_buffs_equipped:
  - buff_ref: thorns
    variables:
      reflect_percent: 20 # override a buff variable for this item

grants_buffs_held:
  - buff_ref: aura-of-dread
```

`grants_buffs_equipped` applies only when the item is in a slot. `grants_buffs_held` applies whenever the item is in inventory. The buff applies fresh at the start of each [combat encounter](./adventures.md#combat).

---

## Labels

Labels are classification tags from your [`game.yaml` `item_labels` list](./game-configuration.md#item-labels). They affect inventory display (color, sort order) and can be queried by conditions.

```yaml
spec:
  displayName: "Flaming Greatsword"
  category: weapon
  labels:
    - rare
    - magic
  stackable: false
  equip:
    slots: [main_hand, off_hand]
    stat_modifiers:
      - stat: strength
        amount: 8
  value: 2500
```

Players see the label color in inventory. Conditions can check for items with a specific label using `item_held_label` (see [Conditions](./conditions.md)).

---

## Item Placement

Items can be placed anywhere in your content package — the engine scans all `.yaml` files recursively and loads every Item manifest it finds. A common convention is to use `items/` directories at the relevant scope:

```
regions/dungeon/items/skeleton-key.yaml          ← near dungeon content, by convention
regions/dungeon/locations/vault/items/key.yaml   ← near vault content, by convention
items/gold-coins.yaml                            ← game-wide items, by convention
```

Items do not automatically appear in the game just because they exist in a manifest. They enter the player's inventory through `item_drop` effects in adventures.

---

## Loot Tables

A `LootTable` manifest defines a named, reusable collection of weighted item entries. Instead of repeating loot lists in every adventure, you define the table once and reference it by name using `loot_ref`.

```yaml
apiVersion: oscilla/v1
kind: LootTable
metadata:
  name: dungeon-treasure
spec:
  displayName: "Dungeon Treasure"
  description: "Standard dungeon loot mix."
  loot:
    - item: gold-coins
      weight: 70
      quantity: 5
    - item: healing-potion
      weight: 20
      quantity: 1
    - item: rare-gem
      weight: 10
      quantity: 1
```

Then reference it from any `item_drop` effect:

```yaml
effects:
  - type: item_drop
    count: 2
    loot_ref: dungeon-treasure
```

`loot_ref` also accepts an **enemy manifest name** — the engine will use the loot list defined on that enemy. This means you can define one canonical loot list on the enemy and share it across both the combat outcome and any post-combat treasure narrative:

```yaml
effects:
  - type: item_drop
    count: 1
    loot_ref: goblin-warrior # uses EnemyManifest.spec.loot
```

**Resolution order:** when the engine sees a `loot_ref`, it first checks named `LootTable` manifests, then `Enemy` manifests. Choose names that do not collide between the two kinds if you want predictable resolution.

**Mutual exclusion:** `loot` (inline list) and `loot_ref` (named reference) cannot both be set on the same effect. Exactly one must be present. The engine raises a load error if neither or both are provided.

### `quantity` on loot entries

Each entry in a loot list (whether inline or in a `LootTable`) supports a `quantity` field:

```yaml
loot:
  - item: gold-coins
    weight: 100
    quantity: 10 # player receives 10 gold-coins per roll
```

`quantity` defaults to `1` when omitted. When a roll selects an entry, the player receives `quantity` copies. Combined with `count`, you can build generous reward tables — a `count: 3` drop with `quantity: 5` on the winning entry grants 15 items.

---

## Reference

### Item manifest fields

| Field                         | Required | Default | Description                                            |
| ----------------------------- | -------- | ------- | ------------------------------------------------------ |
| `metadata.name`               | yes      | —       | Identifier used everywhere items are referenced        |
| `spec.displayName`            | yes      | —       | Player-facing name                                     |
| `spec.description`            | no       | `""`    | Short description shown in inventory                   |
| `spec.category`               | no       | `""`    | Display-only category label (free string)              |
| `spec.stackable`              | no       | `false` | If `true`, multiple copies stack as a count            |
| `spec.value`                  | no       | `0`     | Numeric value (for display or shop mechanics)          |
| `spec.labels`                 | no       | `[]`    | List of item label names from `game.yaml`              |
| `spec.use_effects`            | no       | `[]`    | Effects that fire when the player activates the item   |
| `spec.consumed_on_use`        | no       | `false` | Remove after use (stack decrements; instance removed)  |
| `spec.charges`                | no       | `null`  | Per-instance use count; item removed when it reaches 0 |
| `spec.equip`                  | no       | `null`  | If present, item can be equipped into slots            |
| `spec.grants_skills_equipped` | no       | `[]`    | Skills available only while item is in a slot          |
| `spec.grants_skills_held`     | no       | `[]`    | Skills available whenever item is in inventory         |
| `spec.grants_buffs_equipped`  | no       | `[]`    | Buffs applied at combat start while equipped           |
| `spec.grants_buffs_held`      | no       | `[]`    | Buffs applied at combat start while held               |

### EquipSpec fields

| Field            | Required | Default | Description                                                       |
| ---------------- | -------- | ------- | ----------------------------------------------------------------- |
| `slots`          | yes      | —       | List of slot names (min 1) from `CharacterConfig.equipment_slots` |
| `stat_modifiers` | no       | `[]`    | List of `{stat, amount}` pairs active while equipped              |
| `requires`       | no       | `null`  | Condition evaluated against base stats before allowing equip      |

### Constraints

- `charges` is mutually exclusive with `stackable: true` and `consumed_on_use: true`
- All `equip.slots` values must match defined `equipment_slots` in `character_config.yaml`
- All `equip.stat_modifiers[].stat` values must match stats in `character_config.yaml`
- All skills in `grants_skills_equipped` and `grants_skills_held` must match loaded Skill manifests
- All buff refs must match loaded Buff manifests

---

_See [Effects](./effects.md) for what you can put in `use_effects`._
_See [Skills](./skills.md) for skill and buff manifest syntax._
_See [Game Configuration](./game-configuration.md) for `item_labels` and equipment slot definitions._
_See [Conditions](./conditions.md) for `item_held_label` and `item_equipped` conditions._
