# Tasks: Content Authoring Expressiveness

## 1. Passive Event Step

- [x] **1.1** Add `PassiveStep` model to `oscilla/engine/models/adventure.py`:
  - Fields: `type: Literal["passive"]`, `label: str | None = None`, `text: str | None`, `effects: List[Effect] = []`, `bypass: Condition | None = None`, `bypass_text: str | None = None`
  - Add to `Step` union
  - _Acceptance: `PassiveStep(type="passive", effects=[])` validates; `PassiveStep` with all optional fields omitted validates_

- [x] **1.2** Create `oscilla/engine/steps/passive.py` with `run_passive()` handler:
  - Evaluate bypass condition if present; show `bypass_text` if set and bypass fires; return COMPLETED
  - Show `text` if present and not bypassed; apply all effects via `run_effect()`; return COMPLETED
  - _Acceptance: bypass fires → effects skipped; bypass absent → effects applied_

- [x] **1.3** Register `PassiveStep` in `oscilla/engine/pipeline.py` step dispatch (`_run_step`)
  - _Acceptance: adventure with a passive step executes without raising `NotImplementedError`_

- [x] **1.4** Write tests in `tests/engine/test_passive_step.py`:
  - `run_passive` with no bypass applies effects
  - `run_passive` with bypass condition True skips effects, shows `bypass_text`
  - `run_passive` with bypass condition True and no `bypass_text` — silent skip
  - `run_passive` with bypass condition False applies effects normally
  - `run_passive` with no text applies effects silently (no TUI show_text call)
  - _See design.md for function signatures_

- [x] **1.5** Update `docs/authors/adventures.md`: add "Passive Steps" section with text, effects, bypass, bypass_text fields and two worked examples (trap with bypass, healing shrine)

- [x] **1.6** Add testlandia QA adventure `content/testlandia/adventures/test-passive-trap.yaml`:
  - Two passive steps: dart trap (-10 HP, bypass on dexterity ≥ 12, bypass_text "Your reflexes save you.") and healing spring (+15 HP, no bypass)

- [x] **1.7** Run `make tests` — confirm all checks pass

---

## 2. Adventure Repeat Controls

- [x] **2.1** Add repeat control fields to `AdventureSpec` in `oscilla/engine/models/adventure.py`:
  - `repeatable: bool = True`, `max_completions: int | None = None`, `cooldown_days: int | None = None`, `cooldown_adventures: int | None = None`
  - Add `model_validator` that raises `ValueError` if both `repeatable: false` and `max_completions` are set
  - _Acceptance: both fields set → `ValidationError`; each alone validates_

- [x] **2.2** Add new fields to `CharacterState` in `oscilla/engine/character.py`:
  - `adventure_last_completed_on: Dict[str, str] = field(default_factory=dict)`
  - `adventure_last_completed_at_total: Dict[str, int] = field(default_factory=dict)`
  - Add to `to_dict()` and restore in `from_dict()` with empty-dict defaults

- [x] **2.3** Add `is_adventure_eligible(adventure_ref, spec, today)` method to `CharacterState`:
  - Check `repeatable: false` (equivalent to max_completions=1 check using `statistics.adventures_completed`)
  - Check `max_completions` hard cap
  - Check `cooldown_days` against `adventure_last_completed_on[ref]`
  - Check `cooldown_adventures` against `adventure_last_completed_at_total[ref]`
  - _Acceptance: see design.md for full logic; each constraint independently gate-keeps_

- [x] **2.4** Update adventure pool filtering in `oscilla/engine/tui.py`:
  - After `evaluate(entry.requires, ...)`, also call `player.is_adventure_eligible(entry.ref, spec, date.today())`
  - _Acceptance: one-shot adventure disappears from pool after first completion_

- [x] **2.5** Update `oscilla/engine/session.run_adventure()` to record completion state after pipeline finishes:
  - Set `player.adventure_last_completed_on[ref] = date.today().isoformat()`
  - Set `player.adventure_last_completed_at_total[ref] = sum(statistics.adventures_completed.values())`

- [x] **2.6** Create DB migration with `make create_migration MESSAGE="add adventure repeat controls state"`:
  - Add `character_iteration_adventure_state` table: `(iteration_id UUID FK, adventure_ref VARCHAR, last_completed_on DATE, last_completed_at_total INT, PRIMARY KEY (iteration_id, adventure_ref))`

- [x] **2.7** Add `upsert_adventure_state()` service function to `oscilla/services/character.py`
  - Add new `CharacterIterationAdventureState` SQLAlchemy model to `oscilla/models/`
  - _Acceptance: upsert creates row on first call, updates on subsequent calls_

- [x] **2.8** Update `session.sync()` to persist `adventure_last_completed_on` and `adventure_last_completed_at_total`

- [x] **2.9** Update character load (`_restore_character` or equivalent) to read `character_iteration_adventure_state` rows back into `CharacterState`

- [x] **2.10** Write tests in `tests/engine/test_adventure_repeat.py`:
  - `is_adventure_eligible`: `repeatable: false` hides after 1 completion
  - `is_adventure_eligible`: `max_completions: 2` hides at exactly 2
  - `is_adventure_eligible`: `cooldown_days: 1` hides same-day, shows next day
  - `is_adventure_eligible`: `cooldown_adventures: 3` hides below threshold, shows at threshold
  - `is_adventure_eligible`: no constraints → always eligible
  - `is_adventure_eligible`: never-completed → no cooldown applies
  - Write integration test verifying state persists across `sync()` / reload

- [x] **2.11** Update `docs/authors/adventures.md`: add "Repeat Controls" section documenting all four fields, explain that cooldown_adventures uses total completions (not location-specific), note reset-on-prestige behavior

- [x] **2.12** Add testlandia QA adventures:
  - `content/testlandia/adventures/test-one-shot.yaml` with `repeatable: false`
  - `content/testlandia/adventures/test-cooldown.yaml` with `cooldown_adventures: 3`

- [x] **2.13** Run `make tests` — confirm all checks pass

---

## 3. Adventure Outcome Definitions

- [x] **3.1** Add `outcomes: List[str] = []` to `GameSpec` in `oscilla/engine/models/game.py`
  - _Acceptance: `GameSpec` without `outcomes` field loads without error_

- [x] **3.2** Change `EndAdventureEffect.outcome` from `Literal["completed", "defeated", "fled"]` to `str` with default `"completed"` in `oscilla/engine/models/adventure.py`
  - _Acceptance: `EndAdventureEffect(type="end_adventure", outcome="custom")` validates_

- [x] **3.3** Add `_validate_outcome_refs()` to `oscilla/engine/loader.py`:
  - Collect `_BUILTIN_OUTCOMES = {"completed", "defeated", "fled"}`
  - Scan every `EndAdventureEffect` across all loaded adventures
  - If `outcome` not in `_BUILTIN_OUTCOMES`, verify it is in `registry.game.spec.outcomes`
  - Produce a `LoadError` for any undeclared outcome
  - Call at the end of `validate_references()`

- [x] **3.4** Add `adventure_outcome_counts: Dict[str, Dict[str, int]]` to `CharacterStatistics`:
  - Add `record_adventure_outcome(adventure_ref, outcome)` method
  - Include in `to_dict()` and `from_dict()` in `CharacterState`

- [x] **3.5** Update `session.run_adventure()` to call `player.statistics.record_adventure_outcome(adventure_ref, outcome.value)` after each completion

- [x] **3.6** Widen `stat_type` parameter type in `increment_statistic()` in `oscilla/services/character.py` from `Literal[...]` to `str`
  - Update SQLAlchemy model annotation if needed (it is already VARCHAR in DB, no migration needed)

- [x] **3.7** Update `session.sync()` to persist `adventure_outcome_counts` using `increment_statistic()` with `stat_type = f"adventure_outcome:{outcome_name}"`

- [x] **3.8** Update character load to reconstruct `adventure_outcome_counts` from statistics rows where `stat_type.startswith("adventure_outcome:")`

- [x] **3.9** Write tests in `tests/engine/test_adventure_outcomes.py`:
  - Loader accepts built-in outcomes without game.yaml declaration
  - Loader accepts custom outcome declared in game.yaml
  - Loader raises LoadError for undeclared custom outcome
  - `record_adventure_outcome` increments correctly per outcome
  - Multiple outcomes tracked independently for same adventure

- [x] **3.10** Add `outcomes: [completed, fled, discovered]` to `content/testlandia/game.yaml`

- [x] **3.11** Add testlandia QA adventure `content/testlandia/adventures/test-custom-outcome.yaml` with a choice step where one option fires `end_adventure: {outcome: discovered}`

- [x] **3.12** Update `docs/authors/adventures.md`: add "Outcome Definitions" section explaining `game.yaml` declarations, built-in names, custom names, and per-outcome tracking (mention `adventure_outcome_counts` is exposable via conditions in a future change)

- [x] **3.13** Run `make tests` — confirm all checks pass

---

## 4. Quest Stage Condition

- [x] **4.1** Add `QuestStageCondition` to `oscilla/engine/models/base.py`:
  - Fields: `type: Literal["quest_stage"]`, `quest: str`, `stage: str`
  - Add to `Condition` union
  - _Acceptance: `QuestStageCondition(type="quest_stage", quest="x", stage="y")` validates_

- [x] **4.2** Add `case QuestStageCondition(quest=q, stage=s)` handler to `oscilla/engine/conditions.py`:
  - Return `player.active_quests.get(q) == s`

- [x] **4.3** Add `quest_stage` condition cross-reference validation to `oscilla/engine/loader.py`:
  - Scan all `QuestStageCondition` instances across all manifests
  - Verify `quest` ref exists in `registry.quests`
  - Verify `stage` matches one of the quest's declared stage names
  - Produce `LoadError` for each invalid reference
  - Call from `validate_references()`

- [x] **4.4** Write tests in `tests/engine/test_quest_stage_condition.py`:
  - Condition is true when quest active at matching stage
  - Condition is false when quest active at different stage
  - Condition is false when quest not active (not in `active_quests`)
  - Condition is false when quest in `completed_quests`
  - Loader raises LoadError for unknown quest ref in condition
  - Loader raises LoadError for unknown stage name in condition

- [x] **4.5** Add testlandia QA fixtures:
  - `content/testlandia/quests/test-stage-condition-quest.yaml`: two stages (`searching` → `complete` terminal), advancing on `test-stage-condition-done`
  - `content/testlandia/adventures/test-stage-gate.yaml`: gated by `quest_stage: {quest: test-stage-condition-quest, stage: searching}`

- [x] **4.6** Update `docs/authors/quests.md`: add "Quest Stage Condition" section with syntax, worked example, and note about false-when-not-active behavior

- [x] **4.7** Run `make tests` — confirm all checks pass

---

## 5. Quest Failure States

- [x] **5.1** Add `fail_condition: Condition | None = None` and `fail_effects: List[Effect] = []` to `QuestStage` in `oscilla/engine/models/quest.py`:
  - Update `model_rebuild()` call to include `Condition` reference
  - Update `validate_stage_graph` to reject `fail_condition` on terminal stages
  - _Acceptance: terminal stage with `fail_condition` raises `ValueError`; non-terminal stage accepts it_

- [x] **5.2** Add `QuestFailEffect` to `oscilla/engine/models/adventure.py`:
  - Fields: `type: Literal["quest_fail"]`, `quest_ref: str`
  - Add to `Effect` union
  - _Acceptance: `QuestFailEffect(type="quest_fail", quest_ref="x")` validates_

- [x] **5.3** Add `failed_quests: Set[str] = field(default_factory=set)` to `CharacterState` in `oscilla/engine/character.py`:
  - Add to `to_dict()` (serialized as sorted list)
  - Restore in `from_dict()` with empty-set default

- [x] **5.4** Add `_evaluate_quest_failures()` async function to `oscilla/engine/quest_engine.py`:
  - For each active quest with a non-None `fail_condition`, evaluate using `evaluate()`
  - If satisfied: pop from `active_quests`, add to `failed_quests`, show TUI message, run `fail_effects`
  - Call at the end of `evaluate_quest_advancements()` — AFTER the advancement loop

- [x] **5.5** Add silent failure correction to `_advance_quests_silent()` in `oscilla/engine/quest_engine.py`:
  - After advancement walk, evaluate `fail_condition` for remaining active quests
  - If satisfied: move to `failed_quests` WITHOUT running `fail_effects`

- [x] **5.6** Add `QuestFailEffect` handler to `oscilla/engine/steps/effects.py`:
  - Unknown ref → log error + TUI error message, return
  - Quest not active → log warning, return
  - Active → pop from `active_quests`, add to `failed_quests`, show TUI message, run `fail_effects`
  - _See design.md for full implementation_

- [x] **5.7** Update `set_quest()` in `oscilla/services/character.py`:
  - Change `status` parameter type from `Literal["active", "completed"]` to `Literal["active", "completed", "failed"]`
  - Update query in character load to include `status == "failed"` rows, populating `failed_quests`

- [x] **5.8** Update `session.sync()` to persist `failed_quests` via `set_quest(..., status="failed")`, mirroring the `completed_quests` pass

- [x] **5.9** Write tests in `tests/engine/test_quest_failure.py`:
  - `_evaluate_quest_failures`: fail_condition met → quest in `failed_quests`, fail_effects run
  - `_evaluate_quest_failures`: fail_condition not met → no change
  - `_advance_quests_silent`: fail_condition met → quest in `failed_quests`, no effects run
  - `QuestFailEffect` handler: unknown ref → error, no state change
  - `QuestFailEffect` handler: not active → warning, no state change
  - `QuestFailEffect` handler: active → moved to `failed_quests`, fail_effects run
  - `terminal: true` with `fail_condition` → load-time `ValueError`
  - Integration test: `failed_quests` persists across `sync()` / reload

- [x] **5.10** Add testlandia QA fixtures:
  - `content/testlandia/quests/test-failable-quest.yaml`: stage `active` with `fail_condition: {type: milestone, name: test-quest-fail-trigger}` and `fail_effects: [{type: stat_change, stat: hp, amount: -5}]`
  - `content/testlandia/adventures/test-fail-quest.yaml`: grants `test-quest-fail-trigger` milestone

- [x] **5.11** Update `docs/authors/quests.md`:
  - Add "Quest Failure" section: `fail_condition`, `fail_effects`, `failed_quests`, `quest_fail` effect
  - Document model validator constraint (no `fail_condition` on terminal stages)
  - Worked example: failable hostage-rescue quest

- [x] **5.12** Run `make tests` — confirm all checks pass

---

## 6. Documentation

- [x] **6.1** Review `docs/authors/adventures.md` for consistency: passive step, repeat controls, and outcome definitions sections should use consistent YAML example style

- [x] **6.2** Review `docs/authors/quests.md` for consistency: quest stage condition and quest failure sections should be coherent with existing quest content

- [x] **6.3** Check `docs/dev/game-engine.md` to see if any engine diagrams or lists should be updated to reflect new step types, condition types, or effect types

---

## 7. Roadmap Cleanup

- [x] **7.1** Remove "Named Random Tables" from `ROADMAP.md` (already implemented in tech-debt-q1)
- [x] **7.2** Remove "Enemy Loot Table Reference in on_win" from `ROADMAP.md` (already implemented)
- [x] **7.3** Remove "Quest Activation Engine" from `ROADMAP.md` (already implemented in tech-debt-q1)
- [x] **7.4** Remove "Passive Event Step", "Adventure Repeat Controls", "Adventure Outcome Definitions", "Quest Stage Condition", "Quest Failure States" from `ROADMAP.md` when this change is complete
