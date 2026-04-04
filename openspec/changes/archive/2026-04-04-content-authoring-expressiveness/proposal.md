## Why

Content authors are blocked on five common gameplay patterns that have no direct expression in the current authoring language. Passive environmental effects require fake combat steps, one-shot adventures have no enforcement mechanism, quest state can't be queried by condition, and quests can never fail. Each gap is small in isolation, but together they force authors into workarounds that make manifests harder to read and maintain. These five roadmap items — all rated **S** — share a single coherent theme (author expressiveness) and touch cleanly separated areas of the engine, making them a natural fit for a single change.

## What Changes

- **Passive Event Step**: A new `type: passive` step applies effects automatically with no player input. An optional `bypass` condition lets a character skip the step entirely, and an optional `bypass_text` is shown when the bypass fires. Authors use this for traps, environmental hazards, automatic rewards, and healing shrines without needing the workaround of a fake single-option combat or choice step.

- **Adventure Repeat Controls**: New fields on the adventure manifest control whether and how often an adventure may be run: `repeatable: false` (one-shot), `max_completions: int` (hard cap), `cooldown_days: int` (calendar-day cooldown), and `cooldown_adventures: int` (cooldown measured in total adventures completed). Tracking is per character iteration and resets on prestige. When all adventures at a location become ineligible, the existing no-eligible-adventure fallback applies unchanged.

- **Adventure Outcome Definitions**: `game.yaml` can declare a custom set of outcome names beyond the three engine-internal defaults (`completed`, `defeated`, `fled`). Custom outcomes are usable in `end_adventure` effects. The engine continues to emit `completed`, `defeated`, and `fled` from combat, stat-check, and choice steps — these three are always implicitly valid. Per-adventure, per-outcome completion counts are added to player state and persisted to the database, enabling conditions that branch based on how an adventure previously resolved.

- **Quest Stage Condition**: A new `type: quest_stage` condition evaluates to true when a named quest is active and currently at a specific named stage. This gives authors direct, explicit control over adventure and narrative gating without relying on milestone proxies.

- **Quest Failure States**: Quest stages can declare an optional `fail_condition` (a standard condition) and `fail_effects` list. When a milestone is granted, the quest engine evaluates active quest failure conditions in addition to advancement conditions. Failed quests are added to a new `failed_quests` set on player state, mirroring `completed_quests`. A `quest_fail` effect is also added so adventures can manually fail a quest without a milestone trigger.

## Capabilities

### New Capabilities

- `passive-step`: A new adventure step type that applies effects automatically with optional bypass condition and bypass text.
- `adventure-repeat-controls`: Per-adventure controls for one-shot behavior, hard completion caps, and calendar-day or adventure-count cooldowns.
- `adventure-outcome-definitions`: Custom outcome names in `game.yaml`, usable in `end_adventure` effects, with per-adventure per-outcome count tracking in player state.
- `quest-stage-condition`: A condition type that checks the current stage of an active quest.
- `quest-failure-states`: Fail conditions on quest stages, `fail_effects` list, `failed_quests` player state set, and `quest_fail` effect.

### Modified Capabilities

- `adventure-pipeline`: Extended to support the new `passive` step type.
- `quest-engine`: Extended to evaluate failure conditions on milestone grant and to handle `quest_fail` effects.
- `condition-evaluator`: Extended with the new `quest_stage` condition type.

## Impact

- `oscilla/engine/models/adventure.py`: Add `PassiveStep` model; add repeat control fields to `AdventureSpec`; change `EndAdventureEffect.outcome` from `Literal[...]` to `str`; add `QuestFailEffect` model; update `Step` union.
- `oscilla/engine/models/game.py`: Add `outcomes: List[str]` field to `GameSpec` for declaring custom outcome names.
- `oscilla/engine/models/base.py`: Add `QuestStageCondition` to the `Condition` union.
- `oscilla/engine/models/quest.py`: Add `fail_condition: Condition | None` and `fail_effects: List[Effect]` to `QuestStage`.
- `oscilla/engine/character.py`: Add `failed_quests: Set[str]`, `adventure_completion_counts: Dict[str, int]`, `adventure_outcome_counts: Dict[str, Dict[str, int]]`, `adventure_last_completed_day: Dict[str, str]` (ISO date), `adventure_last_completed_total: Dict[str, int]`.
- `oscilla/engine/conditions.py`: Implement `QuestStageCondition` handler.
- `oscilla/engine/pipeline.py`: Update `AdventureOutcome` to include validation against `game.yaml` outcomes at load time; add outcome count recording in `run_adventure`.
- `oscilla/engine/steps/effects.py`: Add `PassiveStep` handler; add `QuestFailEffect` handler.
- `oscilla/engine/steps/passive.py`: New file — `run_passive()` step handler.
- `oscilla/engine/quest_engine.py`: Add failure evaluation pass after advancement in `evaluate_quest_advancements`.
- `oscilla/engine/loader.py`: Validate `end_adventure` outcome strings against game.yaml + built-ins; validate `quest_stage` condition refs.
- `oscilla/engine/session.py`: Persist `failed_quests`, `adventure_completion_counts`, `adventure_outcome_counts`, `adventure_last_completed_day`, `adventure_last_completed_total`.
- `db/versions/`: New migration for `failed_quests`, per-adventure outcome counts, and repeat control state.
- `docs/authors/adventures.md`: Document passive step, repeat controls, and outcome definitions.
- `docs/authors/quests.md`: Document quest failure states and quest stage condition.
- `tests/engine/`: New test files for each feature area.

### Testlandia QA Content

**Passive Step:**

- A new adventure `testlandia/adventures/test-passive-trap.yaml` with two passive steps: a dart trap step (deals -10 HP) and a healing spring step (+15 HP). The trap step declares a `bypass` condition on `dexterity >= 12` and a `bypass_text` saying "Your reflexes save you." Manual QA: character with dexterity ≥ 12 skips the trap text; character without does not.

**Repeat Controls:**

- A new adventure `testlandia/adventures/test-one-shot.yaml` with `repeatable: false`. Manual QA: adventure appears once; after completion it does not appear again.
- A new adventure `testlandia/adventures/test-cooldown.yaml` with `cooldown_adventures: 3`. Manual QA: adventure disappears after completion and reappears after 3 more adventures are run.

**Adventure Outcome Definitions:**

- Add `outcomes: [completed, fled, discovered]` to `testlandia/game.yaml`.
- A new adventure `testlandia/adventures/test-custom-outcome.yaml` with a choice step where one option fires `end_adventure: discovered`. Manual QA: adventure count bookkeeping shows the `discovered` outcome tracked separately.

**Quest Stage Condition:**

- A new quest `testlandia/quests/test-stage-condition-quest.yaml` with two stages: `searching` (advances on `test-item-found`) and `complete` (terminal).
- A new adventure `testlandia/adventures/test-stage-gate.yaml` gated by `type: quest_stage`, `quest: test-stage-condition-quest`, `stage: searching`. Manual QA: the adventure only appears when the quest is active in the `searching` stage.

**Quest Failure States:**

- A new quest `testlandia/quests/test-failable-quest.yaml` with a stage `active` that has `fail_condition: {type: milestone, name: test-quest-failed-trigger}` and `fail_effects: [{type: stat_change, stat: hp, amount: -5}]`.
- A new adventure `testlandia/adventures/test-fail-quest.yaml` that grants `test-quest-failed-trigger`. Manual QA: granting the milestone fails the quest, applies the penalty, and the quest appears in `failed_quests`, not `active_quests`.
