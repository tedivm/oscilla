## 1. Shared Cooldown Model

- [x] 1.1 Define `Cooldown` Pydantic model in `oscilla/engine/models/adventure.py` with fields `ticks`, `game_ticks`, `seconds`, `turns` (all `int | str | None`) and `scope: Literal["turn"] | None`
- [x] 1.2 Add `validate_scope_fields` model validator enforcing: scope="turn" → only `turns` allowed; no scope → `turns` must be None
- [x] 1.3 Add `at_least_one_constraint` model validator enforcing at least one field is non-None
- [x] 1.4 Remove `SkillCooldown` model from `oscilla/engine/models/skill.py`; update `SkillSpec.cooldown` to use `Cooldown`; add import of `Cooldown` from models.adventure
- [x] 1.5 Remove flat cooldown fields (`cooldown_days`, `cooldown_ticks`, `cooldown_game_ticks`, `cooldown_adventures`) and their validators from `AdventureSpec`; replace with `cooldown: Cooldown | None = None`
- [x] 1.6 Define `MilestoneRecord` Pydantic model in `oscilla/engine/models/base.py` (near `MilestoneCondition`) with fields `tick: int` and `timestamp: int`; add `Field` descriptions for each

## 2. Template Constants

- [x] 2.1 Define `SECONDS_PER_MINUTE`, `SECONDS_PER_HOUR`, `SECONDS_PER_DAY`, `SECONDS_PER_WEEK` as module-level constants in `oscilla/engine/templates.py`
- [x] 2.2 Add these constants to `SAFE_GLOBALS` dict in `templates.py`
- [x] 2.3 Verify `build_mock_context()` includes the constants (it already calls `ctx.update(SAFE_GLOBALS)` — confirm this is sufficient)

## 3. CharacterState Field Changes

- [x] 3.1 Change `milestones: Set[str]` to `milestones: Dict[str, MilestoneRecord]` in `CharacterState`; add import of `MilestoneRecord` from `oscilla.engine.models.base`; update `typing` imports — add `Dict`, remove `Set` if no longer needed elsewhere
- [x] 3.2 Remove `skill_cooldowns: Dict[str, int]` field from `CharacterState`; add `skill_tick_expiry: Dict[str, int]` and `skill_real_expiry: Dict[str, int]`
- [x] 3.3 Remove `adventure_last_completed_on: Dict[str, str]` field; add `adventure_last_completed_real_ts: Dict[str, int]`
- [x] 3.4 Add `adventure_last_completed_game_ticks: Dict[str, int]` field alongside existing `adventure_last_completed_at_ticks`
- [x] 3.5 Update `grant_milestone()` to store `MilestoneRecord(tick=self.internal_ticks, timestamp=int(time.time()))` instead of calling `self.milestones.add(name)`; add `import time` if not already present; guard with `if name not in self.milestones`
- [x] 3.6 Verify `has_milestone()` is unchanged — `return name in self.milestones` works for both Set and Dict
- [x] 3.7 Delete `tick_skill_cooldowns()` method entirely
- [x] 3.8 Update `to_dict()` to serialize new fields: `milestones` as `{name: {"tick": r.tick, "timestamp": r.timestamp} for name, r in self.milestones.items()}`, `skill_tick_expiry`, `skill_real_expiry`, `adventure_last_completed_real_ts`, `adventure_last_completed_game_ticks`; remove `skill_cooldowns`, `adventure_last_completed_on`
- [x] 3.9 Update `from_dict()`: (a) detect list-format milestones and migrate to `MilestoneRecord(tick=0, timestamp=0)` per entry with warning; (b) detect int-value dict milestones and migrate to `MilestoneRecord(tick=N, timestamp=0)` per entry with warning; (c) parse current nested-dict format directly; (d) detect and migrate `__game__` prefixed entries from `adventure_last_completed_at_ticks` to `adventure_last_completed_game_ticks`; (e) load `skill_tick_expiry` and `skill_real_expiry` with empty-dict defaults

## 4. Adventure Eligibility Check

- [x] 4.1 Update `is_adventure_eligible()` signature: replace `today: date` with `now_ts: int` and add `template_engine: GameTemplateEngine | None = None`
- [x] 4.2 Implement `_resolve(v)` helper inside `is_adventure_eligible()` to handle `int | str | None` cooldown fields by optionally rendering through template engine
- [x] 4.3 Implement `ticks` cooldown check against `adventure_last_completed_at_ticks`
- [x] 4.4 Implement `game_ticks` cooldown check against `adventure_last_completed_game_ticks`
- [x] 4.5 Implement `seconds` cooldown check against `adventure_last_completed_real_ts`
- [x] 4.6 Short-circuit for `scope == "turn"` (turn cooldowns are not checked here)
- [x] 4.7 Update all callers of `is_adventure_eligible()` to pass `now_ts=int(time.time())` and remove `today=` parameter

## 5. Completion Timestamp Recording

- [x] 5.1 In `oscilla/engine/pipeline.py`, after advancing ticks, add `self._player.adventure_last_completed_game_ticks[adventure_ref] = self._player.game_ticks`
- [x] 5.2 In `oscilla/engine/session.py`, replace `self._character.adventure_last_completed_on[adventure_ref] = _date.today().isoformat()` with `self._character.adventure_last_completed_real_ts[adventure_ref] = int(time.time())`; add `import time` if not present; remove `_date` import if unused

## 6. Condition Evaluator

- [x] 6.1 Add `MilestoneTicksElapsedCondition` model to `oscilla/engine/models/base.py` with fields `name: str`, `gte: int | None`, `lte: int | None` and a `require_comparator` validator
- [x] 6.2 Add `MilestoneTicksElapsedCondition` to the `Condition` union in `base.py` (place it after `MilestoneCondition`)
- [x] 6.3 Add `MilestoneTicksElapsedCondition` import to `oscilla/engine/conditions.py`
- [x] 6.4 Add evaluator branch in `evaluate()` for `MilestoneTicksElapsedCondition`: look up `MilestoneRecord` in `player.milestones.get(n)`, return False if None, compute elapsed as `player.internal_ticks - record.tick`, apply gte/lte comparators

## 7. Skill Cooldown Helpers

- [x] 7.1 Add `_skill_on_cooldown(player, skill_ref) -> bool` helper function in `oscilla/engine/actions.py` that checks both `skill_tick_expiry` and `skill_real_expiry`
- [x] 7.2 Add `_set_skill_cooldown(player, skill_ref, cooldown, template_engine)` helper in `oscilla/engine/actions.py` that sets `skill_tick_expiry` and `skill_real_expiry` from cooldown fields; logs and ignores `game_ticks` field; adds `import time`

## 8. Overworld Skill Actions

- [x] 8.1 Update the skill display loop in `oscilla/engine/actions.py` to use `_skill_on_cooldown()` for availability checks; update `cooldown_label` generation to remove `scope == "adventure"` vs `scope == "turn"` branching (now `scope != "turn"` is the adventure-scope branch)
- [x] 8.2 Update the pre-use validation in the overworld skill action handler to use `_skill_on_cooldown()`
- [x] 8.3 Update the post-use cooldown recording in the overworld handler to use `_set_skill_cooldown()`

## 9. Combat Skill Actions

- [x] 9.1 Update `_use_skill_in_combat()` in `oscilla/engine/steps/combat.py`: replace `spec.cooldown.scope == "adventure"` check with import and call to `_skill_on_cooldown()` from actions.py
- [x] 9.2 Update the post-use cooldown recording in `_use_skill_in_combat()` to call `_set_skill_cooldown()` for adventure-scope cooldowns; keep `ctx.skill_uses_this_combat` for turn-scope

## 10. Prestige Effect Cleanup

- [x] 10.1 Update `oscilla/engine/steps/effects.py` prestige effect handler: replace `player.skill_cooldowns = {}` with `player.skill_tick_expiry = {}; player.skill_real_expiry = {}`

## 11. Database Models & Migration

- [x] 11.1 Update `CharacterIterationMilestone` in `oscilla/models/character_iteration.py`: add `grant_tick: Mapped[int]` (`BigInteger`, `nullable=False`, `default=0`) and `grant_timestamp: Mapped[int]` (`BigInteger`, `nullable=False`, `default=0`) columns
- [x] 11.2 Update `CharacterIterationSkillCooldown`: replace `cooldown_remaining: Mapped[int]` with `tick_expiry: Mapped[int]` and `real_expiry: Mapped[int]` (both `BigInteger`, non-nullable, `default=0`)
- [x] 11.3 Update `CharacterIterationAdventureState`: remove `last_completed_on: Mapped[str | None]`; add `last_completed_real_ts: Mapped[int | None]` (`BigInteger`, nullable) and `last_completed_game_ticks: Mapped[int | None]` (`BigInteger`, nullable)
- [x] 11.4 Create a new Alembic migration with `make create_migration MESSAGE="tick-anchored-state-refactor"` covering all three table changes; verify migration is compatible with both SQLite and PostgreSQL; run `make check_ungenerated_migrations` to confirm no further migrations are needed

## 12. Service Layer

- [x] 12.1 Update `add_milestone()` in `oscilla/services/character.py`: add `grant_tick: int` and `grant_timestamp: int` parameters; pass them to `CharacterIterationMilestone(...)`
- [x] 12.2 Update `set_skill_cooldown()`: replace `cooldown_remaining: int` parameter with `tick_expiry: int` and `real_expiry: int`; update delete condition to `tick_expiry <= 0 and real_expiry <= 0`; update merge call to use new column names
- [x] 12.3 Update `upsert_adventure_state()`: replace `last_completed_on: str | None` with `last_completed_real_ts: int | None`; add `last_completed_game_ticks: int | None`; update merge call
- [x] 12.4 Update `load_character()` milestone deserialization: change `[row.milestone_ref for row in iteration.milestone_rows]` to `{row.milestone_ref: {"tick": row.grant_tick, "timestamp": row.grant_timestamp} for row in iteration.milestone_rows}` so it produces the current nested-dict format directly
- [x] 12.5 Update `load_character()` skill cooldown deserialization: replace `skill_cooldowns` dict with `skill_tick_expiry` and `skill_real_expiry` dicts sourced from `tick_expiry` / `real_expiry` columns
- [x] 12.6 Update `load_character()` adventure state deserialization: replace `adventure_last_completed_on` dict with `adventure_last_completed_real_ts`, `adventure_last_completed_game_ticks`; keep `adventure_last_completed_at_ticks`; update the `data` dict passed to `CharacterState.from_dict()`

## 13. Session Persistence Diff

- [x] 13.1 Update `_persist_diff()` in `oscilla/engine/session.py`: replace `state.milestones - last_milestones` set subtraction with dict iteration; pass `grant_tick=record.tick, grant_timestamp=record.timestamp` to `add_milestone()`
- [x] 13.2 Update `_persist_diff()`: replace `skill_cooldowns` diff with `skill_tick_expiry` + `skill_real_expiry` diff; pass `tick_expiry` and `real_expiry` to `set_skill_cooldown()`
- [x] 13.3 Update `_persist_diff()` adventure state section: replace `adventure_last_completed_on` diff with `adventure_last_completed_real_ts` + `adventure_last_completed_game_ticks`; pass updated params to `upsert_adventure_state()`

## 14. Tests

- [x] 14.1 Add `test_grant_milestone_records_tick_and_timestamp()` to `tests/engine/test_character.py` — verifies `milestones[name].tick == internal_ticks` and `milestones[name].timestamp > 0` at grant time
- [x] 14.2 Add `test_grant_milestone_noop_if_already_held()` — verifies the original `MilestoneRecord` (both tick and timestamp) is not overwritten on re-grant
- [x] 14.3 Add `test_from_dict_migrates_milestone_list()` — verifies old `["a", "b"]` format migrates to `{"a": MilestoneRecord(tick=0, timestamp=0), ...}`
- [x] 14.4 Add `test_from_dict_migrates_milestone_int_dict()` — verifies intermediate `{"a": 42}` format migrates to `{"a": MilestoneRecord(tick=42, timestamp=0)}`
- [x] 14.5 Add `test_from_dict_migrates_game_prefix_from_at_ticks()` — verifies `__game__dungeon-raid` entries migrate out
- [x] 14.6 Add `test_is_adventure_eligible_ticks_cooldown()` — builds `Cooldown(ticks=5)` and tests in/out of cooldown
- [x] 14.7 Add `test_is_adventure_eligible_seconds_cooldown()` — builds `Cooldown(seconds=3600)` and tests with Unix timestamps
- [x] 14.8 Add `test_is_adventure_eligible_multiple_constraints_anded()` — builds `Cooldown(ticks=5, seconds=3600)` and verifies both must pass
- [x] 14.9 Add `tests/engine/models/test_cooldown.py` with tests for `Cooldown` model validation: turn scope rejects ticks, no-scope rejects turns, empty cooldown rejected, template string accepted
- [x] 14.10 Add `test_milestone_ticks_elapsed_*` tests to `tests/engine/test_conditions.py` covering: not granted → False, gte pass, gte fail, lte pass, lte fail, both gte+lte window, no comparator raises
- [x] 14.11 Add skill cooldown integration test class in `tests/engine/` that verifies `_skill_on_cooldown()` and `_set_skill_cooldown()` work correctly end-to-end with a minimal skill fixture

## 15. Content Migration — Testlandia

- [x] 15.1 Audit `content/testlandia/` for any adventures using flat cooldown fields (`cooldown_days`, `cooldown_ticks`, `cooldown_game_ticks`) and migrate each to nested `cooldown:` syntax
- [x] 15.2 Audit `content/testlandia/` skills for `SkillCooldown`-style YAML (`scope: adventure, count: N`) and migrate to `cooldown: {ticks: N}`; migrate `scope: turn, count: N` to `cooldown: {scope: turn, turns: N}`
- [x] 15.3 Create `content/testlandia/adventures/test-cooldown-ticks.yaml` — adventure with `cooldown: {ticks: 3}`; description text explains the cooldown; serves as manual QA for tick-based repeat controls
- [x] 15.4 Create `content/testlandia/adventures/test-cooldown-seconds.yaml` — adventure with `cooldown: {seconds: "{{ SECONDS_PER_MINUTE }}"}` (1 minute); demonstrates real-world cooldown with template constant
- [x] 15.5 Create `content/testlandia/adventures/test-milestone-timestamps.yaml` — adventure that grants milestone `timestamp-test` on first completion; a follow-up step gated by `milestone_ticks_elapsed: {name: timestamp-test, gte: 2}` is only visible after 2 more adventures complete; allows manual QA of the new condition
- [x] 15.6 Add or update a testlandia skill to use `cooldown: {ticks: 2}` (previously this would have been non-functional); verify the skill is correctly blocked and re-enabled by advancing ticks
- [x] 15.7 Run `uv run oscilla content test` on testlandia and verify all manifests validate without errors
- [x] 15.8 Run `uv run pytest` and verify all tests pass after all migrations

## 16. Documentation

- [x] 16.1 Create `docs/authors/cooldowns.md` — new document for content authors covering: unified `cooldown:` schema; `ticks`, `game_ticks`, `seconds`, `turns` fields; `scope: turn` behavior; template expressions; `SECONDS_PER_*` constants; adventure vs skill examples; migration guide from old flat fields
- [x] 16.2 Update `docs/authors/adventures.md` — replace repeat-controls section flat-field examples with nested `cooldown:` block; add cross-reference to cooldowns.md
- [x] 16.3 Update `docs/authors/skills.md` — replace `scope: adventure, count: N` cooldown examples with equivalent `ticks: N`; add cross-reference to cooldowns.md
- [x] 16.4 Update `docs/authors/conditions.md` — add `milestone_ticks_elapsed` condition entry with `gte`/`lte` fields and YAML examples; clarify `internal_ticks` vs `game_ticks` distinction
- [x] 16.5 Update `docs/authors/templates.md` — add `SECONDS_PER_MINUTE`, `SECONDS_PER_HOUR`, `SECONDS_PER_DAY`, `SECONDS_PER_WEEK` to the built-in globals reference table
- [x] 16.6 Update `docs/dev/game-engine.md` — document the two-track time model in character state; describe `adventure_last_completed_*` dicts; describe `_skill_on_cooldown` and `_set_skill_cooldown` helpers; note the `tick_skill_cooldowns` bug that was fixed
- [x] 16.7 Add `docs/authors/cooldowns.md` and any new docs to the table of contents in `docs/authors/README.md`
