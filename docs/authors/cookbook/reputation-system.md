# Cookbook: Reputation System

This recipe shows how to build a reputation system using a single `int` stat, conditions, and templates — no special engine support required.

The basic idea: adventures grant or deduct `reputation` points, and other adventures gate their best outcomes (or availability) behind reputation thresholds.

---

## Setup

In `character_config.yaml`, declare the reputation stat:

```yaml
spec:
  hidden_stats:
    - name: reputation
      type: int
      default: 0
      bounds:
        min: -100
        max: 100
      description: "Standing with the kingdom's citizens."
```

Using `hidden_stats` keeps it out of the character status panel. If you want the player to see their standing, move it to `public_stats`.

---

## Granting and Deducting Reputation

Use `stat_change` effects in adventure outcomes:

```yaml
# Helping the innkeeper
- type: narrative
  text: "The innkeeper beams. 'You're welcome here any time!'"
  effects:
    - type: stat_change
      stat: reputation
      amount: 10

# Extorting a merchant
- type: choice
  prompt: "The merchant looks frightened."
  options:
    - label: "Demand payment for 'protection'"
      steps:
        - type: narrative
          text: "Word spreads. People look away when you pass."
        effects:
          - type: stat_change
            stat: reputation
            amount: -15
          - type: stat_change
            stat: gold
            amount: 20
```

---

## Gating Adventures on Reputation

Lock an adventure to high-reputation players:

```yaml
# In a location's adventure pool
adventures:
  - ref: guild-invitation
    weight: 30
    condition:
      type: character_stat
      name: reputation
      gte: 50 # only appear once the player is well regarded
```

Or require it at the adventure level:

```yaml
spec:
  displayName: "The King's Audience"
  requires:
    type: character_stat
    name: reputation
    gte: 75
  steps: …
```

---

## Showing Reputation in Narrative Text

Use a template to reference the reputation stat directly in prose:

```yaml
- type: narrative
  text: |
    The guard eyes you carefully. Your reputation precedes you —
    {% if player.stats.reputation >= 50 %}
    she waves you through without a word.
    {% elif player.stats.reputation >= 0 %}
    she asks a few questions before stepping aside.
    {% else %}
    she calls for a second guard and demands to know your business.
    {% endif %}
```

---

## Branching on Reputation in Adventures

Use a `stat_check` step for purely mechanical branching:

```yaml
- type: stat_check
  condition:
    type: character_stat
    name: reputation
    gte: 40
  on_pass:
    steps:
      - type: narrative
        text: "The merchant recognizes you and offers a discount."
    effects:
      - type: stat_change
        stat: gold
        amount: 10
  on_fail:
    steps:
      - type: narrative
        text: "The merchant eyes your worn gear suspiciously."
```

---

## Extending the System

**Multiple factions.** Use separate stats: `kingdom_reputation`, `guild_reputation`, `thieves_reputation`. Adventures that please one faction can deduct from another.

**Titles.** Use `milestone_grant` at reputation thresholds: grant `milestone: respected-citizen` when reputation crosses 50, then use that milestone in passive effects and conditions elsewhere.

**Reputation decay.** Add a `passive_effects` entry in `game.yaml` that provides a small stat modifier based on level — or handle decay through adventure effects that fire frequently.

---

_See [Conditions](../conditions.md) · [Effects](../effects.md) · [Templates](../templates.md)_
