## ADDED Requirements

### Requirement: quest_stage condition type is supported

The condition evaluator SHALL support `type: quest_stage` conditions. The evaluator SHALL read `player.active_quests` dict and return `true` if and only if the quest is present and the current stage value equals the declared `stage` field. No registry access is required to evaluate this condition.
