## ADDED Requirements

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
