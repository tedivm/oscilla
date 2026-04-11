# Combat Skills

## Purpose

The combat skills system defines how skills are used in turn-based combat, including the CombatContext runtime state, player and enemy skill actions, buff modifier mechanics, periodic effect ticking, and equipment-granted buffs applied at combat start.

## Requirements

### Requirement: CombatContext carries live combat state

The engine SHALL define a `CombatContext` dataclass that is constructed at the start of each `run_combat()` call and destroyed when combat ends. It SHALL never be serialized.

`CombatContext` SHALL contain:

- `enemy_hp: int` — current enemy HP mirrored to `step_state` for persistence.
- `enemy_ref: str` — the enemy manifest name.
- `active_effects: List[ActiveCombatEffect]` — ticking periodic effects.
- `skill_uses_this_combat: Dict[str, int]` — maps skill_ref to the turn number it was last used; used for turn-scope cooldown enforcement.
- `turn_number: int` — starts at 1, incremented each round.
- `enemy_resources: Dict[str, int]` — initialized from `EnemySpec.skill_resources`; not persisted.

`ActiveCombatEffect` SHALL have `source_skill: str`, `target: Literal["player", "enemy"]`, `remaining_turns: int`, `per_turn_effects: List[Effect]` (may be empty), `modifiers: List[CombatModifier]` (default `[]`), and `label: str` (default `""`). When created by `ApplyBuffEffect`, the `label` is set from `buff_manifest.metadata.name`; `label` is used by `DispelEffect` to identify and remove the effect before natural expiry; `modifiers` are consulted by the combat loop during damage arithmetic.

#### Scenario: CombatContext initializes from EnemySpec

- **WHEN** a combat step begins for an enemy with `skill_resources: {mana: 50}`
- **THEN** `CombatContext.enemy_resources == {"mana": 50}` at round 1

#### Scenario: CombatContext stores turn number

- **WHEN** three combat rounds complete
- **THEN** `CombatContext.turn_number == 4` at the start of round 4

---

### Requirement: Player skill use in combat

The combat turn loop SHALL present a dynamic menu: `["Attack", ...skills..., "Flee"]`. Skills appear between Attack and Flee, one entry per skill ref in `player.available_skills(registry)` where the skill's `contexts` includes `"combat"`. Selecting a skill action SHALL invoke `_use_skill_in_combat()`.

`_use_skill_in_combat()` SHALL validate the following in order before applying any effects:

1. Turn-scope cooldown not active.
2. Adventure-scope cooldown not active.
3. Resource cost is affordable.
4. `requires` condition is satisfied (if declared).

If any check fails, the TUI SHALL display an appropriate message and the function SHALL return False without consuming any resources or advancing cooldowns.

If all checks pass:

1. Resource is deducted from `player.stats`.
2. Cooldown is recorded:
   - Turn-scope: tracked in `CombatContext.skill_uses_this_combat` (turn number at use).
   - Adventure-scope: `skill_tick_expiry` and `skill_real_expiry` on CharacterState are set to `internal_ticks + required_ticks` and `time.time() + required_seconds` respectively.
3. `use_effects` are dispatched via `run_effect()`.

Adventure-scope cooldown is active when `internal_ticks < skill_tick_expiry[ref]` OR `time.time() < skill_real_expiry[ref]`.

#### Scenario: Player selects skill action

- **WHEN** a player with the "fireball" skill in their available_skills selects "Skill: Fireball" from the combat menu
- **THEN** fireball's use_effects are dispatched and any resource cost is deducted

#### Scenario: Skill blocked by insufficient resource

- **WHEN** a skill costs 10 mana and the player has 5 mana
- **THEN** the TUI shows a "Not enough mana" message and no effects fire

#### Scenario: Turn-scope cooldown blocks reuse

- **WHEN** a skill with `cooldown: {scope: turn, turns: 3}` was last used on turn 1
- **THEN** attempting to use it again on turn 2 or 3 shows a cooldown message
- **THEN** the skill fires normally on turn 4

#### Scenario: Adventure-scope tick cooldown blocks reuse

- **WHEN** a skill with `cooldown: {ticks: 3}` is used at `internal_ticks == 10`
- **THEN** `skill_tick_expiry[skill_ref] == 13`
- **THEN** the skill cannot be used again while `internal_ticks < 13`

#### Scenario: Adventure-scope ticks cooldown expires after advancement

- **WHEN** a skill with `cooldown: {ticks: 3}` was used and `internal_ticks` has advanced to 13 or beyond
- **THEN** the skill is available for use again

#### Scenario: No skills available, menu shows only Attack and Flee

- **WHEN** the player has no skills with `contexts: [combat]`
- **THEN** the combat menu contains exactly `["Attack", "Flee"]` with no skill entries

---

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

- **WHEN** an ActiveCombatEffect reaches remaining_turns == 0 after ticking
- **THEN** it is removed from CombatContext.active_effects

#### Scenario: Multiple independent effects tick together

- **WHEN** two different periodic effects are active simultaneously
- **THEN** both tick each round; expiry is tracked independently

---

### Requirement: Enemy skills with timed dispatch

`EnemySpec` SHALL accept a `skills: List[EnemySkillEntry]` field (default `[]`). Each `EnemySkillEntry` has:

- `skill_ref: str` — Skill manifest name.
- `use_every_n_turns: int` (default 0) — auto-fire interval; 0 means never auto-fire.

At the end of each combat round (after the enemy's basic attack), the combat loop SHALL check each skill entry with `use_every_n_turns > 0`. If `turn_number % use_every_n_turns == 0`, the engine SHALL attempt to fire the skill. Resource cost is checked against `CombatContext.enemy_resources`; insufficient resources silently skip the skill. Enemy `use_effects` (including `apply_buff` effects) are dispatched via `run_effect()` with the combat context set.

Enemy skills that fire automatically in this phase are NOT blocked by cooldown logic; only resource availability controls them.

---

### Requirement: Equipment and inventory grant buffs at combat start

`ItemSpec` SHALL accept `grants_buffs_equipped: List[BuffGrant]` and `grants_buffs_held: List[BuffGrant]` fields (both default `[]`). `BuffGrant` has `buff_ref: str` and optional `variables: Dict[str, int] = {}` for per-call variable overrides.

At the start of each `run_combat()` call, after constructing `CombatContext` and before the first round, the engine SHALL:

1. For each equipped item (item ref in an equipment slot), dispatch `ApplyBuffEffect(buff_ref=grant.buff_ref, target="player", variables=grant.variables)` for each `BuffGrant` in its `grants_buffs_equipped`.
2. For each item anywhere in inventory (stacks or instances), dispatch `ApplyBuffEffect(buff_ref=grant.buff_ref, target="player", variables=grant.variables)` for each `BuffGrant` in its `grants_buffs_held`.

Buff refs that do not exist in the registry are logged as errors and skipped — they do not crash the combat.

#### Scenario: Equipped item grants buff at combat start

- **WHEN** the player has an item with `grants_buffs_equipped: [{buff_ref: thorns}]` equipped in a slot
- **AND** a Buff manifest named `"thorns"` exists in the registry
- **THEN** at the start of combat, an `ActiveCombatEffect` with `label="thorns"` is added before round 1

#### Scenario: Equipped item grants buff with variable override

- **WHEN** the player has an item with `grants_buffs_equipped: [{buff_ref: thorns, variables: {reflect_percent: 60}}]` equipped
- **AND** the `thorns` buff has `variables: {reflect_percent: 30}` and a `damage_reflect` modifier referencing `reflect_percent`
- **THEN** the resulting `ActiveCombatEffect` has a `damage_reflect` modifier with concrete `percent=60`

#### Scenario: Held item grants buff at combat start

- **WHEN** the player has an item with `grants_buffs_held: [{buff_ref: shielded}]` anywhere in inventory (not necessarily equipped)
- **AND** a Buff manifest named `"shielded"` exists in the registry
- **THEN** at the start of combat, an `ActiveCombatEffect` with `label="shielded"` is added before round 1
