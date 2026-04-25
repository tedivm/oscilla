# Combat System

## Purpose

The combat system provides a manifest-driven framework for two-party adversarial encounters. A `CombatSystem` manifest declares defeat conditions, damage formula lists, turn order, initiative, player action mode, lifecycle hooks, and ephemeral combat stats. The engine dispatches all combat arithmetic to the declared system with no hardcoded stat assumptions; any game can define its own stat names, victory conditions, and available actions. Multiple combat systems per game are supported; individual combat steps can override any system field for a single encounter.

## Requirements

### Requirement: CombatSystem manifest kind

A `CombatSystem` manifest SHALL be loadable via the standard manifest envelope (`apiVersion: oscilla/v1`, `kind: CombatSystem`). Its `spec` SHALL carry all fields governing a two-party adversarial encounter. The content registry SHALL store all registered `CombatSystem` manifests under a `combat_systems` namespace. When exactly one `CombatSystem` is registered and no explicit `default_combat_system` is set on the `GameSpec`, that system SHALL be auto-promoted to the default.

#### Scenario: Single combat system auto-promotes to default

- **WHEN** a game package declares exactly one `CombatSystem` manifest and `GameSpec.default_combat_system` is not set
- **THEN** `registry.get_default_combat_system()` returns that manifest

#### Scenario: Explicit default overrides auto-promotion

- **WHEN** a game package declares two `CombatSystem` manifests and `GameSpec.default_combat_system` names one of them
- **THEN** `registry.get_default_combat_system()` returns the explicitly named manifest

#### Scenario: No combat system returns None

- **WHEN** no `CombatSystem` manifests are registered
- **THEN** `registry.get_default_combat_system()` returns `None`

#### Scenario: Combat step without resolvable system is a load error

- **WHEN** an adventure contains a `combat` step and no `CombatSystem` can be resolved for it
- **THEN** the content validator emits a hard error identifying the adventure

---

### Requirement: Defeat conditions

A `CombatSystemSpec` SHALL declare `player_defeat_condition` and `enemy_defeat_condition` as full `Condition` trees evaluated after each actor phase. An `enemy_stat` condition leaf SHALL check a named key in `enemy_stats`; a `combat_stat` condition leaf SHALL check a named key in `combat_stats`. Both leaves SHALL evaluate to `false` with a logged warning when called outside a combat context (i.e., when `enemy_stats` or `combat_stats` is `None`).

#### Scenario: Enemy defeat condition using enemy_stat leaf

- **WHEN** `enemy_defeat_condition` is an `enemy_stat` condition with `stat: hp` and `lte: 0`, and `enemy_stats["hp"]` reaches 0 after a damage formula
- **THEN** the defeat condition evaluates to `true` and combat ends with a player victory

#### Scenario: Player defeat condition using character_stat leaf

- **WHEN** `player_defeat_condition` references `player.stats["hp"]` and the player's HP reaches 0
- **THEN** the defeat condition evaluates to `true` and combat ends with an enemy victory

#### Scenario: Combat stat condition evaluated mid-combat

- **WHEN** `enemy_defeat_condition` is a `combat_stat` condition checking `lives <= 0` and `combat_stats["lives"]` reaches 0 via a `stat_change target='combat'` effect
- **THEN** the defeat condition evaluates to `true`

#### Scenario: Enemy stat condition outside combat

- **WHEN** `evaluate(EnemyStatCondition(...), player, enemy_stats=None)` is called
- **THEN** it returns `false` and logs a warning

---

### Requirement: Damage formula lists

A `CombatSystemSpec` SHALL declare `player_damage_formulas` and `enemy_damage_formulas` as lists of `DamageFormulaEntry` objects. Each `DamageFormulaEntry` SHALL have a Jinja2 `formula` string rendered in `CombatFormulaContext`, a `target_stat` naming the stat key to decrement, a `target` routing field (`"player"`, `"enemy"`, or `"combat"`), an optional `display` label, and an optional `threshold_effects` list. All entries in a list SHALL apply in order before defeat conditions are evaluated. A `DamageFormulaEntry` with `target_stat: null` and an empty `threshold_effects` list SHALL be a hard load error. Formulas SHALL be mock-rendered at load time to catch syntax errors.

#### Scenario: Player damage formula decrements enemy stat

- **WHEN** `player_damage_formulas` contains one entry with `target_stat: hp`, `target: enemy`, and `formula: "{{ player.stats['strength'] - enemy_stats['defense'] }}"`
- **THEN** each round the result is subtracted from `enemy_stats["hp"]`

#### Scenario: Multiple player damage formulas apply in order

- **WHEN** `player_damage_formulas` contains two entries targeting different enemy stats
- **THEN** both are applied sequentially in the declared order before the defeat check

#### Scenario: Threshold effects fire in matching band

- **WHEN** a formula result falls within a `ThresholdEffectBand` range and that band declares `effects`
- **THEN** the effects in that band are run after the stat decrement

#### Scenario: formula syntax error caught at load time

- **WHEN** a `DamageFormulaEntry.formula` contains invalid Jinja2 syntax
- **THEN** the content validator emits a hard error before the game starts

---

### Requirement: Resolution formulas phase

A `CombatSystemSpec` MAY declare `resolution_formulas: List[DamageFormulaEntry]`. These formulas SHALL fire once per round after all actor phases have completed, before defeat conditions are evaluated. In sequential turn-order modes, `resolution_formulas` SHALL be skipped if a mid-round defeat occurred. In `"simultaneous"` mode, `resolution_formulas` SHALL always execute. Each entry in the list has full visibility into the final committed state of both `enemy_stats` and `combat_stats`.

#### Scenario: Resolution formulas fire after actor phases in sequential mode

- **WHEN** neither actor is defeated after their phases and `resolution_formulas` is non-empty
- **THEN** each entry is applied in order before the final defeat check

#### Scenario: Resolution formulas skipped on mid-round defeat in sequential mode

- **WHEN** the first actor defeats the second during their phase in sequential mode
- **THEN** `resolution_formulas` do not execute

#### Scenario: Resolution formulas always fire in simultaneous mode

- **WHEN** `turn_order: "simultaneous"` is set and both actor phases complete
- **THEN** `resolution_formulas` always execute regardless of stat values after actor phases

---

### Requirement: Player turn modes

A `CombatSystemSpec` SHALL declare `player_turn_mode: "auto" | "choice"`. In `"auto"` mode, `player_damage_formulas` fire automatically each round; no player menu is presented. In `"choice"` mode, the player selects an action from a menu that includes: `SystemSkillEntry` skills declared on the system (filtered by optional `condition`), player-owned skills whose `contexts` intersects the system's `skill_contexts`, combat-context items in the player's inventory, and always-present "Do Nothing". `player_damage_formulas` and `player_turn_mode: "choice"` present simultaneously SHALL be a hard load error.

#### Scenario: Auto mode fires formulas without player input

- **WHEN** `player_turn_mode: "auto"` and `player_damage_formulas` is non-empty
- **THEN** the player's damage formulas apply automatically each round without presenting a menu

#### Scenario: Choice mode presents skill menu

- **WHEN** `player_turn_mode: "choice"` and the player has a skill with a matching context
- **THEN** that skill appears in the combat action menu

#### Scenario: Choice mode always includes Do Nothing

- **WHEN** `player_turn_mode: "choice"` regardless of available skills
- **THEN** "Do Nothing" is always present as an option

#### Scenario: Choice mode with player_damage_formulas is a load error

- **WHEN** `CombatSystemSpec` has `player_turn_mode: "choice"` and non-empty `player_damage_formulas`
- **THEN** the content validator emits a hard error

#### Scenario: SystemSkillEntry condition hides skill when false

- **WHEN** a `SystemSkillEntry` has a `condition` that evaluates to `false` for the current player state
- **THEN** that skill does not appear in the choice-mode menu for that round

---

### Requirement: Turn order and initiative

A `CombatSystemSpec` SHALL declare `turn_order: "player_first" | "enemy_first" | "initiative" | "simultaneous"`. `"player_first"` and `"enemy_first"` are deterministic. `"initiative"` requires both `player_initiative_formula` and `enemy_initiative_formula`; the higher result acts first; equal results are resolved by `initiative_tie: "player_first" | "enemy_first"` (default `"player_first"`). `"simultaneous"` causes both actor phases to always complete before any defeat check. Initiative formulas MUST be absent when `turn_order` is not `"initiative"` (warning); initiative formulas MUST be present when `turn_order` is `"initiative"` (error).

#### Scenario: Player-first turn order

- **WHEN** `turn_order: "player_first"`
- **THEN** the player phase executes first; if the player wins, the enemy phase is skipped

#### Scenario: Initiative player wins roll

- **WHEN** `turn_order: "initiative"` and `player_initiative_formula` renders a higher value than `enemy_initiative_formula`
- **THEN** the player acts first that round

#### Scenario: Initiative tie resolved by initiative_tie field

- **WHEN** both initiative formulas render the same value and `initiative_tie: "enemy_first"`
- **THEN** the enemy acts first that round

#### Scenario: Simultaneous mode both phases always complete

- **WHEN** `turn_order: "simultaneous"`
- **THEN** both actor phases complete before any defeat check; mutual defeat is possible

#### Scenario: Mutual defeat in simultaneous mode

- **WHEN** both actors reach their defeat conditions in the same round under `"simultaneous"` mode
- **THEN** the outcome is governed by `simultaneous_defeat_result` (default: `"enemy_victory"`)

#### Scenario: Initiative formula missing for initiative turn order

- **WHEN** `turn_order: "initiative"` and one or both initiative formulas are absent
- **THEN** the content validator emits a hard error

---

### Requirement: Lifecycle hooks

A `CombatSystemSpec` MAY declare any of: `on_combat_start`, `on_combat_end`, `on_combat_victory`, `on_combat_defeat`, `on_round_end` — each a `List[Effect]`. `on_combat_start` fires once when a new combat begins (not on session resume). `on_combat_end` fires once at resolution regardless of outcome before `on_defeat_effects`, loot, and branch dispatch. `on_combat_victory` and `on_combat_defeat` fire after `on_combat_end`. `on_round_end` fires at the end of each complete round where no defeat occurred.

#### Scenario: on_combat_start fires on new encounter only

- **WHEN** a new combat begins (not resumed from a save)
- **THEN** `on_combat_start` effects fire before the first round

#### Scenario: on_combat_start does not fire on resume

- **WHEN** a combat is resumed mid-encounter (enemy_stats loaded from step_state)
- **THEN** `on_combat_start` does not fire again

#### Scenario: on_combat_end fires on both victory and defeat

- **WHEN** combat ends by any outcome (player win, player loss, or flee)
- **THEN** `on_combat_end` effects fire before `on_combat_victory` or `on_combat_defeat`

#### Scenario: on_round_end fires after complete rounds only

- **WHEN** a round completes without any defeat occurring
- **THEN** `on_round_end` effects fire at the end of that round

---

### Requirement: Combat stats (ephemeral)

A `CombatSystemSpec` MAY declare `combat_stats: List[CombatStatEntry]`, each with `name: str` and `default: int = 0`. Combat stats are initialized at encounter start and discarded at encounter end; they are never written to the player's global stat store. They live in `step_state["combat_stats"]` for save/resume across sessions. They are accessible in all formula expressions as `combat_stats['name']` and are mutable via `stat_change target='combat'` or `stat_set target='combat'`.

#### Scenario: Combat stat initialized to default at encounter start

- **WHEN** a new combat begins and `CombatSystemSpec` declares `combat_stats: [{name: escalation, default: 0}]`
- **THEN** `combat_stats["escalation"]` is `0` at the start of the first round

#### Scenario: Combat stat mutable via stat_change effect

- **WHEN** a `stat_change` effect with `target: "combat"` and `stat: "escalation"` fires during combat
- **THEN** `combat_stats["escalation"]` is updated accordingly

#### Scenario: Combat stat is not written to player stats on combat end

- **WHEN** combat ends
- **THEN** `combat_stats` values are discarded and not applied to `player.stats`

#### Scenario: Combat stat survives save and resume

- **WHEN** a session is saved mid-combat and resumed
- **THEN** `combat_stats` values are restored from `step_state["combat_stats"]`

---

### Requirement: Per-step combat overrides

A `CombatStep` MAY declare a `combat_system: str` to select a named system for that encounter, and a `combat_overrides: CombatStepOverrides` to override any `CombatSystemSpec` fields without authoring a full separate manifest. Overrides are merged at runtime; absent override fields leave the base system values intact. The merged result is validated as a complete `CombatSystemSpec` at load time.

#### Scenario: Per-step system name selects specific manifest

- **WHEN** a `CombatStep` declares `combat_system: "boss-combat"` and that manifest is registered
- **THEN** the boss-combat system governs that encounter instead of the game default

#### Scenario: Per-step override replaces a single field

- **WHEN** `combat_overrides` sets only `turn_order: "enemy_first"`
- **THEN** all other base system fields are preserved; only turn order changes for that encounter

#### Scenario: Override that conflicts with remaining spec is a load error

- **WHEN** an override sets `player_turn_mode: "choice"` on a system that has non-empty `player_damage_formulas` and no override to clear them
- **THEN** the validator emits a hard error for the merged result

---

### Requirement: Formula globals

The template engine SHALL provide `rollpool`, `rollsum`, `keephigh`, and `clamp` as safe global functions available in all combat formula expressions. These functions SHALL raise `ValueError` on invalid inputs.

#### Scenario: rollpool counts successes

- **WHEN** `rollpool(5, 6, 4)` is called
- **THEN** it returns the count of dice (out of 5d6) that rolled ≥ 4, as an integer between 0 and 5

#### Scenario: rollsum returns total

- **WHEN** `rollsum(3, 6)` is called
- **THEN** it returns an integer between 3 and 18

#### Scenario: keephigh returns sum of highest k

- **WHEN** `keephigh(4, 6, 3)` is called
- **THEN** it returns the sum of the highest 3 dice rolled out of 4d6

#### Scenario: clamp restricts value to range

- **WHEN** `clamp(15, 0, 10)` is called
- **THEN** it returns 10

#### Scenario: rollpool with invalid input raises ValueError

- **WHEN** `rollpool(0, 6, 4)` is called (n < 1)
- **THEN** it raises `ValueError`

---

### Requirement: stat_change target routing

The `stat_change` and `stat_set` effects SHALL correctly dispatch to three stat namespaces based on `target`: `"player"` mutates `player.stats`; `"enemy"` mutates `enemy_stats[effect.stat]` (using the `stat` field as the key); `"combat"` mutates `combat_stats[effect.stat]`. A `stat_change target='enemy'` SHALL correctly use the `stat` field as the dictionary key, not any hardcoded field name. `heal target='enemy'` SHALL emit a deprecation warning at load time; the `HealEffect` player path is unchanged.

#### Scenario: stat_change target enemy uses stat field

- **WHEN** `stat_change(target="enemy", stat="hp", value=-10)` runs in a combat context where `enemy_stats = {"hp": 50}`
- **THEN** `enemy_stats["hp"]` becomes 40

#### Scenario: stat_change target combat mutates combat_stats

- **WHEN** `stat_change(target="combat", stat="escalation", value=1)` runs
- **THEN** `combat_stats["escalation"]` is incremented by 1

#### Scenario: heal target enemy emits deprecation warning

- **WHEN** the content is loaded and an adventure step contains `heal(target="enemy")`
- **THEN** the validator emits a deprecation warning suggesting `stat_change target='enemy'` instead
