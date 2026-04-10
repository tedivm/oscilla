# Archetypes

An **archetype** is a named, persistent state attached to a character — something like "Warrior", "Scholar", "Vampire", or "Guild Member". Archetypes are granted and revoked by effects during adventures. While held, an archetype can apply passive stat bonuses and unlock skills, making them a flexible tool for building progression paths, role identity, or faction membership.

---

## What Archetypes Are For

Archetypes fill the role that a traditional character-class system might fill in another engine, but without hard-wiring any class structure into the game. You define exactly what archetypes exist, what they mean in your world, and how they interact with adventures.

Common uses:

- **Permanent role identity** — a Warrior archetype that grants combat stat bonuses for the whole game
- **Earned progression** — a Veteran archetype unlocked after completing a major quest chain
- **Faction alignment** — Guild Member, Exile, or Outcast states that open or close adventures
- **Temporary states** — Cursed or Blessed states that can be removed by specific encounters

---

## Archetype Manifest

An archetype is described by an `Archetype` manifest placed in your content package:

```yaml
apiVersion: oscilla/v1
kind: Archetype
metadata:
  name: warrior # kebab-case identifier used in effects and conditions
spec:
  displayName: "Warrior"
  description: "A trained combatant. Grants a bonus to strength."

  # Fires once when this archetype is first granted
  gain_effects:
    - type: stat_change
      stat: strength
      amount: 5

  # Fires once when this archetype is removed
  lose_effects:
    - type: stat_change
      stat: strength
      amount: -5

  # Applied continuously while the archetype is held
  passive_effects:
    - stat_modifiers:
        - stat: strength
          amount: 2
      skill_grants:
        - power-attack
```

### Field Reference

| Field             | Type                  | Required | Default | Description                                                 |
| ----------------- | --------------------- | -------- | ------- | ----------------------------------------------------------- |
| `displayName`     | `str`                 | yes      | —       | Human-readable name shown in the TUI                        |
| `description`     | `str`                 | no       | `""`    | Optional summary text for author reference                  |
| `gain_effects`    | `List[Effect]`        | no       | `[]`    | Effects dispatched once when the archetype is first granted |
| `lose_effects`    | `List[Effect]`        | no       | `[]`    | Effects dispatched once when the archetype is removed       |
| `passive_effects` | `List[PassiveEffect]` | no       | `[]`    | Always-on bonuses applied while this archetype is held      |

---

## Granting and Revoking Archetypes

Use the `archetype_add` and `archetype_remove` effects inside any adventure step to grant or remove archetypes. Use `skill_revoke` in `lose_effects` to take back skills that were granted when the archetype was applied.

See [Effects — Managing Skills and Archetypes](./effects.md#managing-skills-and-archetypes) for the full reference, including `force` behavior and lifecycle details.

Quick examples:

```yaml
# Grant an archetype
effects:
  - type: archetype_add
    name: warrior

# Remove an archetype
effects:
  - type: archetype_remove
    name: warrior

# Revoke a skill learned via the archetype
effects:
  - type: skill_revoke
    skill: power-attack
```

---

## Passive Effects

`passive_effects` on an archetype work identically to the `passive_effects` in `game.yaml`, but apply only while the archetype is held. See [Passive Effects](./passive-effects.md) for full syntax.

A passive effect with no `condition` applies unconditionally while the archetype is held:

```yaml
passive_effects:
  - stat_modifiers:
      - stat: strength
        amount: 3
    skill_grants:
      - power-attack
```

A passive effect with a `condition` applies only when the condition is satisfied:

```yaml
passive_effects:
  - condition:
      type: character_stat
      stat: level
      gte: 10
    stat_modifiers:
      - stat: strength
        amount: 5
```

---

## Conditions

Five condition types check archetype state. They work anywhere conditions are accepted — adventure `requires`, location `unlock`, choice option `requires`, stat-check `condition`, passive effect `condition`, etc.

| Type                      | What it checks                                                                      |
| ------------------------- | ----------------------------------------------------------------------------------- |
| `has_archetype`           | Character holds the named archetype                                                 |
| `has_all_archetypes`      | Character holds every archetype in the list                                         |
| `has_any_archetypes`      | Character holds at least one archetype in the list                                  |
| `archetype_count`         | Number of held archetypes satisfies a numeric comparison (`gte`/`lte`/`eq`)         |
| `archetype_ticks_elapsed` | Ticks since the named archetype was granted satisfy a comparison; false if not held |

See [Conditions — Archetype Conditions](./conditions.md#archetype-conditions) for the full syntax and field reference.

---

## Worked Example

An adventure that grants the Warrior archetype on completion, gates a follow-up adventure on holding it, and removes it if the player fails a later encounter:

**`archetypes/warrior.yaml`:**

```yaml
apiVersion: oscilla/v1
kind: Archetype
metadata:
  name: warrior
spec:
  displayName: "Warrior"
  gain_effects:
    - type: stat_change
      stat: strength
      amount: 5
    - type: skill_grant
      skill: power-attack
  lose_effects:
    - type: stat_change
      stat: strength
      amount: -5
    - type: skill_revoke
      skill: power-attack
  passive_effects:
    - stat_modifiers:
        - stat: strength
          amount: 2
```

**`adventures/warrior-initiation.yaml`:**

```yaml
apiVersion: oscilla/v1
kind: Adventure
metadata:
  name: warrior-initiation
spec:
  displayName: "The Warrior's Trial"
  requires:
    type: not
    condition:
      type: has_archetype
      name: warrior
  steps:
    - type: narrative
      text: "You complete the trial."
      effects:
        - type: archetype_add
          name: warrior
        - type: end_adventure
          outcome: completed
```

**`adventures/warrior-duel.yaml`** (only available to warriors who've held the archetype for at least 5 ticks):

```yaml
apiVersion: oscilla/v1
kind: Adventure
metadata:
  name: warrior-duel
spec:
  displayName: "A Warrior's Duel"
  requires:
    type: archetype_ticks_elapsed
    name: warrior
    gte: 5
  steps:
    - type: stat_check
      condition:
        type: character_stat
        stat: strength
        gte: 15
      on_pass:
        steps:
          - type: narrative
            text: "You win the duel with ease."
            effects:
              - type: end_adventure
                outcome: completed
      on_fail:
        steps:
          - type: narrative
            text: "Defeated, you lose your warrior standing."
            effects:
              - type: archetype_remove
                name: warrior
              - type: end_adventure
                outcome: defeated
```

---

## Load-Time Validation

The loader validates all archetype references at package load time. Using an archetype name in any effect (`archetype_add`, `archetype_remove`) or condition (`has_archetype`, `has_all_archetypes`, `has_any_archetypes`, `archetype_ticks_elapsed`) that is not declared as an `Archetype` manifest produces a **hard error** and prevents the game from starting.

---

## See Also

- [Conditions](./conditions.md) — full syntax for all condition types
- [Effects](./effects.md) — full syntax for all effect types
- [Passive Effects](./passive-effects.md) — stat modifier and skill grant syntax
- [Skills](./skills.md) — `skill_grant` and skill definitions
