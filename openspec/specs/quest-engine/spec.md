# Quest Engine

## Purpose

Defines the quest activation and progression mechanics: how quests are started, how stages advance based on granted milestones, and how terminal stages trigger completion effects.

---

## Requirements

### Requirement: Quest activation via effect

A `quest_activate` effect SHALL exist as a first-class member of the `Effect` discriminated union. When applied, it SHALL add the named quest to the player's `active_quests` at the quest's declared `entry_stage`. If the quest is already active or already completed, the effect SHALL be silently ignored (no-op, warning logged). If the quest ref does not resolve to a known manifest, the engine SHALL log an error and display a red error message via the TUI; no state change occurs.

#### Scenario: Quest activates successfully

- **WHEN** a `quest_activate` effect with a valid `quest_ref` is applied to a player who does not have that quest active or completed
- **THEN** the quest is added to `player.active_quests` with value equal to the quest's `entry_stage`, and the TUI shows "Quest started: <displayName>"

#### Scenario: Quest activate is idempotent when already active

- **WHEN** a `quest_activate` effect is applied to a player who already has that quest in `active_quests`
- **THEN** no state change occurs, a warning is logged, and no TUI message is shown

#### Scenario: Quest activate is idempotent when already completed

- **WHEN** a `quest_activate` effect is applied to a player who has that quest in `completed_quests`
- **THEN** no state change occurs, a warning is logged, and no TUI message is shown

#### Scenario: Quest activate with unknown ref

- **WHEN** a `quest_activate` effect references a `quest_ref` not found in the registry
- **THEN** no state change occurs, an error is logged, and the TUI displays a red error message

---

### Requirement: Milestone-driven stage advancement

When a milestone is granted to a player via `milestone_grant` at runtime, the engine SHALL immediately evaluate all active quests for stage advancement. A stage SHALL advance if at least one of its `advance_on` milestone names is present in the player's milestone set. Advancement SHALL follow the stage's `next_stage` pointer recursively — if the new stage is also immediately satisfiable (all its `advance_on` milestones are already held), it SHALL be advanced again in the same evaluation pass. This walk continues until either a stage with no satisfied `advance_on` milestones is reached or a terminal stage is reached.

#### Scenario: Stage advances on matching milestone

- **WHEN** a `milestone_grant` effect grants milestone `"m"` and a player has an active quest with current stage whose `advance_on` includes `"m"`
- **THEN** the quest's current stage is updated to the stage's `next_stage` pointer

#### Scenario: Multiple chained advancements in one pass

- **WHEN** a player's active quest is at stage A, stage A advances on milestone `"a"`, stage B advances on milestone `"b"`, and both `"a"` and `"b"` are now held after a single `milestone_grant`
- **THEN** the quest advances directly from A to B to the next stage in a single evaluation, not requiring a second milestone grant

#### Scenario: No advance_on match — no advancement

- **WHEN** a `milestone_grant` effect is applied and no active quest stage lists that milestone in `advance_on`
- **THEN** no quest stage changes occur

---

### Requirement: Terminal stage completion effects

Each `QuestStage` MAY declare a `completion_effects: List[Effect]`. This list SHALL only be valid on stages where `terminal: true` is set. The Pydantic model validator SHALL reject non-terminal stages that declare `completion_effects` with a `ValueError` at load time. When a quest reaches a terminal stage during runtime advancement, the engine SHALL execute every effect in `completion_effects` using the same `run_effect` dispatcher used by adventures, then mark the quest as completed by removing it from `active_quests` and adding it to `completed_quests`. The TUI SHALL show "Quest complete: <displayName>" before executing completion effects.

#### Scenario: Completion effects fire on terminal stage

- **WHEN** an active quest advances to its terminal stage
- **THEN** every effect in `completion_effects` is executed (item drops, milestone grants, stat changes, etc.), the quest is removed from `active_quests`, it is added to `completed_quests`, and the TUI displays the completion message

#### Scenario: completion_effects on non-terminal stage is a load error

- **WHEN** a Quest manifest declares `completion_effects` on a stage where `terminal: false`
- **THEN** Pydantic model validation raises a `ValueError` and the content loader reports a `LoadError`

---

### Requirement: Quest state re-evaluated on character load

When a character is restored from persisted state (loaded from the database), the engine SHALL silently re-evaluate all active quests against the player's current milestone set and advance any stages whose `advance_on` conditions are satisfied. This silent advancement SHALL NOT execute `completion_effects` — those are one-time rewards already reflected in the saved character data. This ensures quest state stays consistent across sessions even when milestones were granted before a quest was activated or when content was updated between sessions.

#### Scenario: Quest advances silently on load

- **WHEN** a character is loaded from the database and they have an active quest at stage A, and their milestone set contains a milestone listed in stage A's `advance_on`
- **THEN** the quest stage is advanced to `next_stage` before the session begins, without executing any `completion_effects` and without producing TUI output

#### Scenario: Already-current quest state is unchanged on load

- **WHEN** a character is loaded and their active quests are already at the correct stage for their milestone set
- **THEN** no quest state changes occur during load

---

### Requirement: Quest engine evaluates failure conditions after advancement

After the stage advancement pass completes in `evaluate_quest_advancements()`, the quest engine SHALL evaluate `fail_condition` for every remaining active quest stage that declares one. This failure pass runs regardless of whether any advancement occurred. Failure is an independent evaluation path from advancement.

#### Scenario: Failure and advancement in same milestone grant

- **WHEN** a milestone is granted that both advances quest A (to a new stage) and satisfies the fail_condition of quest B
- **THEN** quest A advances to its new stage AND quest B is failed; both happen in the same evaluation call

---

### Requirement: Silent load-time pass corrects failed quest state

The `_advance_quests_silent()` function (called at character load) SHALL also evaluate `fail_condition` for active quests. If a fail condition is satisfied, it SHALL move the quest to `failed_quests` WITHOUT running `fail_effects` — state correction only, no side effects.

#### Scenario: Quest with satisfied fail_condition is corrected on load

- **WHEN** a character is loaded and an active quest's `fail_condition` is already satisfied
- **THEN** the quest is moved to `failed_quests` without executing any fail_effects
