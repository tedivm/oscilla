# Cookbook: Locked Doors

This recipe shows how to gate a narrative option behind a key item, grant the key through a discovery, and use a milestone to prevent finding the key twice.

The pattern is general — "locked door with a physical key" is just one application. The same technique works for any case where holding an item unlocks an option.

---

## The Key Item

Define the key as a non-stackable, non-equippable item:

```yaml
apiVersion: game/v1
kind: Item
metadata:
  name: iron-key
spec:
  displayName: "Iron Key"
  description: "A heavy key stamped with a raven crest."
  category: key
  stackable: false
  value: 0
```

(No `equip` and no `use_effects` — it's a pure story item.)

---

## Placing the Key in the World

The key appears as a one-time discovery. Use a combination of milestone and `item_drop` to prevent finding it repeatedly:

```yaml
# In a location's adventure pool — only visible once
adventures:
  - ref: hidden-alcove
    weight: 20
    condition:
      type: milestone
      name: found-iron-key
      absent: true       # ← only show this adventure if the milestone is NOT set
```

The adventure itself:

```yaml
apiVersion: game/v1
kind: Adventure
metadata:
  name: hidden-alcove
spec:
  displayName: "Hidden Alcove"
  description: "Something glints behind the old tapestry."
  steps:
    - type: narrative
      text: |
        You pull the tapestry aside. A small iron key sits on a stone ledge.
        It looks old — carefully hidden.
      effects:
        - type: item_drop
          loot:
            - item: iron-key
              weight: 1
        - type: milestone_grant
          milestone: found-iron-key
```

Once `found-iron-key` is granted, this adventure no longer appears in the pool.

---

## The Locked Door

The locked door is a choice step where one option requires the key:

```yaml
- type: choice
  prompt: "A heavy iron door blocks the passage. What do you do?"
  options:
    - label: "Use the iron key"
      requires:
        type: item
        item_ref: iron-key
        quantity: 1
      steps:
        - type: narrative
          text: |
            The key fits perfectly. The lock turns with a satisfying clunk.
            Beyond the door is a vaulted chamber.
        effects:
          - type: use_item
            item_ref: iron-key    # remove the key from inventory after use
          - type: milestone_grant
            milestone: opened-raven-door

    - label: "Try to force it open"
      steps:
        - type: stat_check
          condition:
            type: character_stat
            name: strength
            gte: 18
          on_pass:
            steps:
              - type: narrative
                text: "You heave. The door bends. The lock shatters."
            effects:
              - type: milestone_grant
                milestone: opened-raven-door
          on_fail:
            steps:
              - type: narrative
                text: "You throw your shoulder into it. The door doesn't budge."

    - label: "Leave it for now"
      steps:
        - type: narrative
          text: "You make note of the door and move on."
```

The player without the key still sees the "Try to force it open" option. The key option only shows when `iron-key` is in inventory.

---

## Tracking Completion

The `milestone: opened-raven-door` can be used in follow-on logic:

```yaml
# Gate a reward adventure on having opened the door
adventures:
  - ref: treasure-vault
    weight: 100
    condition:
      type: milestone
      name: opened-raven-door
```

Or check it in a `stat_check` later in the same adventure chain.

---

## Variations

**Consumable item (like a potion or spell scroll).** Use `consumed_on_use: true` on the item and omit the `use_item` effect — the item is removed on use automatically.

**Combination lock.** Require multiple items using `all` conditions:

```yaml
requires:
  type: all
  conditions:
    - type: item
      item_ref: iron-key
      quantity: 1
    - type: item
      item_ref: raven-signet
      quantity: 1
```

**Permanent access.** Skip the `use_item` effect if the door should stay open without consuming the key (the player keeps the key as a permanent souvenir).

---

*See [Conditions](../conditions.md) · [Effects](../effects.md) · [Items](../items.md)*
