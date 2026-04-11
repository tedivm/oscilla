## 1. Models

- [x] 1.1 Add `BuffDuration` Pydantic model to `oscilla/engine/models/buff.py` with `turns: int | str` (required, ge=1), `ticks: int | str | None`, `game_ticks: int | str | None`, `seconds: int | str | None`, and `is_persistent` property returning `True` when any time-based field is set
- [x] 1.2 Replace `duration_turns: int` with `duration: BuffDuration` on `BuffSpec`; update the `require_tick_or_modifier` validator to remain functional
- [x] 1.3 Add `exclusion_group: str | None = None`, `priority: int | str = 0` (when a string, a variable name resolved against `resolved_vars` at apply time — same pattern as `CombatModifier.percent`; extend `validate_variable_refs` to cover string `priority`), and `exclusion_mode: Literal["block", "replace"] = "block"` to `BuffSpec`; add load-time validator emitting a warning when `priority != 0` and `exclusion_group is None`
- [x] 1.4 Add `StoredBuff` Pydantic model to `oscilla/engine/models/buff.py` with `buff_ref: str`, `remaining_turns: int`, `variables: Dict[str, int]`, `tick_expiry: int | None`, `game_tick_expiry: int | None`, `real_ts_expiry: int | None`
- [x] 1.5 Add `exclusion_group: str = ""`, `priority: int = 0` (always resolved int), `exclusion_mode: str = "block"`, and `is_persistent: bool = False` fields to `ActiveCombatEffect` in `oscilla/engine/combat_context.py`
- [x] 1.6 Add `variables: Dict[str, int]` field to `ActiveCombatEffect` (needed for writeback at combat exit); default `field(default_factory=dict)`
- [x] 1.7 Add `permanent: bool = False` field to `DispelEffect` in `oscilla/engine/models/adventure.py`

## 2. Character State

- [x] 2.1 Add `active_buffs: List[StoredBuff]` field to `CharacterState` in `oscilla/engine/character.py` with `field(default_factory=list)`
- [x] 2.2 Add import of `StoredBuff` to `character.py` (from `oscilla.engine.models.buff`)
- [x] 2.3 Implement `sweep_expired_buffs(self, now_tick: int, now_game_tick: int, now_ts: int) -> None` method on `CharacterState` that removes entries where any expiry condition is met
- [x] 2.4 Update `CharacterState.to_dict()` to include `active_buffs` serialized as a list of dicts via `sb.model_dump()`
- [x] 2.5 Update `CharacterState.from_dict()` to restore `active_buffs` from the saved list using `StoredBuff.model_validate()`; default to `[]` when key is absent

## 3. Buff Blocking

- [x] 3.1 In `run_effect()` `ApplyBuffEffect` case in `oscilla/engine/steps/effects.py`, after variable resolution: (a) resolve `priority` — if `spec.priority` is a string, look it up in `resolved_vars` (same as `_resolve_percent`) and use the resulting `int`; (b) scan `combat.active_effects` for same `exclusion_group` + same `target`; if any `ae.priority >= resolved_priority`, log DEBUG and return early; (c) if `spec.exclusion_mode == "replace"`, evict all same-group same-target entries from `combat.active_effects` before proceeding
- [x] 3.2 When constructing `ActiveCombatEffect` in the `apply_buff` handler, populate `exclusion_group`, `priority` (resolved int), `exclusion_mode`, and `variables` from the resolved spec and call-site values
- [x] 3.3 Add unit tests in `tests/engine/test_combat_skills.py` for exclusion-group behavior: (a) block mode — stronger blocks weaker, weaker does not block stronger but both remain, equal priority blocks, no group never blocked, per-target isolation; (b) replace mode — stronger evicts weaker then applies, weaker does not apply, equal priority blocked; (c) variable-name priority — same buff manifest with higher-variable application evicts lower-variable application in replace mode; (d) undeclared string priority raises load error

## 4. Buff Persistence — Effect Handlers

- [x] 4.1 In the `apply_buff` handler, set `ae.is_persistent = spec.duration.is_persistent` when constructing `ActiveCombatEffect`
- [x] 4.2 In the `dispel` handler, after removing from `combat.active_effects`, add: when `effect.permanent == True`, remove matching entries from `player.active_buffs` by `buff_ref == label`
- [x] 4.3 Add unit tests for permanent dispel: clears `active_buffs`; non-permanent dispel leaves `active_buffs` intact

## 5. Buff Persistence — Combat Lifecycle

- [x] 5.1 In `run_combat()` in `oscilla/engine/steps/combat.py`, at entry after building `CombatContext`, call `player.sweep_expired_buffs(...)` then inject `player.active_buffs` entries into `CombatContext.active_effects` with `is_persistent=True` and `remaining_turns=stored.remaining_turns`
- [x] 5.2 Extract a helper `_build_active_combat_effect(spec, buff_ref, target, variables, remaining_turns) -> ActiveCombatEffect` in `combat.py` (or `effects.py`) to deduplicate between initial apply and re-injection
- [x] 5.3 After `run_combat()` loop exits (all outcomes: win/defeat/flee), add writeback logic: for each `is_persistent` `ActiveCombatEffect` with `remaining_turns > 0` update corresponding `StoredBuff` in `player.active_buffs`; remove entries for persistent effects that hit 0 turns during combat
- [x] 5.4 Add integration tests using `tests/fixtures/content/` fixture set: persistent buff written back after partial use, buff fully consumed not stored, stored buff re-injected into second combat with correct remaining turns, sweep removes expired buff before injection

## 6. Adventure Pipeline

- [x] 6.1 In `oscilla/engine/pipeline.py`, at the point where `internal_ticks` / `game_ticks` are advanced after adventure completion, call `player.sweep_expired_buffs(now_tick=player.internal_ticks, now_game_tick=player.game_ticks, now_ts=int(time.time()))`
- [x] 6.2 Add test verifying that a tick-expiry buff is removed from `active_buffs` after adventure completion causes tick to reach `tick_expiry`

## 7. Database

- [x] 7.1 Create Alembic migration in `db/versions/` adding `character_iteration_active_buffs` table with columns: `iteration_id` (UUID FK → `character_iterations.id`), `buff_ref` (TEXT), `remaining_turns` (INT NOT NULL), `variables_json` (TEXT NOT NULL), `tick_expiry` (INT nullable), `game_tick_expiry` (INT nullable), `real_ts_expiry` (INT nullable); composite PK `(iteration_id, buff_ref)`
- [x] 7.2 Add `CharacterIterationActiveBuff` SQLAlchemy model to the appropriate models file following existing patterns for `CharacterIterationSkillCooldown`
- [x] 7.3 Update `save_character()` in `oscilla/services/character.py` to delete existing `character_iteration_active_buffs` rows for the iteration and re-insert from `player.active_buffs` (serialize `variables` as JSON text)
- [x] 7.4 Update `load_character()` in `oscilla/services/character.py` to query `character_iteration_active_buffs` and populate `active_buffs` (deserialize `variables_json`)
- [x] 7.5 Add service-layer tests: active buff persists across session save/load; no rows returns empty list

## 8. Content Migration

- [x] 8.1 Update all buff manifests in `content/testlandia/` to replace `duration_turns: N` with `duration: {turns: N}`
- [x] 8.2 Verify `oscilla content validate testlandia` passes after migration

## 9. Test Fixtures

- [x] 9.1 Create `tests/fixtures/content/persistent-buff/` with minimal manifests: a `test-game.yaml`, `test-character-config.yaml`, `test-enemy.yaml`, and `test-persistent-buff.yaml` (Buff manifest with `duration: {turns: 3, ticks: 2}`); add an encounter-scoped `test-encounter-buff.yaml` (duration: `{turns: 2}`) for contrast
- [x] 9.2 Create `tests/fixtures/content/buff-blocking/` with `test-buff-high.yaml` (exclusion_group: test-group, priority: 60) and `test-buff-low.yaml` (exclusion_group: test-group, priority: 30) for blocking unit tests

## 10. Documentation

- [x] 10.1 Update `docs/authors/skills.md` `BuffSpec` fields table: replace `duration_turns` row with `duration` row; add "Buff Blocking" subsection explaining `exclusion_group` and `priority` with YAML example; add "Buff Persistence" subsection explaining `BuffDuration` time-based fields with examples for adventure-scope and persistent scope
- [x] 10.2 Update `docs/authors/effects.md` `dispel` entry to document the new `permanent` field
- [x] 10.3 Update `docs/dev/game-engine.md`: `ActiveCombatEffect` fields table to include `exclusion_group`, `priority`, `is_persistent`; update `CombatContext` lifecycle description to cover persistent buff injection and writeback; add `BuffDuration` model table
