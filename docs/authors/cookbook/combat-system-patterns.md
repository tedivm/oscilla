# Combat System Patterns

These patterns show common combat designs using the `CombatSystem` manifest. Each is a complete working example you can copy and adapt.

## Table of Contents

- [Pattern 1: Classic HP Combat (Auto Mode)](#pattern-1-classic-hp-combat-auto-mode)
- [Pattern 2: Choice-Mode Skill Menu](#pattern-2-choice-mode-skill-menu)
- [Pattern 3: Initiative-Based Turn Order](#pattern-3-initiative-based-turn-order)
- [Pattern 4: Simultaneous Resolution (Rock-Paper-Scissors Style)](#pattern-4-simultaneous-resolution-rock-paper-scissors-style)
- [Pattern 5: Dice-Pool Mechanics](#pattern-5-dice-pool-mechanics)
- [Complete Game-System Examples](#complete-game-system-examples)

---

## Pattern 1: Classic HP Combat (Auto Mode)

The simplest design: player and enemy trade hits each round, the first to reach 0 HP loses. Player acts automatically.

```yaml
# content/mygame/combat-systems/classic-combat.yaml
apiVersion: oscilla/v1
kind: CombatSystem
metadata:
  name: classic-combat
spec:
  player_defeat_condition:
    type: character_stat
    name: hp
    lte: 0
  enemy_defeat_condition:
    type: enemy_stat
    stat: hp
    lte: 0
  turn_order: player_first
  player_turn_mode: auto
  player_damage_formulas:
    - formula: "{{ clamp(player.get('strength', 5) - enemy_stats.get('defense', 0), 1, 9999) * -1 }}"
      target_stat: hp
      target: enemy
      display: "Attack"
  enemy_damage_formulas:
    - formula: "{{ clamp(enemy_stats.get('attack', 0) - player.get('armor', 0), 0, 9999) * -1 }}"
      target_stat: hp
      target: player
      display: "Enemy strikes"
```

Point to it in `game.yaml`:

```yaml
spec:
  default_combat_system: classic-combat
```

Enemy manifests declare `stats:` with the keys your formulas reference:

```yaml
spec:
  stats:
    hp: 30
    attack: 8
    defense: 2
  on_defeat_effects:
    - type: stat_change
      stat: xp
      amount: 50
```

---

## Pattern 2: Choice-Mode Skill Menu

The player chooses an action from a menu each round. Skills are used instead of automatic formulas.

```yaml
# content/mygame/combat-systems/tactical-combat.yaml
apiVersion: oscilla/v1
kind: CombatSystem
metadata:
  name: tactical-combat
spec:
  player_defeat_condition:
    type: character_stat
    name: hp
    lte: 0
  enemy_defeat_condition:
    type: enemy_stat
    stat: hp
    lte: 0
  turn_order: player_first
  player_turn_mode: choice
  skill_contexts:
    - combat
  system_skills:
    - skill: basic-strike # always available
    - skill: power-strike
      condition: # only shown when charged
        type: character_stat
        name: energy
        gte: 10
  enemy_damage_formulas:
    - formula: "{{ clamp(enemy_stats.get('attack', 0), 0, 9999) * -1 }}"
      target_stat: hp
      target: player
      display: "Enemy attacks"
```

Skill manifests set `contexts: [combat]` to appear in the menu. System skills appear regardless of whether the player has permanently learned them:

```yaml
# content/mygame/skills/basic-strike.yaml
apiVersion: oscilla/v1
kind: Skill
metadata:
  name: basic-strike
spec:
  displayName: "Strike"
  description: "A basic attack."
  contexts:
    - combat
  effects:
    - type: stat_change
      target: enemy
      stat: hp
      amount: -8
```

---

## Pattern 3: Initiative-Based Turn Order

Each round, both combatants roll for initiative. The winner acts first. Ties go to the player.

```yaml
# content/mygame/combat-systems/initiative-combat.yaml
apiVersion: oscilla/v1
kind: CombatSystem
metadata:
  name: initiative-combat
spec:
  player_defeat_condition:
    type: character_stat
    name: hp
    lte: 0
  enemy_defeat_condition:
    type: enemy_stat
    stat: hp
    lte: 0
  turn_order: initiative
  player_initiative_formula: "{{ player.get('dexterity', 5) + roll(1, 6) }}"
  enemy_initiative_formula: "{{ enemy_stats.get('speed', 5) + roll(1, 6) }}"
  initiative_tie: player_first
  player_turn_mode: auto
  player_damage_formulas:
    - formula: "{{ clamp(player.get('strength', 5), 1, 9999) * -1 }}"
      target_stat: hp
      target: enemy
      display: "Attack"
  enemy_damage_formulas:
    - formula: "{{ clamp(enemy_stats.get('attack', 0), 0, 9999) * -1 }}"
      target_stat: hp
      target: player
      display: "Enemy attacks"
```

Fast enemies (high `speed`) will often go first, but a lucky roll can surprise them.

---

## Pattern 4: Simultaneous Resolution (Rock-Paper-Scissors Style)

Both combatants act at the same time. A defeat that might occur mid-round in sequential mode only takes effect after both actors finish. A `resolution_formulas` phase handles cleanup or momentum effects.

```yaml
# content/mygame/combat-systems/simultaneous-combat.yaml
apiVersion: oscilla/v1
kind: CombatSystem
metadata:
  name: simultaneous-combat
spec:
  player_defeat_condition:
    type: character_stat
    name: hp
    lte: 0
  enemy_defeat_condition:
    type: enemy_stat
    stat: hp
    lte: 0
  turn_order: simultaneous
  simultaneous_defeat_result: player_wins # mutual defeat favors the player
  player_turn_mode: auto
  player_damage_formulas:
    - formula: "{{ clamp(player.get('strength', 5), 1, 9999) * -1 }}"
      target_stat: hp
      target: enemy
  enemy_damage_formulas:
    - formula: "{{ clamp(enemy_stats.get('attack', 0), 0, 9999) * -1 }}"
      target_stat: hp
      target: player
  # Both take damage each round regardless of who "dies" first
  resolution_formulas:
    - formula: "{{ combat_stats.get('poison_ticks', 0) * -3 }}"
      target_stat: hp
      target: enemy
      display: "Poison burns"
  combat_stats:
    - name: poison_ticks
      default: 0
```

---

## Pattern 5: Dice-Pool Mechanics

Use `rollpool` for success-counting systems (like the World of Darkness or Chronicles of Darkness approach): roll a pool of dice, count dice at or above a threshold.

```yaml
# content/mygame/combat-systems/dice-pool-combat.yaml
apiVersion: oscilla/v1
kind: CombatSystem
metadata:
  name: dice-pool-combat
spec:
  player_defeat_condition:
    type: character_stat
    name: hp
    lte: 0
  enemy_defeat_condition:
    type: enemy_stat
    stat: hp
    lte: 0
  turn_order: player_first
  player_turn_mode: auto
  player_damage_formulas:
    - formula: |
        {% set pool = player.get('skill_dice', 3) %}
        {% set hits = rollpool(pool, 10, 7) %}
        {{ clamp(hits * 3, 0, 9999) * -1 }}
      target_stat: hp
      target: enemy
      display: "Dice pool attack"
      threshold_effects:
        - min: -9 # 3+ hits — critical blow
          effects:
            - type: narrative
              text: "A devastating blow!"
        - max: 0 # 0 hits — botch
          effects:
            - type: narrative
              text: "A total miss."
  enemy_damage_formulas:
    - formula: "{{ rollsum(enemy_stats.get('attack_dice', 2), 6) * -1 }}"
      target_stat: hp
      target: player
      display: "Enemy rolls attack"
```

`rollpool(pool, 10, 7)` rolls `pool` d10s and returns the count where the result is 7 or higher. Multiply hits by your damage-per-success constant.

---

_Back to [Combat Systems](../combat-systems.md) for the full field reference._

---

## Complete Game-System Examples

The files below each model a specific tabletop RPG or game system. They are standalone multi-document YAML files (one `CombatSystem` plus companion `Skill` and `Enemy` manifests) that demonstrate how the engine's features map to real game mechanics. Some push the engine to its limits — those are annotated.

| File                                                                                     | System                   | What it demonstrates                                                                                                                  |
| ---------------------------------------------------------------------------------------- | ------------------------ | ------------------------------------------------------------------------------------------------------------------------------------- |
| [13th-age-escalation-die.yaml](combat-examples/13th-age-escalation-die.yaml)             | 13th Age                 | `combat_stats` escalation counter incremented via `on_round_end`; escalation-gated system skill unlocked by a `combat_stat` condition |
| [blades-in-the-dark.yaml](combat-examples/blades-in-the-dark.yaml)                       | Blades in the Dark       | Dice pool with `rollpool()`; three-tier `threshold_effects` bands mapping Position/Effect levels                                      |
| [burning-wheel-scripted-combat.yaml](combat-examples/burning-wheel-scripted-combat.yaml) | Burning Wheel            | Scripted simultaneous combat; intent–action maneuver encoding via `resolution_formulas`                                               |
| [call-of-cthulhu-sanity.yaml](combat-examples/call-of-cthulhu-sanity.yaml)               | Call of Cthulhu          | Dual-track defeat (HP + Sanity) using an `any` composite condition; `on_combat_start` Sanity drain                                    |
| [cortex-prime.yaml](combat-examples/cortex-prime.yaml)                                   | Cortex Prime             | Approximate "sum of 2 highest dice" using `{% set %}` bindings — **Breaks the Model** (see file header)                               |
| [dnd5e-action-economy.yaml](combat-examples/dnd5e-action-economy.yaml)                   | D&D 5e (Action Economy)  | Action + Bonus Action approximation via compound skills — **Possible but Awkward**                                                    |
| [dnd5e-attack-roll.yaml](combat-examples/dnd5e-attack-roll.yaml)                         | D&D 5e (Attack Roll)     | Gated d20 attack roll with `threshold_effects`; conditional damage formula                                                            |
| [ironsworn-progress-clocks.yaml](combat-examples/ironsworn-progress-clocks.yaml)         | Ironsworn                | Progress clock victory condition on `combat_stat`; `threshold_effects` clock advancement in the Strike skill                          |
| [morale-system.yaml](combat-examples/morale-system.yaml)                                 | Generic Morale           | Non-HP defeat condition; enemy flees when morale breaks rather than when HP reaches zero                                              |
| [pbta-tiered-outcomes.yaml](combat-examples/pbta-tiered-outcomes.yaml)                   | PbtA (Apocalypse World)  | `target_stat: null` threshold-only mode; dynamic `value` formula strings in tier bands                                                |
| [poker.yaml](combat-examples/poker.yaml)                                                 | Poker                    | Card draw strategy game; `resolution_formulas` state-sharing across entries; delta-encode pattern for chip tracking                   |
| [rock-paper-scissors.yaml](combat-examples/rock-paper-scissors.yaml)                     | Rock-Paper-Scissors      | Canonical `simultaneous` + `resolution_formulas` example; intent-declaration skills                                                   |
| [savage-worlds-wild-die.yaml](combat-examples/savage-worlds-wild-die.yaml)               | Savage Worlds            | Wild Die: `max(roll(trait_die), roll(6))`; raise approximation via `threshold_effects`                                                |
| [vampire-the-masquerade.yaml](combat-examples/vampire-the-masquerade.yaml)               | Vampire: the Masquerade  | Split pool `rollpool()` for Hunger dice approximation — **Breaks the Model** (see file header)                                        |
| [warhammer-fantasy-battle.yaml](combat-examples/warhammer-fantasy-battle.yaml)           | Warhammer Fantasy Battle | Two-stage gated damage in a single formula; inline ternary wound table                                                                |
| [warhammer-frpg-opposed-rolls.yaml](combat-examples/warhammer-frpg-opposed-rolls.yaml)   | Warhammer FRP            | Opposed simultaneous rolls serialized via a `combat_stat` channel — **Possible but Awkward**                                          |
