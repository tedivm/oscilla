# Quest Stage Condition

## Purpose

Defines the `quest_stage` condition leaf predicate, which allows content to gate choices, steps, and adventure eligibility on whether a specific quest is active at a specific stage.

## Requirements

### Requirement: quest_stage condition evaluates quest and stage

A `quest_stage` condition type SHALL exist as a member of the `Condition` discriminated union. It SHALL evaluate to `true` when the named quest is present in `player.active_quests` AND the current stage exactly matches the declared `stage` value. If the quest is not active (absent from `active_quests`, present in `completed_quests`, or unknown), the condition evaluates to `false`.

#### Scenario: Quest active at matching stage — true

- **WHEN** a `quest_stage` condition with `quest: "find-artifact"` and `stage: "searching"` is evaluated for a player whose `active_quests["find-artifact"] == "searching"`
- **THEN** the condition evaluates to `true`

#### Scenario: Quest active at different stage — false

- **WHEN** a `quest_stage` condition with `quest: "find-artifact"` and `stage: "searching"` is evaluated for a player whose `active_quests["find-artifact"] == "returning"`
- **THEN** the condition evaluates to `false`

#### Scenario: Quest not active — false

- **WHEN** a `quest_stage` condition is evaluated for a player who does not have the quest in `active_quests`
- **THEN** the condition evaluates to `false` regardless of whether the quest is in `completed_quests` or `failed_quests`

---

### Requirement: quest_stage condition is validated at load time

The content loader SHALL validate that the `quest` field resolves to a known quest manifest and that the `stage` field matches one of the quest's declared stage names. Unknown quest refs and unknown stage names SHALL produce a `LoadError`.

#### Scenario: Unknown quest ref is a load error

- **WHEN** a `quest_stage` condition references a `quest` name not found in the registry
- **THEN** the content loader raises a `LoadError` identifying the manifest and condition

#### Scenario: Unknown stage name is a load error

- **WHEN** a `quest_stage` condition references a `stage` that does not appear in the quest's declared stages
- **THEN** the content loader raises a `LoadError` identifying the manifest, quest, and stage
