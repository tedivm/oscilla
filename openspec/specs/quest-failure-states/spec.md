# Quest Failure States

## Purpose

Defines how quests can fail — via declarative `fail_condition` on stage manifests, via the explicit `quest_fail` effect, and how failed quest state is persisted and restored across sessions.

## Requirements

### Requirement: Quest stages can declare a fail condition

A `QuestStage` MAY declare a `fail_condition: Condition` field. When a milestone is granted at runtime, after the advancement pass completes, the engine SHALL evaluate `fail_condition` for every active quest stage that declares one. If the condition is satisfied, the quest is failed: it is removed from `active_quests`, added to `failed_quests`, and `fail_effects` are executed. The TUI SHALL display "Quest failed: <displayName>" before executing fail effects. A Pydantic model validator SHALL reject `fail_condition` on terminal stages (they are already resolved).

#### Scenario: fail_condition met after milestone grant — quest fails

- **WHEN** a milestone is granted, an active quest's current stage has `fail_condition: {type: milestone, name: "enemy-slew-hostage"}`, and that milestone is now held
- **THEN** the quest is removed from `active_quests`, added to `failed_quests`, and the TUI shows "Quest failed: <displayName>"

#### Scenario: fail_condition not met — quest continues

- **WHEN** a milestone is granted and the active quest's fail_condition evaluates to false
- **THEN** no failure occurs; the quest remains in `active_quests` at its current stage

#### Scenario: fail_condition on terminal stage is a load error

- **WHEN** a `QuestStage` with `terminal: true` declares a `fail_condition`
- **THEN** the content loader raises a validation error

---

### Requirement: Failing a quest runs fail_effects

A `QuestStage` MAY declare a `fail_effects: List[Effect]` list. When a quest fails (either via `fail_condition` or via the `quest_fail` effect), every effect in `fail_effects` for the current stage SHALL be dispatched through `run_effect()`. These effects execute after the quest state has been updated (removed from `active_quests`, added to `failed_quests`).

#### Scenario: Fail effects execute on failure

- **WHEN** a quest fails and its current stage has `fail_effects: [{type: stat_change, stat: hp, amount: -5}]`
- **THEN** the player's HP is reduced by 5

#### Scenario: No fail_effects — clean failure with no side effects

- **WHEN** a quest fails and its current stage has no `fail_effects`
- **THEN** the quest is moved to `failed_quests` without any additional effects

---

### Requirement: quest_fail effect manually fails a quest

A `quest_fail` effect type SHALL exist as a member of the `Effect` discriminated union. When applied, it SHALL fail the named quest by removing it from `active_quests`, adding it to `failed_quests`, running the current stage's `fail_effects`, and showing the TUI failure message. If the quest is not active, a warning is logged and no state change occurs. If the quest ref is unknown, an error is logged and a TUI error message is shown.

#### Scenario: quest_fail on an active quest fails it

- **WHEN** a `quest_fail` effect with `quest_ref: "find-artifact"` is applied and the quest is active
- **THEN** the quest is moved to `failed_quests`, `fail_effects` run, and the TUI shows "Quest failed: Find Artifact"

#### Scenario: quest_fail on an inactive quest is a no-op

- **WHEN** a `quest_fail` effect references a quest that is not in `active_quests`
- **THEN** a warning is logged and no state change occurs

#### Scenario: quest_fail with unknown ref shows error

- **WHEN** a `quest_fail` effect references a quest not in the registry
- **THEN** an error is logged and the TUI displays an error message; no state change occurs

---

### Requirement: failed_quests state persists across sessions

A new `failed_quests: Set[str]` field SHALL exist on `CharacterState` alongside `completed_quests`. Failed quests SHALL be persisted using `status: "failed"` in the existing `character_iteration_quests` table and restored on character load. The existing `set_quest()` service function SHALL accept `"failed"` as a valid status value.

#### Scenario: failed_quests persists across session restart

- **WHEN** a quest is failed during a session and the session ends
- **THEN** on next load, the quest appears in `failed_quests` and not in `active_quests`

#### Scenario: Failure evaluation on load

- **WHEN** a character is loaded and a quest's `fail_condition` is already satisfied
- **THEN** the silent load-time pass does NOT run fail effects (only state correction — moving to failed_quests — is performed silently)
