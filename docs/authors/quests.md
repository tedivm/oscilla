# Quests

A quest is a multi-stage storyline that the engine tracks on the player. Quests give your narrative arcs structure: the player starts in an initial stage, earns milestones, and advances through stages until reaching a terminal completion stage.

Quests create a sense of longer-term purpose — the difference between scattered encounters and a journey with a destination. They also help the player keep track of what options they have to make progress, which is especially important in larger open world games.

---

## Basic Structure

```yaml
apiVersion: game/v1
kind: Quest
metadata:
  name: missing-merchant
spec:
  displayName: "The Missing Merchant"
  description: "Old Gregor hasn't returned from the wilderness. Something happened."
  entry_stage: search-begun
  stages:
    - name: search-begun
      description: "Head into the wilderness and look for clues."
      advance_on:
        - found-gregor-camp
      next_stage: camp-found

    - name: camp-found
      description: "Gregor's camp was ransacked. Find who did it."
      advance_on:
        - defeated-bandit-leader
      next_stage: complete

    - name: complete
      description: "Justice served. Report back to the village."
      terminal: true
```

`entry_stage` sets which stage the player starts in when this quest becomes active. `stages` defines every stage, each one naming its milestone triggers and where it leads.

---

## The Stage Graph

Each stage is a node in a directed graph. The engine validates the graph at load time and rejects quests with:

- Duplicate stage names
- `entry_stage` pointing to a stage that doesn't exist
- Non-terminal stages without a `next_stage`
- Terminal stages that have a `next_stage` or `advance_on`
- `next_stage` pointing to a stage that doesn't exist

This means if your quest parses successfully, its stage flow is guaranteed to be consistent.

### Non-terminal stages

A non-terminal stage advances when any milestone in its `advance_on` list is granted to the player. The first match moves the quest to `next_stage`.

```yaml
- name: search-begun
  description: "Find clues in the wilderness."
  advance_on:
    - found-tracks        # either of these milestones will advance the stage
    - found-campfire
  next_stage: clues-found
```

`advance_on` is a list, and any listed milestone triggers the advancement. Once the stage advances, additional milestones in the list for that stage have no further effect.

### Terminal stages

A terminal stage marks quest completion. It has neither `advance_on` nor `next_stage`.

```yaml
- name: complete
  description: "The quest is over."
  terminal: true
```

---

## Starting a Quest

Que can be activated from adventure effects using the `quest_activate` effect. When the player encounters this effect, the engine registers the quest as active at its entry stage, notifies the player, and immediately evaluates whether any advancement is already possible.

```yaml
# In an adventure step:
- type: narrative
  text: "The innkeeper grabs your sleeve and whispers urgently."
  effects:
    - type: quest_activate
      quest_ref: missing-merchant
```

If the player already holds any milestone listed in the entry stage's `advance_on` list at activation time, the quest advances immediately (in the same tick) without any extra effect.

Activating a quest that is already active or already completed is a safe no-op — the engine logs a warning and silently skips the activation.

## Advancing a Quest

A non-terminal stage advances automatically when any milestone in its `advance_on` list is granted to the player. The engine evaluates quest state after every `milestone_grant` effect — there is no need for an explicit advance call in your adventure.

```yaml
# In an adventure step:
- type: passive_effects
  effects:
    - type: milestone_grant
      milestone: found-gregor-camp
# The engine immediately checks all active quests.
# Any quest with 'found-gregor-camp' in its current stage's advance_on list advances.
```

---

## Completion Effects

A terminal stage can declare `completion_effects` — a list of effects that fire when the quest completes. These run once, at the moment the quest reaches the terminal stage.

```yaml
- name: complete
  description: "Justice served."
  terminal: true
  completion_effects:
    - type: xp_grant
      amount: 200
    - type: item_drop
      count: 1
      loot:
        - item: reward-sword
          weight: 100
    - type: milestone_grant
      milestone: missing-merchant-resolved
```

Any [effect](./effects.md) is valid in `completion_effects`. The engine runs them in order, using the same effect pipeline as adventure steps.

**Only terminal stages may have `completion_effects`.** Declaring them on a non-terminal stage is a load-time validation error.

---


Quests work through milestones, and milestones are granted by adventure effects. This means:

1. Write the adventures that make up your questline
2. Each adventure's key moments grant milestones
3. Map those milestones to quest stage advancement in the quest manifest
gate later [adventures](./adventures.md) behind [conditions](./conditions.md) that check the current quest stage or milestone

A quest stage condition uses the standard [milestone condition](./conditions.md#milestone):

```yaml
# Gate an adventure to only appear while the quest is in a specific stage
requires:
  type: milestone
  name: started-missing-merchant
```

For more precise stage gating, use a [location's adventure pool `condition` field](./world-building.md#conditional-pool-entries) to ensure a quest-specific adventure only appears after the relevant milestones are in place.

---

## A Complete Example

```yaml
apiVersion: game/v1
kind: Quest
metadata:
  name: lich-of-the-deep
spec:
  displayName: "Lich of the Deep"
  description: |
    Ancient evil stirs in the dungeon depths. An undead sorcerer claims the old
    dungeon as its domain. Only a true hero can end its unlife.
  entry_stage: discover
  stages:
    - name: discover
      description: "Find and breach the dungeon entrance."
      advance_on:
        - found-dungeon-entrance
        - entered-dungeon
      next_stage: confront

    - name: confront
      description: "Reach the lich's sanctum and destroy it."
      advance_on:
        - destroyed-lich-phylactery
      next_stage: complete

    - name: complete
      description: "The lich is destroyed. The dungeon is free."
      terminal: true
      completion_effects:
        - type: xp_grant
          amount: 500
        - type: milestone_grant
          milestone: lich-destroyed
```

Two milestones can trigger the `discover` → `confront` transition. Whichever the player earns first moves the quest forward. The terminal stage fires an XP reward and a milestone when the quest completes.

---

## Reference

### Quest manifest fields

| Field | Required | Description |
|---|---|---|
| `metadata.name` | yes | Unique identifier |
| `spec.displayName` | yes | Player-facing quest title |
| `spec.description` | no | Summary shown in the quest log |
| `spec.entry_stage` | yes | Stage name the player starts in when the quest activates |
| `spec.stages` | yes | List of stage definitions (at least one, must include a terminal stage) |

### QuestStage fields

| Field | Required | Default | Description |
|---|---|---|---|
| `name` | yes | — | Unique stage identifier within this quest |
| `description` | no | `""` | Player-facing stage objective |
| `advance_on` | required (non-terminal) | `[]` | Milestone names that trigger advancement |
| `next_stage` | required (non-terminal) | — | Stage name to advance to |
| `terminal` | no | `false` | If `true`, this stage is the quest completion state |
| `completion_effects` | no | `[]` | Effects that fire when this stage is reached (terminal only) |

### Validation rules

- Stage names must be unique within the quest
- `entry_stage` must reference a defined stage
- Non-terminal stages must have `next_stage`
- Terminal stages must not have `advance_on` or `next_stage`
- All `next_stage` values must reference defined stages
- `completion_effects` may only be declared on terminal stages

---

*See [Effects](./effects.md) for `milestone_grant` and `quest_activate` syntax.*
*See [Conditions](./conditions.md) for the `milestone` condition type used to gate adventures.*
