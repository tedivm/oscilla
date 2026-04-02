# Adventure Pipeline

## Purpose

The adventure pipeline system orchestrates the execution of adventure content, handling step-by-step progression, effects processing, and TUI interaction.

## Requirements

### Requirement: Adventures are ordered lists of typed steps

An adventure manifest SHALL define a `steps` list where each entry is a typed step object. The adventure pipeline runner SHALL execute steps in declared order asynchronously. Each step SHALL have a `type` discriminator field that determines which handler processes it. All step handlers and the pipeline runner itself SHALL be `async def` coroutines.

#### Scenario: Steps execute in order

- **WHEN** an adventure with three steps (narrative, combat, stat_check) is run
- **THEN** the narrative step executes first, then combat, then stat_check

#### Scenario: Unknown step type is rejected at load time

- **WHEN** the content loader parses an adventure manifest containing a step with an unrecognised `type`
- **THEN** it raises a validation error identifying the adventure and the invalid step type

---

### Requirement: Narrative step

A `narrative` step SHALL display a text body to the player and pause until the player acknowledges it (e.g., presses Enter). The `run_narrative` handler SHALL be an `async def` function that `await`s `tui.show_text()` and `tui.wait_for_ack()`.

#### Scenario: Narrative is shown and acknowledged

- **WHEN** a narrative step executes
- **THEN** the step's `text` field is displayed and the pipeline pauses until player acknowledgement before proceeding to the next step

---

### Requirement: Combat step (turn-based)

A `combat` step SHALL initiate a turn-based fight between the player and an enemy referenced by name from the registry. Each round the player acts first, then the enemy. Combat ends when either the player's or enemy's HP reaches zero, or the player successfully flees. The `run_combat` handler SHALL be an `async def` function that `await`s all `tui` calls.

#### Scenario: Player wins combat

- **WHEN** a combat step runs and the player reduces the enemy's HP to 0
- **THEN** the combat step is marked complete and the pipeline proceeds to the next step

#### Scenario: Enemy defeats player

- **WHEN** a combat step runs and the enemy reduces the player's HP to 0
- **THEN** the adventure ends immediately and the player is returned to location selection

#### Scenario: Player flees

- **WHEN** a combat step runs and the player chooses to flee
- **THEN** the combat step terminates and the adventure ends (remaining steps are skipped)

#### Scenario: Turn order

- **WHEN** a combat round begins
- **THEN** the player's attack resolves before the enemy's attack in that round

---

### Requirement: Choice step (branching)

A `choice` step SHALL present the player with a labeled menu of options. Each option SHALL have a display label and a nested `steps` list that executes when that option is chosen. Conditions on options are evaluated at step execution time; options whose conditions are not met SHALL be hidden. The `run_choice` handler SHALL be an `async def` function that `await`s `tui.show_menu()`.

#### Scenario: Player selects an option

- **WHEN** a choice step presents three options and the player selects option 2
- **THEN** the nested steps of option 2 execute and the pipeline continues with the step after the choice

#### Scenario: Option hidden by unmet condition

- **WHEN** a choice step has an option with a `requires` condition that the player does not meet
- **THEN** that option is not shown in the menu

#### Scenario: All options hidden

- **WHEN** all options in a choice step have unmet conditions
- **THEN** the step is skipped and the pipeline continues to the next step

---

### Requirement: Item drop effect (loot)

An `item_drop` effect SHALL contain a weighted loot table of item references. The engine SHALL randomly select one item from the table (weighted by the `weight` field) and add one unit of that item to the player's inventory. The effect MAY have a `count` field specifying how many independent rolls to make (default 1). Effects are silent state mutations — no TUI output is produced.

#### Scenario: Item is granted to player

- **WHEN** an item_drop effect executes and the weighted roll selects `iron-sword`
- **THEN** one `iron-sword` is added to the player's inventory

#### Scenario: Multiple rolls

- **WHEN** an item_drop effect has `count: 3`
- **THEN** three independent weighted rolls are made and each resulting item is added to inventory

---

### Requirement: Milestone grant effect

A `milestone_grant` effect SHALL add a named milestone to the player's milestone set. If the player already has the milestone, the effect SHALL be a no-op. Effects are silent state mutations — no TUI output is produced.

#### Scenario: New milestone is granted

- **WHEN** a milestone_grant effect executes with `milestone: cleared-goblin-cave` and the player does not have that milestone
- **THEN** the milestone is added to the player's milestone set

#### Scenario: Duplicate milestone is no-op

- **WHEN** a milestone_grant effect executes with a milestone the player already has
- **THEN** the effect completes without error and the milestone set is unchanged

---

### Requirement: XP grant effect

An `xp_grant` effect SHALL add a specified amount of XP to the player. Negative amounts are valid (XP penalty). If the resulting total XP meets or exceeds the threshold for the next level, the player's level SHALL be incremented automatically and `max_hp` recalculated. Effects are silent state mutations — `add_xp()` returns the list of level numbers gained (empty if none) but no TUI output is produced at effect dispatch time. The updated level and HP are visible in `show_status()` after the adventure.

#### Scenario: XP is added without levelling

- **WHEN** an xp_grant effect grants 50 XP and the player does not have enough total XP to level up
- **THEN** the player's XP increases by 50 and level remains unchanged

#### Scenario: XP triggers level up

- **WHEN** an xp_grant effect grants enough XP to cross a level threshold
- **THEN** the player's level increments, `max_hp` is recalculated, and the new level is visible in the status display after the adventure completes

---

### Requirement: End adventure effect

An `end_adventure` effect SHALL immediately terminate the running adventure with a declared outcome (`completed`, `defeated`, or `fled`). It is useful for story branches where a narrative choice or a trap ends the run without combat. Effects that appear before `end_adventure` in the same effects list still fire; steps after the triggering branch are skipped.

#### Scenario: End adventure terminates adventure immediately

- **WHEN** an `end_adventure` effect with `outcome: defeated` fires inside a choice option's effects list
- **THEN** the adventure ends immediately with the `DEFEATED` outcome and remaining steps are not executed

#### Scenario: Effects before end_adventure still fire

- **WHEN** an effects list contains `[xp_grant, end_adventure]`
- **THEN** the XP is granted before the adventure terminates

---

### Requirement: goto and label for step navigation

Any top-level step in an adventure MAY carry a `label` string. An `OutcomeBranch` or `ChoiceOption` MAY specify a `goto` string instead of a `steps` list; when a `goto` fires, execution jumps to the first top-level step whose `label` matches. `goto` and `steps` are mutually exclusive within the same branch or option. Labels must be unique across all top-level steps in the adventure and are validated at load time.

#### Scenario: goto jumps to labeled step

- **WHEN** a combat step's `on_defeat` branch has `goto: shared-defeat` and a top-level step has `label: shared-defeat`
- **THEN** execution continues from the labeled step

#### Scenario: Duplicate label rejected at load time

- **WHEN** two top-level steps in the same adventure share the same `label` value
- **THEN** the content loader raises a validation error identifying the adventure and the duplicate label

#### Scenario: Unresolved goto rejected at load time

- **WHEN** a `goto` references a label that does not exist on any top-level step in that adventure
- **THEN** the content loader raises a validation error identifying the adventure and the missing label

---

### Requirement: Stat check step (conditional branch)

A `stat_check` step SHALL evaluate a condition against the current player state and execute one of two nested step lists: `on_pass` if the condition evaluates to true, or `on_fail` if false. Either branch may be empty.

#### Scenario: Passing branch executes

- **WHEN** a stat_check step evaluates its condition as true
- **THEN** the `on_pass` steps execute and the pipeline continues after the stat_check

#### Scenario: Failing branch executes

- **WHEN** a stat_check step evaluates its condition as false
- **THEN** the `on_fail` steps execute and the pipeline continues after the stat_check

---

### Requirement: Pipeline accepts an optional PersistCallback

`AdventurePipeline.__init__` SHALL accept an `on_state_change: PersistCallback | None = None` parameter. When `None`, no persistence calls are made and the pipeline behaves identically to its pre-persistence behaviour. The `PersistCallback` protocol SHALL be defined in `oscilla/engine/pipeline.py` as:

```python
class PersistCallback(Protocol):
    async def __call__(
        self,
        state: CharacterState,
        event: Literal["step_start", "combat_round", "adventure_end"],
    ) -> None: ...
```

#### Scenario: Pipeline with no callback is unchanged

- **WHEN** `AdventurePipeline` is constructed without `on_state_change`
- **THEN** the pipeline runs to completion without error and no persistence calls are attempted

#### Scenario: Pipeline with callback receives correct events

- **WHEN** `AdventurePipeline` is constructed with a `PersistCallback` and a two-step adventure (narrative, combat) is run
- **THEN** the callback is called with `event="step_start"` before each step and `event="combat_round"` after each combat round and `event="adventure_end"` once after the outcome is resolved

---

### Requirement: Pipeline calls PersistCallback with step_start before each step dispatch

Before dispatching any step handler, the pipeline SHALL call `on_state_change(state, "step_start")` if a callback is registered. This checkpoint captures the current `AdventurePosition.step_index` before the step mutates the character state.

#### Scenario: step_start fires before narrative step

- **WHEN** a narrative step begins
- **THEN** `on_state_change(state, "step_start")` is awaited before `show_text()` is called

---

### Requirement: Pipeline calls PersistCallback with combat_round after each combat round

After each combat round resolution (both character and enemy actions complete), the pipeline SHALL call `on_state_change(state, "combat_round")`. This checkpoint captures the current `step_state` (enemy HP) so a crash mid-combat can be resumed from the last round.

#### Scenario: combat_round fires after each round

- **WHEN** a combat step runs for three rounds before the character wins
- **THEN** `on_state_change(state, "combat_round")` is called three times

---

### Requirement: Pipeline calls PersistCallback with adventure_end after effects are applied

After the adventure outcome is determined and all outcome effects (XP, items, milestones) have been applied to the character, the pipeline SHALL call `on_state_change(state, "adventure_end")`. At this point, `active_adventure` SHALL be set to `None` on the character state before the callback fires.

#### Scenario: adventure_end fires after effects, before returning to caller

- **WHEN** an adventure completes with the COMPLETED outcome
- **THEN** all effects are applied to the character, `active_adventure` is set to None, and `on_state_change(state, "adventure_end")` is awaited before `run()` returns

---

### Requirement: SkillGrantEffect in the effect union

The effect union (used in adventure steps, item use_effects, and skill use_effects) SHALL include a `skill_grant` effect type. It SHALL have a `skill` field (string, required) naming the Skill manifest to teach. When dispatched by `run_effect()`, it SHALL call `player.grant_skill(skill_ref, registry)`.

#### Scenario: skill_grant effect in adventure step

- **WHEN** an adventure step's effects list includes `{type: skill_grant, skill: fireball}`
- **THEN** after the step runs, `"fireball"` is in `player.known_skills`

#### Scenario: skill_grant with unknown skill ref is rejected at load time

- **WHEN** an adventure manifest includes `{type: skill_grant, skill: nonexistent}` in a step's effects
- **THEN** the content loader raises a validation error

---

### Requirement: DispelEffect and ApplyBuffEffect in the effect union

The effect union SHALL include a `dispel` effect type with a `label: str` field (required, `min_length=1`) and a `target: Literal["player", "enemy"]` field (default `"player"`). When dispatched by `run_effect()` with a `CombatContext`, it SHALL remove all `ActiveCombatEffect` entries from `CombatContext.active_effects` where both `ae.label == label` and `ae.target == target`. When `combat` is `None`, it SHALL be silently skipped.

The effect union SHALL include an `apply_buff` effect type with a `buff_ref: str` field, a `target: Literal["player", "enemy"]` field (default `"player"`), and a `variables: Dict[str, int]` field (default `{}`). `BuffSpec` does NOT carry a `target` field — the target is determined at use time by the `ApplyBuffEffect.target` field, allowing the same buff manifest to be applied to either participant. When dispatched by `run_effect()` with a `CombatContext`, the engine SHALL:

1. Look up the buff in `registry.buffs`.
2. Merge `buff_spec.variables` (defaults) with `effect.variables` (overrides) into `resolved_vars`.
3. For each modifier in `spec.modifiers`, resolve `percent`: if `int`, use directly; if `str`, look up in `resolved_vars`.
4. Construct an `ActiveCombatEffect` with `label=buff_manifest.metadata.name`, `target=effect.target`, and resolved modifier copies, then append it to `combat.active_effects`.

When `combat` is `None`, it SHALL log a WARNING and skip. An unknown `buff_ref` SHALL log an ERROR and skip without crashing.

#### Scenario: dispel dispels a labelled active effect

- **WHEN** `CombatContext.active_effects` contains an `ActiveCombatEffect` with `label="on-fire"` and `target="player"`, and a `dispel` effect with `label="on-fire"` and `target="player"` is dispatched
- **THEN** `CombatContext.active_effects` no longer contains any entry with `label="on-fire"` and `target="player"`

#### Scenario: dispel with no match is a no-op

- **WHEN** a `dispel` effect is dispatched and no active effects match the label
- **THEN** no error is raised and `active_effects` is unchanged

#### Scenario: dispel outside combat is silently skipped

- **WHEN** a `dispel` effect is dispatched with `combat=None`
- **THEN** no error is raised (valid for items used outside combat)

---

### Requirement: Effect dispatcher routes effects to handlers

The effect dispatcher function `run_effect()` SHALL accept all existing parameters plus an optional `combat: CombatContext | None = None` parameter (default None, backward-compatible with all existing call sites).

When `combat` is None and an effect's `target` field is `"enemy"`, the dispatcher SHALL log a WARNING and skip the effect rather than raising an error. This preserves forward-compatibility with content that declares enemy-targeting effects in non-combat contexts.

All existing call sites that do not pass `combat` remain valid and require no updates.

#### Scenario: Existing adventure step effects work without combat parameter

- **WHEN** a stat_change effect runs in a narrative adventure step (no combat)
- **THEN** the effect is dispatched normally without error

#### Scenario: Enemy-targeting effect outside combat is skipped with warning

- **WHEN** a `stat_change` effect with `target: "enemy"` is dispatched with `combat=None`
- **THEN** the effect is skipped, a WARNING is logged, and no other state changes occur

#### Scenario: Enemy-targeting effect inside combat applies to enemy_hp

- **WHEN** a `stat_change` effect with `target: "enemy"` and `amount: -10` is dispatched with a CombatContext where `enemy_hp == 50`
- **THEN** `CombatContext.enemy_hp == 40` after the dispatch

---

### Requirement: target field on StatChangeEffect, StatSetEffect, and HealEffect

`StatChangeEffect` and `HealEffect` SHALL accept a `target: Literal["player", "enemy"]` field (default `"player"`). When `target == "player"`, behavior is identical to the current implementation. When `target == "enemy"`, the effect is routed through `CombatContext.enemy_hp`.

`StatSetEffect` SHALL accept `target: Literal["player"]` only. Declaring `target: "enemy"` on a `stat_set` effect is a load-time validation error.

All existing manifests that omit `target` default to `"player"` and require no changes.

#### Scenario: stat_change with target player is unchanged

- **WHEN** a `stat_change` effect without a `target` field fires
- **THEN** the named stat on the player is modified as before

#### Scenario: heal with target player is unchanged

- **WHEN** a `heal` effect without a `target` field fires
- **THEN** the player's HP is restored as before

#### Scenario: stat_set with target enemy is rejected at load time

- **WHEN** a manifest declares `{type: stat_set, stat: strength, value: 10, target: enemy}`
- **THEN** the content loader raises a validation error

---

### Requirement: AdventurePipeline constructs ExpressionContext before executing steps

Before executing any step, `AdventurePipeline` SHALL construct an `ExpressionContext` from the current `CharacterState`. The context SHALL be passed to all step handlers and to `_run_effects()`. The context SHALL be reconstructed whenever player state changes between steps so that templates always see current values.

#### Scenario: Context is fresh when a step runs after a stat change

- **WHEN** step N applies a `stat_change` and step N+1 contains `{{ player.stats['gold'] }}`
- **THEN** step N+1's template sees the updated gold value, not the pre-step-N value

---

### Requirement: NarrativeStep text field supports template strings

When a `NarrativeStep.text` is a template string (contains `{{`, `{%`, or a pronoun placeholder), the pipeline SHALL render it through the `GameTemplateEngine` before passing to the TUI. Plain strings SHALL be passed directly without engine overhead.

#### Scenario: Template text is rendered before display

- **WHEN** a `NarrativeStep` has `text: "Welcome, {{ player.name }}."` and the player's name is `"Jordan"`
- **THEN** the TUI receives the string `"Welcome, Jordan."` — not the raw template

#### Scenario: Plain text is not modified

- **WHEN** a `NarrativeStep` has `text: "You enter the tavern."` (no template syntax)
- **THEN** the TUI receives exactly `"You enter the tavern."`

---

### Requirement: Effect numeric fields accept template strings that resolve to integers

`xp_grant.amount`, `stat_change.amount`, and `item_drop.count` SHALL accept either a literal integer or a template string. When the field is a template string, the effect dispatcher SHALL render it through `GameTemplateEngine.render_int()` before applying the effect. The rendered value MUST be a non-fractional integer; a render result that cannot be parsed as `int` SHALL raise a `TemplateRuntimeError`.

#### Scenario: Template amount renders to correct integer

- **WHEN** `xp_grant { amount: "{{ player.level * 50 }}" }` is applied for a level-3 player
- **THEN** the player gains 150 XP

#### Scenario: Non-integer template amount raises TemplateRuntimeError

- **WHEN** a template `amount` resolves to `"fifteen"` at runtime
- **THEN** a `TemplateRuntimeError` is raised with the resolved value and template ID in the message

#### Scenario: roll() in amount produces value in expected range

- **WHEN** `stat_change { stat: gold, amount: "{{ roll(5, 15) }}" }` is applied
- **THEN** `gold` increases by an integer between 5 and 15 inclusive
