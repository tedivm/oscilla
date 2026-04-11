## MODIFIED Requirements

### Requirement: Buff modifiers provide passive combat bonuses

All timed combat effects — both tick-based (DoTs/heals) and passive modifiers (damage scaling) — are delivered exclusively through `kind: Buff` manifests applied via `apply_buff` effects. `SkillSpec` does NOT have a `periodic_effect` field; skills that grant timed effects add an `apply_buff` entry to `use_effects` referencing a named Buff manifest.

When a Buff manifest is applied, an `ActiveCombatEffect` is added to `CombatContext.active_effects` with `label` set to the Buff manifest's `metadata.name`. The label is stable and can be targeted by `DispelEffect` to remove the effect before natural expiry. A buff with no label (empty `label`) cannot be dispelled by name.

`CombatModifier` supports four types: `damage_reduction`, `damage_amplify`, `damage_reflect`, `damage_vulnerability`. Each carries a `percent` (`int | str` — string values are variable names resolved at apply time from `BuffSpec.variables`) and a `target` (`"player"` | `"enemy"`).

`ActiveCombatEffect` SHALL include the following new fields in addition to its existing ones:

- `exclusion_group: str = ""` — mirrors `BuffSpec.exclusion_group`; empty string when no group.
- `priority: int = 0` — mirrors `BuffSpec.priority`; used by the exclusion-group check.
- `is_persistent: bool = False` — `True` when this effect was loaded from `CharacterState.active_buffs` or was created from a buff with a time-based expiry field. Tracked to control writeback at combat exit.

The combat loop SHALL:

- Consult `damage_amplify` modifiers (via `_apply_damage_amplify`) when computing the player's basic attack damage, scaling outgoing damage by `(1 + total_amplify_percent/100)`.
- Consult `damage_reduction` and `damage_vulnerability` modifiers (via `_apply_incoming_modifiers`) when computing incoming enemy attack damage, applying `factor = max(0.0, 1.0 - reduction/100 + vulnerability/100)`. If base > 0, minimum applied damage is 1.
- Consult `damage_reflect` modifiers (via `_apply_reflect`) after the player takes damage, bouncing `max(1, int(taken * reflect_percent/100))` damage onto the enemy (or player, for enemy-held thorns).
- Stack all modifiers of the same type additively across all active `ActiveCombatEffect` entries.

#### Scenario: Buff applied via apply_buff can be dispelled by manifest name

- **WHEN** an `apply_buff` effect for the `on-fire` buff is dispatched, adding an `ActiveCombatEffect` with `label="on-fire"`
- **AND** a `dispel` effect with `label: "on-fire"` is later dispatched
- **THEN** the `ActiveCombatEffect` is immediately removed from `CombatContext.active_effects` and no further ticks fire

#### Scenario: damage_reduction modifier reduces incoming enemy attack

- **WHEN** a player has an active `ActiveCombatEffect` with `modifiers: [{type: damage_reduction, percent: 40, target: player}]`
- **AND** the enemy's raw attack (after dexterity mitigation) is 10
- **THEN** the player takes `max(1, int(10 * 0.60)) = 6` damage

#### Scenario: damage_amplify modifier increases player's basic attack

- **WHEN** a player has an active `ActiveCombatEffect` with `modifiers: [{type: damage_amplify, percent: 50, target: player}]`
- **AND** the player's base attack (strength - enemy defense) is 10
- **THEN** the enemy takes `int(10 * 1.50) = 15` damage

#### Scenario: damage_reflect bounces hit back to attacker

- **WHEN** a player has an active `ActiveCombatEffect` with `modifiers: [{type: damage_reflect, percent: 30, target: player}]`
- **AND** the player takes 10 incoming damage after all reduction modifiers
- **THEN** the enemy also receives `max(1, int(10 * 0.30)) = 3` damage via `_apply_reflect`

#### Scenario: damage_vulnerability increases incoming damage for target

- **WHEN** a player has an active `ActiveCombatEffect` with `modifiers: [{type: damage_vulnerability, percent: 25, target: player}]`
- **AND** the enemy's raw attack is 10
- **THEN** the player takes `max(1, int(10 * 1.25)) = 12` damage

#### Scenario: Reduction and vulnerability modifiers stack additively

- **WHEN** a player has both `damage_reduction: 40%` and `damage_vulnerability: 25%` active simultaneously
- **AND** the enemy's raw incoming attack is 10
- **THEN** `factor = 1.0 - 0.40 + 0.25 = 0.85`, and the player takes `max(1, int(10 * 0.85)) = 8` damage

#### Scenario: Pure modifier buff ticks without per-turn dispatch

- **WHEN** a `BuffSpec` declares only `modifiers` (no `per_turn_effects`)
- **THEN** `_tick_active_effects` skips the per-turn dispatch loop but still decrements `remaining_turns` and removes the effect on expiry

---

### Requirement: Periodic effect ticking

At the top of each combat round (before the player acts), the combat loop SHALL tick all entries in `CombatContext.active_effects`. For each `ActiveCombatEffect`:

1. Display source_skill name and remaining turns count.
2. Dispatch each effect in `per_turn_effects` through `run_effect()` with the relevant `combat` context.
3. Decrement `remaining_turns` by 1.
4. Remove entries whose `remaining_turns` has reached 0.

#### Scenario: Buff ticks for declared duration

- **WHEN** an `apply_buff` effect applies a buff with `duration: {turns: 3}` and `per_turn_effects: [{type: stat_change, amount: -5, target: enemy}]`
- **THEN** the enemy takes -5 HP each at the top of the next 3 rounds; no tick occurs on round 4

#### Scenario: Expired effects are removed from active_effects

- **WHEN** an `ActiveCombatEffect` reaches `remaining_turns == 0` after ticking
- **THEN** it is removed from `CombatContext.active_effects`

#### Scenario: Multiple independent effects tick together

- **WHEN** two different periodic effects are active simultaneously
- **THEN** both tick each round; expiry is tracked independently

## REMOVED Requirements

### Requirement: BuffSpec.duration_turns

**Reason:** Replaced by `BuffSpec.duration: BuffDuration`. The `BuffDuration` model expresses the same per-combat turn count via `duration.turns` and additionally supports time-based expiry fields for persistent buffs. Every existing `duration_turns: N` must be migrated to `duration: {turns: N}`.

**Migration:** Replace `duration_turns: N` with `duration: {turns: N}` in all buff manifests. The testlandia content package is the only existing content and will be updated as part of this change.
