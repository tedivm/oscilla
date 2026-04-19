# Effects

Effects are how you change the game world. Every time a player wins a fight, earns a reward, spends gold, unlocks a door, or triggers a story beat, an effect is responsible. Effects are the atomic units of change — and because complex behaviors are built by composing them, you never need special-case engine features for most mechanics.

Effects appear in several places: on [adventure](./adventures.md) steps, on combat outcome branches ([`on_win`, `on_defeat`, `on_flee`](./adventures.md#combat)), and on the outcomes of [stat check](./adventures.md#stat-check) steps. Multiple effects can be listed together; they all execute in order.

```yaml
on_win:
  effects:
    - type: stat_change
      stat: xp
      amount: 100
    - type: item_drop
      groups:
        - entries:
            - item: gold-coins
              weight: 70
            - item: iron-sword
              weight: 30
    - type: milestone_grant
      milestone: "defeated-the-bandit-captain"
    - type: stat_change
      stat: reputation
      amount: 15
```

This fires four effects in sequence: XP, a loot roll, a story milestone, and a reputation increase. That's the full range of what a single outcome branch might do.

---

## Rewarding the Player

### Granting Experience

XP is stored like any other stat. Use `stat_change` on your XP stat (typically named `xp`) to reward the player:

```yaml
effects:
  - type: stat_change
    stat: xp
    amount: 150
```

Positive amounts reward the player; negative amounts apply a penalty. Level-up calculations happen through `on_stat_threshold` triggers declared in `game.yaml` — there is no special XP handler. See [Game Configuration §XP, Leveling, and HP](./game-configuration.md#xp-leveling-and-hp) for the full setup.

You can also use a [template expression](./templates.md) for dynamic XP:

```yaml
effects:
  - type: stat_change
    stat: xp
    amount: "{{ roll(50, 200) }}"
```

### Dropping Items

The `item_drop` effect rolls a weighted loot table and gives the player whatever comes up. Item names must match a loaded [Item manifest](./items.md).

```yaml
effects:
  - type: item_drop
    groups:
      - entries:
          - item: healing-potion
            weight: 60
          - item: mana-potion
            weight: 30
          - item: rare-gem
            weight: 10
```

Each group picks exactly one item by default. Use `count` on a group to roll multiple times from it:

```yaml
effects:
  - type: item_drop
    groups:
      - count: 3 # three separate rolls from this group
        entries:
          - item: gold-coins
            weight: 80
          - item: silver-ring
            weight: 20
```

`count` can also be a [template expression](./templates.md): `"{{ roll(1, 3) }}"`.

Use `amount` on any loot entry to grant more than one copy when that entry is selected:

```yaml
effects:
  - type: item_drop
    groups:
      - entries:
          - item: gold-coins
            weight: 100
            amount: 5 # player always receives 5 coins from this roll
```

To guarantee a specific item with no random element, use a single-entry group with `weight: 100`:

```yaml
effects:
  - type: item_drop
    groups:
      - entries:
          - item: ancient-key
            weight: 100
```

You can supply multiple independent groups on a single effect; each group draws independently:

```yaml
effects:
  - type: item_drop
    groups:
      - entries: # always drops one of these
          - item: gold-coins
            weight: 70
          - item: silver-ring
            weight: 30
      - entries: # always also drops one of these
          - item: healing-potion
            weight: 60
          - item: mana-potion
            weight: 40
```

Instead of inline groups, you can reference a named [LootTable manifest](./loot-tables.md) by name using `loot_ref`:

```yaml
effects:
  - type: item_drop
    loot_ref: dungeon-treasure # named LootTable manifest
```

Exactly one of `groups` or `loot_ref` must be set; providing both or neither is a load-time error.

---

## Managing Skills and Archetypes

### Skill Grant

Permanently teaches the player a skill. It appears in their skill list for all future combats.

```yaml
effects:
  - type: skill_grant
    skill: battle-cry # skill manifest name
```

See [Skills](./skills.md) for the full skill manifest format.

### Skill Revoke

Permanently removes a learned skill from the player. This is the counterpart to `skill_grant` and is most commonly used in an archetype's `lose_effects` block to take back skills that were granted when the archetype was applied.

```yaml
effects:
  - type: skill_revoke
    skill: power-attack # skill manifest name
```

This is a safe no-op if the character does not currently know the skill.

### Archetype Add

Grants the named [archetype](./archetypes.md) to the character.

```yaml
effects:
  - type: archetype_add
    name: warrior # Archetype manifest name
    force: false # Optional; defaults to false
```

When an archetype is granted:

1. The archetype's `gain_effects` are dispatched.
2. A grant record (tick + timestamp) is stored on the character.
3. The archetype's `passive_effects` begin applying immediately.

If the character already holds the archetype, this is a no-op. Set `force: true` to re-grant an already-held archetype, which re-fires `gain_effects` and resets the grant timestamp.

### Archetype Remove

Removes the named [archetype](./archetypes.md) from the character.

```yaml
effects:
  - type: archetype_remove
    name: warrior
    force: false # Optional; defaults to false
```

When an archetype is removed:

1. The archetype's `lose_effects` are dispatched.
2. The grant record is deleted from the character.
3. The archetype's `passive_effects` stop applying immediately.

If the character does not hold the archetype, this is a no-op. Set `force: true` to fire `lose_effects` even when the archetype is not currently held.

---

## Modifying Stats

### Stat Change — add or subtract

Use `stat_change` to increment or decrement any `int` [stat](./game-configuration.md#stats). This is the workhorse for gold spending, damage, reputation changes, and anything else that shifts a number.

```yaml
effects:
  - type: stat_change
    stat: gold
    amount: -25 # spend 25 gold

  - type: stat_change
    stat: reputation
    amount: 5 # gain 5 reputation
```

If the stat has `bounds` set in [`character_config.yaml`](./game-configuration.md#stats), the result is clamped automatically and the player is notified.

The `amount` field can be a [template expression](./templates.md):

```yaml
effects:
  - type: stat_change
    stat: gold
    amount: "{{ player.stats.luck * 10 }}"
```

### Stat Set — assign a specific value

Use `stat_set` when you want to assign a value directly rather than adjust it. Works on both `int` and `bool` [stats](./game-configuration.md#stats).

```yaml
effects:
  - type: stat_set
    stat: is_cursed
    value: true

  - type: stat_set
    stat: strength
    value: 20
```

`stat_change` only works with `int` stats. If you need to flip a boolean flag, `stat_set` is what you want.

---

## Tracking Story Progress

### Milestone Grant

Milestones are permanent flags — once set, they stay set. They're the standard way to track whether an event has happened, a [quest](./quests.md) stage has been reached, or a choice has been made.

```yaml
effects:
  - type: milestone_grant
    milestone: "betrayed-the-guild"
```

Once a milestone is set, the [`milestone` condition](./conditions.md#milestone) becomes true permanently, and you can use it to gate future content appropriately.

Granting a milestone also triggers automatic [quest stage advancement](./quests.md#advancing-a-quest) — any active quest whose current stage lists the granted milestone in its `advance_on` list will advance in the same tick.

---

### Quest Activate

Starts a [quest](./quests.md) by registering it as active at its entry stage. The player receives a "Quest started" notification.

```yaml
effects:
  - type: quest_activate
    quest_ref: missing-merchant # must match a Quest manifest name
```

Activating a quest that is already active or already completed is a safe no-op. If the player already holds any milestone required by the entry stage's `advance_on` list, the quest immediately advances (in the same tick). See [Quests](./quests.md) for the full quest manifest format and `completion_effects`.

---

## Using Items

### Use Item

Triggers a specific [item's](./items.md#consumables) `use_effects` as if the player pressed "Use" from their inventory.

```yaml
effects:
  - type: use_item
    item: healing-potion
```

If the item has `consumed_on_use: true`, it is removed after use. The player must already have the item in their inventory for this to do anything. See [Items](./items.md#consumables) for how to define `use_effects` on an item.

---

## Controlling Adventure Flow

### End Adventure

Terminates the adventure with a named outcome. Almost every adventure needs at least one of these.

```yaml
effects:
  - type: end_adventure
    outcome: "victory"
```

The outcome string is freeform — `"victory"`, `"defeat"`, `"fled"`, `"escaped"` — it shows in the TUI after the adventure completes.

### Goto

Jumps to a labeled step within the same adventure. Use this for loops and revisitable decision points.

```yaml
effects:
  - type: goto
    target: crossroads # must match a `label:` on a step
```

See [Adventures](./adventures.md#labels-and-goto) for the full pattern.

---

## Combat Effects

These effects are only meaningful inside combat. Outside combat they are silently skipped.

### Apply Buff

Applies a named [buff](./skills.md#defining-a-buff) to the player or enemy.

```yaml
effects:
  - type: apply_buff
    buff_ref: on-fire
    target: enemy # "player" or "enemy" (default: "player")
```

### Dispel

Removes an active [buff](./skills.md#removing-buffs) by its manifest name.

```yaml
effects:
  - type: dispel
    label: on-fire
    target: enemy
```

The optional `permanent` flag also removes a [persistent buff](./skills.md#buff-blocking) from the player's stored buff list, so it will not be re-injected into a future combat:

```yaml
effects:
  - type: dispel
    label: regen
    target: player
    permanent: true # also clears the stored buff; prevents re-injection
```

Without `permanent: true`, `dispel` only removes the buff from the current combat. A persistent buff that was dispelled mid-combat will still be re-injected (with its remaining turns) into the next combat.

---

## Composing Multiple Effects

Effects fire in order. You can chain as many as you want on a single step:

```yaml
- type: narrative
  text: "You defeat the bandit and recover the stolen goods."
  effects:
    - type: stat_change
      stat: xp
      amount: 75
    - type: item_drop
      groups:
        - entries:
            - item: stolen-purse
              weight: 100
    - type: milestone_grant
      milestone: "bandit-defeated"
    - type: stat_change
      stat: reputation
      amount: 10
```

Four things happen at once: XP, item, milestone, reputation. That's the composability principle in action — no special "bandit defeat handler" needed.

---

## Reference

### All Effect Types

| Type               | Required fields      | Optional fields                             | Notes                                                                                            |
| ------------------ | -------------------- | ------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| `stat_change`      | `stat`, `amount`     | —                                           | `int` stats only; `amount` can be template; use for XP, gold, damage, etc.                       |
| `stat_set`         | `stat`, `value`      | —                                           | Works on `int` and `bool` stats                                                                  |
| `item_drop`        | `groups` or `loot_ref` | —                                           | `groups`: inline list of loot groups; `loot_ref`: named LootTable manifest; exactly one required  |
| `use_item`         | `item`               | —                                           | Player must already hold the item                                                                |
| `milestone_grant`  | `milestone`          | —                                           | Sets a permanent story flag; triggers quest advancement                                          |
| `quest_activate`   | `quest_ref`          | —                                           | Activates a named quest; no-op if already active/complete                                        |
| `skill_grant`      | `skill`              | —                                           | Player permanently learns the skill                                                              |
| `skill_revoke`     | `skill`              | —                                           | Removes a permanently learned skill; no-op if not known                                          |
| `archetype_add`    | `name`               | `force` (default `false`)                   | Grants an archetype; fires `gain_effects`; no-op if already held unless `force: true`            |
| `archetype_remove` | `name`               | `force` (default `false`)                   | Removes an archetype; fires `lose_effects`; no-op if not held unless `force: true`               |
| `apply_buff`       | `buff_ref`           | `target`, `variables`                       | Combat only; `target`: `player` or `enemy`                                                       |
| `dispel`           | `label`              | `target`, `permanent` (default `false`)     | Combat only; removes buff by manifest name; `permanent: true` also clears stored persistent buff |
| `end_adventure`    | `outcome`            | —                                           | Terminates the adventure                                                                         |
| `goto`             | `target`             | —                                           | Jumps to a labeled step                                                                          |

### `item_drop` fields

**Group fields** (each element of `groups`):

| Field     | Type           | Default      | Description                                                                     |
| --------- | -------------- | ------------ | ------------------------------------------------------------------------------- |
| `count`   | `int` or `str` | `1`          | How many entries to draw from this group; can be a template expression          |
| `method`  | `str`          | `"weighted"` | `"weighted"` (with replacement) or `"unique"` (without replacement)            |
| `entries` | list           | required     | At least one entry required                                                     |

**Entry fields** (each element of `entries`):

| Field    | Type           | Default | Description                                              |
| -------- | -------------- | ------- | -------------------------------------------------------- |
| `item`   | `str`          | required | [Item](./items.md) manifest name                        |
| `weight` | `int`          | `1`     | Relative probability; higher = more likely               |
| `amount` | `int` or `str` | `1`     | Copies granted when this entry is selected; can template |

### `apply_buff` fields

| Field       | Type  | Default    | Description                                       |
| ----------- | ----- | ---------- | ------------------------------------------------- |
| `buff_ref`  | `str` | required   | [Buff](./skills.md#defining-a-buff) manifest name |
| `target`    | `str` | `"player"` | `"player"` or `"enemy"`                           |
| `variables` | dict  | `{}`       | Overrides buff manifest variable defaults         |

---

## Emitting Custom Triggers

The `emit_trigger` effect fires a custom trigger that has been declared in `game.yaml`. The trigger is enqueued for drain at the end of the current adventure, which means any adventures mapped to it in `trigger_adventures` run after the currently-active adventure finishes.

```yaml
effects:
  - type: emit_trigger
    trigger: player-discovered-relic # must be in game.yaml triggers.custom
```

### When to use `emit_trigger`

Use it when one author-defined event should automatically start a separate adventure without the player explicitly choosing it. For example: a player finds an artifact (pool adventure) and that automatically triggers a follow-up lore scene (triggered adventure), decoupling the two files from each other.

### Requirements

The trigger name in `trigger` must be declared in `game.yaml` under `triggers.custom`. An undeclared name produces a **load warning** when the package is validated. Example declaration:

```yaml
# game.yaml
spec:
  triggers:
    custom:
      - player-discovered-relic
  trigger_adventures:
    player-discovered-relic:
      - relic-lore-scene
```

### `emit_trigger` fields

| Field     | Type             | Required | Description                                                 |
| --------- | ---------------- | -------- | ----------------------------------------------------------- |
| `type`    | `"emit_trigger"` | yes      | Identifies this effect type                                 |
| `trigger` | `str`            | yes      | Custom trigger name declared in `game.yaml triggers.custom` |

---

_Next: [Templates](./templates.md) — dynamic text and calculations in narrative._
_See [Game Configuration](./game-configuration.md#triggered-adventures) for the full trigger system._
