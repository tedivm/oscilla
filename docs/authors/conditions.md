# Conditions

Conditions are the engine's universal gate. They let you express "this content is available when…" in one consistent syntax, and that syntax works everywhere: [adventure](./adventures.md) `requires`, [location](./world-building.md) `unlock`, choice option `requires`, [item equip requirements](./items.md#equip-requirements), [passive effects](./passive-effects.md), [skill](./skills.md) activation guards — the same vocabulary, the same rules, everywhere.

This means you learn conditions once, and everything clicks into place.

---

## Your First Conditions

Here's a simple adventure that requires the player to be at least level 3:

```yaml
apiVersion: game/v1
kind: Adventure
metadata:
  name: haunted-cellar
spec:
  displayName: "The Haunted Cellar"
  description: "Strange sounds come from below."
  requires:
    type: level
    value: 3
  steps:
    - type: narrative
      text: "You descend into the darkness..."
```

That `requires` block is a condition. It evaluates true when the player's level is 3 or higher, and false otherwise. When false, the adventure won't appear in the location's adventure pool.

The same condition could appear on a location `unlock`, a choice option's `requires`, or an item's `equip.requires`. The syntax is identical.

You can also combine conditions from the start. Use `and` to require multiple things at once:

```yaml
requires:
  type: and
  conditions:
    - type: level
      value: 3
    - type: milestone
      name: "found-the-map"
```

This is true only when the player is level 3 **and** has the `found-the-map` milestone. Each entry in `conditions` is a full condition in its own right — `and` can even nest other `and` or `or` blocks.

---

## Checking What's True Right Now

### Level

The most common gate. True when the player's level meets or exceeds the value.

```yaml
requires:
  type: level
  value: 5
```

### Milestone

True when the player has earned a specific milestone. Milestones are permanent flags set by [`milestone_grant` effects](./effects.md#milestone-grant).

```yaml
requires:
  type: milestone
  name: "rescued-the-princess"
```

Use milestones to track story progress, gate story-sensitive content, and prevent adventures from triggering twice.

### Item in Inventory

True when the player holds a certain item — counting both stackable piles and individual instances.

```yaml
requires:
  type: item
  item_ref: ancient-key
  quantity: 1    # default is 1 if omitted
```

### Character Stat

True when a stat meets a numeric comparison. Works with any `int` [stat](./game-configuration.md#stats) defined in `character_config.yaml`.

```yaml
requires:
  type: character_stat
  stat: strength
  gte: 15
```

Available operators: `gte` (≥), `lte` (≤), `eq` (=), `gt` (>), `lt` (<).

By default this compares the **effective** stat — base value plus any bonuses from equipped items. To check the raw stat and ignore equipment bonuses, use `stat_source: base`:

```yaml
requires:
  type: character_stat
  stat: strength
  gte: 15
  stat_source: base
```

Use `stat_source: base` on item equip requirements when you want to enforce a true intrinsic-stat floor — so the requirement can only be met by the player's raw stat, not by bonuses from other gear they happen to be wearing or effects that are active.

> **Note:** An item's own stat bonus is always excluded from its own equip check by the engine, regardless of `stat_source`. Self-justification is not possible.

### Item Equipped

True when the player currently has a specific item occupying an equipment slot.

```yaml
requires:
  type: item_equipped
  item: enchanted-ring
```

### Item Held with a Label

True when any item in the player's inventory (equipped or not) carries a specific label. Labels are declared in [`game.yaml`](./game-configuration.md#item-labels).

```yaml
requires:
  type: item_held_label
  label: rare
```

> **Note:** This condition cannot be used in `passive_effects` — see [Passive Effects](./passive-effects.md) for why.

### Any Equipped Item Has a Label

True when any currently-equipped item carries a label.

```yaml
requires:
  type: any_item_equipped
  label: magic
```

> **Note:** This condition cannot be used in `passive_effects` either.

### Skill Known or Available

True when the player has learned a [skill](./skills.md), or has it available (including through item grants).

```yaml
# Must have permanently learned this skill
requires:
  type: skill
  skill_ref: arcane-shield
  mode: learned

# Skill is accessible right now (includes item grants)
requires:
  type: skill
  skill_ref: arcane-shield
  mode: available
```

### Enemies Defeated

True when the player has defeated a cumulative count of a specific enemy.

```yaml
requires:
  type: enemies_defeated
  name: goblin-scout
  gte: 10
```

### Locations Visited

True when the player has visited a location a certain number of times.

```yaml
requires:
  type: locations_visited
  name: ancient-ruins
  gte: 1
```

### Adventures Completed

True when the player has completed a specific adventure a certain number of times.

```yaml
requires:
  type: adventures_completed
  name: tutorial-quest
  gte: 1
```

### Prestige Count

True when the player has prestiged a certain number of times.

```yaml
requires:
  type: prestige_count
  gte: 1
```

---

## Combining Conditions

A single condition is useful, but the real power comes from composing them.

### All (AND) — every condition must pass

```yaml
requires:
  type: all
  conditions:
    - type: level
      value: 10
    - type: milestone
      name: "found-ancient-map"
    - type: item
      item_ref: explorer-lantern
      quantity: 1
```

This adventure is only available to level 10+ players who have found the map *and* are carrying a lantern. All three must be true.

### Any (OR) — at least one must pass

```yaml
requires:
  type: any
  conditions:
    - type: character_stat
      stat: strength
      gte: 20
    - type: item
      item_ref: battering-ram
      quantity: 1
```

The door can be broken down by a strong character *or* by anyone with a battering ram.

### Not — inverts the result

```yaml
unlock:
  type: not
  condition:
    type: milestone
    name: "village-destroyed"
```

The location is open only if the village has *not* been destroyed. `not` takes a single `condition`, not a list.

### Nesting

Operators nest freely. Here's an adventure available to characters who haven't completed the intro quest yet, but only if they have enough XP to skip it:

```yaml
requires:
  type: all
  conditions:
    - type: not
      condition:
        type: milestone
        name: "intro-completed"
    - type: level
      value: 5
```

---

## Where Conditions Appear

| Location | Field | Purpose |
|---|---|---|
| Adventure | `requires` | Gates whether the adventure appears at all |
| Location | `unlock` | Gates whether the location is accessible |
| Region | `unlock` | Gates whether the region is accessible |
| Choice option | `requires` | Hides the option unless condition passes |
| Stat check step | `condition` | Determines which branch runs |
| Item equip | `equip.requires` | Prevents equipping unless condition passes |
| Skill activation | `requires` | Blocks skill use if condition fails |
| Passive effects | `condition` | Applies bonus only while condition holds |

---

## Reference

### All Condition Types

| Type | Required fields | Optional fields | Notes |
|---|---|---|---|
| `level` | `value` | — | True when player level ≥ value |
| `milestone` | `name` | — | True when player holds the milestone |
| `item` | `item_ref` | `quantity` (default 1) | Checks inventory count ≥ quantity |
| `character_stat` | `stat`, one operator | `stat_source` | Operators: `gte`, `lte`, `eq`, `gt`, `lt` |
| `item_equipped` | `item` | — | Checks a specific item is equipped |
| `item_held_label` | `label` | — | Any inventory item has this label |
| `any_item_equipped` | `label` | — | Any equipped item has this label |
| `skill` | `skill_ref` | `mode` (default `learned`) | `mode`: `learned` or `available` |
| `enemies_defeated` | `name`, one operator | — | Operators: `gte`, `lte`, `eq`, `gt`, `lt` |
| `locations_visited` | `name`, one operator | — | Operators: `gte`, `lte`, `eq`, `gt`, `lt` |
| `adventures_completed` | `name`, one operator | — | Operators: `gte`, `lte`, `eq`, `gt`, `lt` |
| `prestige_count` | one operator | — | Operators: `gte`, `lte`, `eq`, `gt`, `lt` |
| `all` | `conditions` | — | All child conditions must pass (AND) |
| `any` | `conditions` | — | Any child condition must pass (OR) |
| `not` | `condition` | — | Inverts the single child condition |

### `stat_source` Values

| Value | Meaning |
|---|---|
| `effective` (default) | Base stat + all equipment bonuses |
| `base` | Raw stat only, ignoring equipped-item modifiers |

### Skill Condition `mode` Values

| Value | Meaning |
|---|---|
| `learned` (default) | Skill is in the player's permanent `known_skills` |
| `available` | Skill is usable right now (includes item-granted skills) |

---

*Next: [Effects](./effects.md) — how to change game state.*
