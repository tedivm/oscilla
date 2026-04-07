## 1. Naming Fix — `prestige_count` Everywhere

- [x] 1.1 In `oscilla/engine/models/base.py`, change `PrestigeCountCondition.type: Literal["iteration"]` to `Literal["prestige_count"]`; update the error message in `require_comparator` from `"iteration condition"` to `"prestige_count condition"`
- [x] 1.2 In `oscilla/engine/character.py`, rename the `iteration: int` field to `prestige_count: int` on the `CharacterState` dataclass
- [x] 1.3 In `oscilla/engine/character.py`, update `new_character()` to use `prestige_count=0` instead of `iteration=0`
- [x] 1.4 In `oscilla/engine/character.py`, update `to_dict()` to use the key `"prestige_count"` instead of `"iteration"`
- [x] 1.5 In `oscilla/engine/character.py`, update `from_dict()` to read `data.get("prestige_count", data.get("iteration", 0))` for backward compatibility
- [x] 1.6 In `oscilla/engine/templates.py`, rename `PlayerContext.iteration` to `PlayerContext.prestige_count` and update `from_character()` to set `prestige_count=char.prestige_count`
- [x] 1.7 In `oscilla/engine/conditions.py`, update the `PrestigeCountCondition` handler to read `player.prestige_count` instead of `player.iteration`
- [x] 1.8 In `oscilla/services/character.py`, update `load_character()` to use `"prestige_count": iteration.iteration` (dict key changes, DB column stays `iteration`)
- [x] 1.9 Run `grep -rn "\.iteration\b\|\"iteration\"" oscilla/` to find any remaining references and update them; run `make mypy_check` to confirm zero type errors
- [x] 1.10 Run `uv run pytest` to confirm all existing tests pass; update any test fixtures that used `iteration=0` to `prestige_count=0`

## 2. `prestige_pending` Ephemeral Field

- [x] 2.1 In `oscilla/engine/character.py`, define the `PrestigeCarryForward` dataclass with `carry_stats: List[str]` and `carry_skills: List[str]`
- [x] 2.2 In `oscilla/engine/character.py`, add `prestige_pending: PrestigeCarryForward | None = None` to `CharacterState`; confirm it is NOT included in `to_dict()` output and NOT read in `from_dict()`

## 3. `PrestigeConfig`, `CharacterCreationDefaults`, and `game.yaml` Blocks

- [x] 3.1 In `oscilla/engine/models/game.py`, add the `PrestigeConfig` Pydantic model with fields: `carry_stats: set[str] = Field(default_factory=set)`, `carry_skills: set[str] = Field(default_factory=set)`, `carry_milestones: set[str] = Field(default_factory=set)`, `pre_prestige_effects: List[Effect] = []`, `post_prestige_effects: List[Effect] = []`; handle the forward reference to `Effect` with `model_rebuild()` at the bottom of the file
- [x] 3.2 In `oscilla/engine/models/game.py`, add the `CharacterCreationDefaults` Pydantic model with fields: `default_name: str | None = None`, `default_pronouns: str | None = None`; add a `model_validator(mode="after")` that validates `default_pronouns` against the built-in `PRONOUN_SETS` keys at parse time (import `PRONOUN_SETS` from `oscilla.engine.templates`)
- [x] 3.3 In `oscilla/engine/models/game.py`, add `prestige: PrestigeConfig | None = None` and `character_creation: CharacterCreationDefaults | None = None` to `GameSpec`
- [x] 3.4 Run `uv run pytest` and `make mypy_check` to confirm no regressions

## 4. `PrestigeEffect` Model

- [x] 4.1 In `oscilla/engine/models/adventure.py`, add `PrestigeEffect(type: Literal["prestige"])` Pydantic model
- [x] 4.2 In `oscilla/engine/models/adventure.py`, add `PrestigeEffect` and `SetNameEffect` to the `Effect` union (before the closing bracket, after `EmitTriggerEffect`)
- [x] 4.3 Run `make mypy_check` to confirm the discriminated union is satisfied

## 5. `PrestigeEffect` Handler

- [x] 5.1 In `oscilla/engine/steps/effects.py`, import `PrestigeCarryForward` from `oscilla.engine.character`
- [x] 5.2 In `oscilla/engine/steps/effects.py`, add the `case PrestigeEffect():` handler in `run_effect()` after the `EmitTriggerEffect` case following the design doc specification: check prestige config, run pre_prestige_effects, snapshot carry values, reset player state, apply carry-forward, increment prestige_count, run post_prestige_effects, set prestige_pending, display confirmation text
- [x] 5.3 Import `PrestigeEffect` and `PrestigeConfig` in `effects.py` to ensure the match statement type-checks correctly

## 6. Session Layer — `_persist_diff` Prestige Handling

- [x] 6.1 In `oscilla/engine/session.py`, at the top of `_persist_diff`, add an early return when `state.prestige_pending is not None and event != "adventure_end"`
- [x] 6.2 In `oscilla/engine/session.py`, inside the `adventure_end` block of `_persist_diff`, add prestige transition logic: call `prestige_character()`, update `self._iteration_id`, set `self._last_saved_state = None`, clear `state.prestige_pending`
- [x] 6.3 Import the updated `prestige_character()` function at the top of `session.py` (it was already imported; update to the new signature)

## 7. `prestige_character()` Service Function Update

- [x] 7.1 In `oscilla/services/character.py`, add `game_manifest: "GameManifest | None" = None` parameter to `prestige_character()`
- [x] 7.2 Replace the hardcoded `base_hp = 10` with `base_hp = game_manifest.spec.hp_formula.base_hp if game_manifest is not None else 10`
- [x] 7.3 Remove the premature `session.commit()` call from `prestige_character()` — the session layer now owns the transaction; replace with `session.flush()` if not already called via `session.add()`
- [x] 7.4 Update the return type annotation to `CharacterIterationRecord` and confirm the function returns the newly created record
- [x] 7.5 Run `make mypy_check` to confirm no type errors in the service layer

## 8. Load-time Validation for `PrestigeEffect`

- [x] 8.1 In `oscilla/engine/loader.py`, add a `_validate_prestige_effects(manifests) -> List[LoadError]` function that returns a `LoadError` for every adventure manifest containing `PrestigeEffect` steps when no `GameSpec` with a `prestige:` block is present among the manifests
- [x] 8.2 Call `_validate_prestige_effects()` in the content-load validation pass alongside the other `List[LoadError]`-returning validators; ensure its errors are included in the combined list that raises `ContentLoadError`
- [x] 8.3 Write a unit test in `tests/engine/` that confirms `ContentLoadError` is raised (not just a warning) when an adventure uses `type: prestige` without a `prestige:` block in `game.yaml`

## 9. `SetNameEffect` Model and Handler

- [x] 9.1 In `oscilla/engine/models/adventure.py`, add `SetNameEffect(type: Literal["set_name"], prompt: str = "What is your name?")` Pydantic model alongside `PrestigeEffect`
- [x] 9.2 Add `SetNameEffect` to the `Effect` union (covered by task 4.2 above — track completion there)
- [x] 9.3 In `oscilla/engine/steps/effects.py`, add the `_is_placeholder_name(name: str) -> bool` helper at module level using a compiled UUID regex: matches `new-{uuid4()}` pattern
- [x] 9.4 In `oscilla/engine/steps/effects.py`, add the `case SetNameEffect():` handler: if `_is_placeholder_name(player.name)`, call `player.name = (await tui.input_text(effect.prompt)).strip()`; otherwise return without prompting
- [x] 9.5 Run `make mypy_check` to confirm no type errors in `effects.py`

## 10. `SetNameEffect` — Session and Service Layer

- [x] 10.1 In `oscilla/engine/session.py`, update `_create_new_character()` to resolve the effective name using this priority order: (1) CLI `character_name` arg, (2) `registry.game.spec.character_creation.default_name` if set, (3) `f"new-{uuid4()}"` placeholder; remove the existing `tui.input_text()` prompt for the name
- [x] 10.2 In `oscilla/engine/session.py`, add `self._db_character_name: str` as a new instance field, initialized from `CharacterRecord.name` at session-start time (alongside `self._iteration_id`)
- [x] 10.3 In `oscilla/engine/session.py`, inside `_persist_diff`, add name-change detection: if `state.name != self._db_character_name`, call `await rename_character(session=self.db_session, character_id=state.character_id, new_name=state.name)` and update `self._db_character_name = state.name`
- [x] 10.4 In `oscilla/services/character.py`, add `rename_character(session, character_id, new_name)` async function: reads `CharacterRecord`, checks uniqueness within `(user_id, game_name)`, updates `record.name`, calls `touch_character_updated_at`; raises `ValueError` if the name is already taken
- [x] 10.5 Run `uv run pytest` to confirm no regressions from the session and service changes

## 11. `CharacterCreationDefaults` — `new_character()` Pronouns

- [x] 11.1 In `oscilla/engine/character.py`, update `new_character()` to resolve initial pronouns from `game_manifest.spec.character_creation.default_pronouns` when set: use `PRONOUN_SETS.get(key)`, fall back to `DEFAULT_PRONOUN_SET` with a `logger.warning` if the key is unknown; pass `pronouns=initial_pronouns` in the `cls(...)` constructor call
- [x] 11.2 Run `make mypy_check` and `uv run pytest` to confirm no regressions

## 12. Unit Tests — Naming Rename

- [x] 12.1 In `tests/engine/` (or appropriate existing test file), add `test_prestige_count_condition_yaml_key`: asserts `{type: prestige_count, gte: 1}` parses as `PrestigeCountCondition`
- [x] 12.2 Add `test_iteration_yaml_key_rejected`: asserts `{type: iteration, gte: 1}` raises `ValidationError`
- [x] 12.3 Add `test_character_state_prestige_count_field`: confirms `CharacterState.new_character()` sets `prestige_count=0` and the attribute `iteration` does not exist
- [x] 12.4 Add `test_to_dict_uses_prestige_count_key`: confirms `to_dict()` output contains `"prestige_count"` and not `"iteration"`
- [x] 12.5 Add `test_from_dict_backward_compat_iteration_key`: confirms `from_dict({"iteration": 3, ...})` produces `prestige_count == 3`

## 13. Unit Tests — Prestige Effect

- [x] 13.1 Create `tests/engine/test_prestige_effect.py`
- [x] 13.2 Add a `prestige_registry` fixture built from `mock_registry` with a `PrestigeConfig` carrying `legacy_power`, a `stat_change +1` pre_prestige_effect, and the `hidden_stats: [legacy_power]` + `public_stats: [cunning]` declared in the character config
- [x] 13.3 Add `test_prestige_resets_level`: confirms `player.level == 1` after prestige
- [x] 13.4 Add `test_prestige_increments_prestige_count`: confirms `prestige_count` increments by 1
- [x] 13.5 Add `test_prestige_runs_pre_effects_before_carry`: confirms `legacy_power` is 1 after prestige (pre_effect +1 → carry captures 1)
- [x] 13.6 Add `test_prestige_carry_stat_survives_reset`: confirms explicitly set legacy_power (5) is carried forward as 6 (pre_effect +1)
- [x] 13.7 Add `test_prestige_non_carry_stat_resets`: confirms `cunning` returns to 0 after prestige regardless of pre-prestige value
- [x] 13.8 Add `test_prestige_sets_prestige_pending`: confirms `player.prestige_pending is not None` after prestige
- [x] 13.9 Add `test_prestige_no_config_logs_error`: confirms the runtime guard in the handler logs an error and returns without mutating state when `registry.game.spec.prestige is None`
- [x] 13.10 Run `uv run pytest tests/engine/test_prestige_effect.py -v` to confirm all tests pass

## 14. Unit Tests — SetNameEffect and CharacterCreationDefaults

- [x] 14.1 Create `tests/engine/test_set_name_effect.py` and add: `test_set_name_updates_character_name`, `test_set_name_strips_whitespace`, `test_set_name_skips_when_name_is_real`, `test_set_name_skips_when_default_name_is_set`, `test_placeholder_name_detection`
- [x] 14.2 Create `tests/engine/test_character_creation_defaults.py` and add: `test_new_character_uses_default_pronouns_from_game_spec`, `test_new_character_uses_default_pronoun_set_when_no_config`, `test_new_character_warns_and_falls_back_on_unknown_pronoun_key`, `test_character_creation_defaults_default_name_bypasses_placeholder`
- [x] 14.3 Run `uv run pytest tests/engine/test_set_name_effect.py tests/engine/test_character_creation_defaults.py -v`

## 15. Testlandia — Phase 1 (Character Creation)

- [x] 15.1 Create `content/testlandia/adventures/character-creation.yaml` with the following structure: `kind: Adventure`, `metadata.name: character-creation`, steps wrapped in a `prestige_count eq: 0` conditional block: (1) narrative opening text with a `type: set_name` effect prompting for the player's name, (2) choice step for pronoun selection (they/them, she/her, he/him) via `set_pronouns` effects, (3) choice step for backstory (`cunning +1` or reputation/backstory), (4) closing narrative using `{they}` pronoun tag and `{{ player.stats.cunning }}`
- [x] 15.2 In `content/testlandia/game.yaml`, add `trigger_adventures: {on_character_create: [character-creation]}` (create the `trigger_adventures:` block if it doesn't exist)
- [x] 15.3 Run `uv run oscilla content test testlandia` to confirm the adventure validates without errors
- [x] 15.4 Run `uv run pytest tests/` to confirm the testlandia content-load tests pass

## 16. Testlandia — Phase 2 (Prestige Setup)

- [x] 16.1 In `content/testlandia/character_config.yaml`, add `legacy_power` to `hidden_stats`: `{name: legacy_power, type: int, default: 0, description: "Accumulated legacy bonus from previous prestige runs. Carries forward on prestige."}`
- [x] 16.2 In `content/testlandia/game.yaml`, add a stat threshold trigger under `triggers.on_stat_threshold`: `{stat: level, threshold: 5, name: max-level-reached}`; add `max-level-reached: [prestige-ceremony]` to `trigger_adventures`
- [x] 16.3 In `content/testlandia/game.yaml`, add the `prestige:` block: `carry_stats: [legacy_power]`, `pre_prestige_effects: [{type: stat_change, stat: legacy_power, amount: 1}]`
- [x] 16.4 Create `content/testlandia/adventures/prestige-ceremony.yaml`: steps: (1) narrative acknowledging the player's journey and showing `{{ player.stats.legacy_power }}`, (2) choice — "Step through (prestige)" with `type: prestige` effect OR "Turn back" with `type: end_adventure`, (3) post-prestige narrative step showing `{{ player.prestige_count }}`
- [x] 16.5 Run `uv run oscilla content test testlandia` to confirm the prestige-ceremony adventure and prestige config validate
- [x] 16.6 Locate the appropriate testlandia region/location (e.g., the existing town or starting area) and add `prestige-veteran-quest` to that location's adventures list with `requires: {type: prestige_count, gte: 1}`
- [x] 16.7 Create `content/testlandia/adventures/prestige-veteran-quest.yaml`: a short narrative adventure with steps that display `{{ player.stats.legacy_power }}` and `{{ player.prestige_count }}`
- [x] 16.8 Run `uv run oscilla content test testlandia` to confirm all new manifests pass validation
- [x] 16.9 Run `uv run pytest tests/` to confirm all tests still pass with the updated testlandia content

## 17. Documentation

- [x] 17.1 In `docs/authors/adventures.md`, add a section "Character Creation Adventures" covering: `on_character_create` trigger, when it fires, how to wire it in `game.yaml`, the `type: set_name` effect (behavior, placeholder-name pattern, interaction with `--character-name`), a complete example adventure demonstrating name input, pronoun selection, and a backstory stat choice; add a subsection for the `type: prestige` effect with a link to `game-configuration.md`
- [x] 17.2 In `docs/authors/game-configuration.md`, add a `character_creation:` section covering: `default_name` and `default_pronouns` fields; biographic game use case; how adventure steps override game-level defaults; then add a `prestige:` section with: field table, execution order explanation, and a complete working `game.yaml` prestige block example
- [x] 17.3 Verify both documents are findable from `docs/authors/README.md` (add links if they aren't already present)

## 18. ROADMAP Update

- [x] 18.1 In `ROADMAP.md`, remove the `[Character Creation Flow]` entry from the summary table and its corresponding section body
- [x] 18.2 In `ROADMAP.md`, remove the `[Prestige System]` entry from the summary table and its corresponding section body
- [x] 18.3 In `ROADMAP.md`, add a new entry: **Cross-Iteration Conditions/Templates/Effects** — ability to query data across all past `character_iterations` rows (e.g., "milestone ever reached in any past run", `{{ player.past_run_count }}`); requires a new query surface over iteration history; related: milestone carry-forward, per-run comparison displays

## 19. Final Validation

- [x] 19.1 Run `make tests` to execute the full test suite (pytest, ruff, mypy, dapperdata, tomlsort)
- [x] 19.2 Run `make chores` to auto-fix any formatting issues identified by the suite
- [x] 19.3 Run `make tests` again to confirm zero failures after formatting fixes
- [x] 19.4 Manually start the dev environment (`docker compose up -d`) and create a new testlandia character to confirm the character-creation adventure fires before the world map
