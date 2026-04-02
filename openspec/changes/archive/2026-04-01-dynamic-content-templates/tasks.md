## 1. Dependencies and Project Setup

- [x] 1.1 Add `jinja2` as a direct declared dependency in `pyproject.toml` (it is likely already a transitive dependency; make it explicit)
- [x] 1.2 Run `make sync` to update `uv.lock` with the pinned `jinja2` version

## 2. Core Template Engine — `oscilla/engine/templates.py`

- [x] 2.1 Create `oscilla/engine/templates.py` with the `PronounSet` frozen dataclass and three predefined sets (`they_them`, `she_her`, `he_him`) plus `DEFAULT_PRONOUN_SET`
- [x] 2.2 Implement `preprocess_pronouns(template_str: str) -> str` — regex preprocessing pass that rewrites pronoun and verb placeholders into Jinja2 expressions with capitalisation filters
- [x] 2.3 Implement read-only context objects: `PlayerPronounView`, `PlayerMilestoneView`, `PlayerContext`, `CombatContextView`, `ExpressionContext`
- [x] 2.4 Implement `PlayerContext.from_character(char: CharacterState) -> PlayerContext` classmethod
- [x] 2.5 Implement safe built-in functions: `_safe_roll`, `_safe_choice`, `_safe_random`, `_safe_sample`, `_now`, `_today`, `_clamp`; define `SAFE_GLOBALS` dict including all of the above plus the calendar/astronomical functions from `calendar_utils` (`season`, `month_name`, `day_name`, `week_number`, `mean`, `zodiac_sign`, `chinese_zodiac`, `moon_phase`), `round`, `sum`, and all Python builtins
- [x] 2.6 Implement safe template filters: `_filter_stat_modifier`, `_filter_pluralize`; define `SAFE_FILTERS` dict
- [x] 2.7 Implement mock context builder: `_StrictMockDict`, `_MockPlayerMilestones`, `_MockPlayerPronouns`, `_MockPlayer`, `_MockCombatContext`, and `build_mock_context(stat_names, include_combat) -> dict`
- [x] 2.8 Define `TemplateValidationError` and `TemplateRuntimeError` exception classes
- [x] 2.9 Implement `GameTemplateEngine` class with `__init__`, `precompile_and_validate`, `render`, `render_int`, and `is_template` methods
- [x] 2.10 Create `oscilla/engine/calendar_utils.py` with all calendar and astronomical utility functions: `season`, `month_name`, `day_name`, `week_number`, `mean`, `zodiac_sign`, `chinese_zodiac`, `moon_phase` (see design for full implementations; no external dependencies beyond `calendar`, `datetime`, `statistics`)

## 3. Character and Config Model Updates

- [x] 3.1 Add `title: str = ""` field and `pronouns: PronounSet` field (defaulting to `DEFAULT_PRONOUN_SET`) to `CharacterState` dataclass in `oscilla/engine/character.py`
- [x] 3.2 Update `CharacterState.to_dict()` to serialise `title` and `pronouns` (as string key via reverse-lookup of `PRONOUN_SETS`)
- [x] 3.3 Update `CharacterState.from_dict()` to deserialise `title` and `pronouns`; fall back to `they_them` and log a warning for unknown keys
- [x] 3.4 Add `PronounSetDefinition` Pydantic model to `oscilla/engine/models/character_config.py`
- [x] 3.5 Add `extra_pronoun_sets: List[PronounSetDefinition] = []` field to `CharacterConfigSpec`

## 4. Adventure Model Updates

- [x] 4.1 Widen `XpGrantEffect.amount` from `int` to `int | str` in `oscilla/engine/models/adventure.py`; update or add `@field_validator` to keep the non-zero check for literal ints while passing through template strings
- [x] 4.2 Widen `StatChangeEffect.amount` from `int` to `int | str`
- [x] 4.3 Widen `ItemDropEffect.count` from `int` (with `ge=1`) to `int | str`

## 5. Content Registry — store `GameTemplateEngine`

- [x] 5.1 Add `template_engine: GameTemplateEngine | None = None` field to `ContentRegistry` dataclass in `oscilla/engine/registry.py`

## 6. Loader — template precompilation and validation

- [x] 6.1 Implement `_collect_all_template_strings(manifests) -> list[tuple[str, str, str]]` helper in `oscilla/engine/loader.py` — walks all adventure manifests and returns `(template_id, raw_str, context_type)` triples
- [x] 6.2 Implement `_validate_templates(manifests, engine) -> list[LoadError]` helper — calls `engine.precompile_and_validate()` for each collected string and accumulates errors
- [x] 6.3 Update `load()` to: extract stat names from `CharacterConfig`, construct `GameTemplateEngine`, call `_validate_templates()`, raise `ContentLoadError` on any template errors, and pass the engine to `_build_registry()`
- [x] 6.4 Update `load_games()` similarly to ensure multi-game setups also validate templates per game
- [x] 6.5 Update `_build_registry()` to accept and store the `GameTemplateEngine` on the returned `ContentRegistry`
- [x] 6.6 Add load-time validation that `extra_pronoun_sets` in `CharacterConfig` do not conflict with built-in set names

## 7. Pipeline — construct and thread ExpressionContext

- [x] 7.1 Add `_build_context(combat_view=None) -> ExpressionContext` method to `AdventurePipeline` in `oscilla/engine/pipeline.py`
- [x] 7.2 Update `_run_effects()` to accept and pass `ExpressionContext` to each effect dispatch call
- [x] 7.3 Update all step-handler call sites in `_dispatch()` to pass the fresh `ExpressionContext`

## 8. Effect Dispatcher — resolve template fields

- [x] 8.1 Add `ctx: ExpressionContext | None = None` parameter to `run_effect()` in `oscilla/engine/steps/effects.py`
- [x] 8.2 At the top of `run_effect()`, build a default `ExpressionContext` from `player` state if `ctx` is `None`
- [x] 8.3 Implement template resolution for `XpGrantEffect.amount`: when field is `str`, call `engine.render_int()` and build a resolved copy of the effect
- [x] 8.4 Implement template resolution for `StatChangeEffect.amount`: same pattern
- [x] 8.5 Implement template resolution for `ItemDropEffect.count`: same pattern

## 9. Narrative Step — render template text

- [x] 9.1 Update `oscilla/engine/steps/narrative.py` (or whichever module handles `NarrativeStep` execution) to accept `ExpressionContext`
- [x] 9.2 Before passing `step.text` to the TUI, check `engine.is_template(text)` and call `engine.render()` if true; pass plain text directly otherwise

## 10. Database Migration

- [x] 10.1 Run `make create_migration MESSAGE="add title and pronoun_set to characters"` to scaffold the Alembic migration
- [x] 10.2 Edit the generated migration to add `title VARCHAR NOT NULL DEFAULT ''` and `pronoun_set VARCHAR NOT NULL DEFAULT 'they_them'` to the `characters` table
- [x] 10.3 Verify the migration applies cleanly against both SQLite (test DB) and confirm it is reversible via `downgrade()`
- [x] 10.4 Run `make document_schema` to update database schema documentation

## 11. Unit Tests — Template Engine

- [x] 11.1 Create `tests/engine/test_templates.py`; add tests for `preprocess_pronouns()`: all pronoun forms, all capitalisation patterns (lower / Title / UPPER), both `{is}` and `{are}`, verb pairs `{was}`/`{were}` and `{has}`/`{have}`, unrecognised placeholder left unchanged
- [x] 11.2 Add `GameTemplateEngine` tests: successful precompile and render for name, stat, level, pronoun, roll, choice, math; invalid player property raises `TemplateValidationError`; invalid stat name raises `TemplateValidationError`; combat context unavailable in adventure context raises `TemplateValidationError`; combat context available in combat context succeeds
- [x] 11.3 Add built-in function tests: `roll()` range, `roll()` with low > high raises, `choice()` from list, `choice()` empty list raises, `sample()` returns k unique elements, `sample()` with k > len raises, `clamp()` within bounds, `clamp()` with lo > hi raises, `round()` rounds correctly, `sum()` totals a list, `random()` returns float in `[0.0, 1.0)`, `now()` returns a `datetime` with correct year, `today()` returns a `date` with correct year; for calendar functions confirm correct return types and that out-of-range arguments raise `ValueError`
- [x] 11.4 Add filter tests: `stat_modifier` positive and negative, `pluralize` singular and plural
- [x] 11.5 Add `render_int()` tests: template resolves to int succeeds, template resolves to non-int raises `TemplateRuntimeError`
- [x] 11.6 Create `tests/engine/test_calendar_utils.py`; add unit tests for every function in `calendar_utils.py`: `season()` for all four seasons, `month_name()` range validation, `day_name()` range validation, `week_number()` returns int in 1–53, `mean()` correct average, `mean()` empty list raises, `zodiac_sign()` spot-checks on known dates, `chinese_zodiac()` 12-year cycle correctness, `moon_phase()` returns one of the eight phase names

## 12. Unit Tests — Pronoun System

- [x] 12.1 Create `tests/engine/test_pronoun_system.py`; add tests for all three built-in sets (correct fields, plural verb flags)
- [x] 12.2 Add `CharacterState` pronoun tests: new character defaults to `they_them`; `to_dict()` serialises as string key; `from_dict()` restores set; unknown key falls back to `they_them` and logs warning
- [x] 12.3 Add pronoun rendering tests: all three sets render correct forms for `{they}`, `{Their}`, `{THEY}`, `{them}`, `{their}`, `{is}`, `{are}`, `{was}`, `{has}`
- [x] 12.4 Add custom pronoun set loading tests: valid `extra_pronoun_sets` in `CharacterConfig` loads without error; conflicting name raises `ContentLoadError`

## 13. Integration Tests — Template Loading and Pipeline

- [x] 13.1 Create `tests/fixtures/content/template-system/` directory with minimal manifest set: a `CharacterConfig`, a `Game`, and one `Adventure` that uses `{{ player.name }}` in narrative text and `roll()` in an `xp_grant.amount`
- [x] 13.2 Create `tests/engine/test_template_integration.py`; add test: fixture loads via `load()` without error; template text renders correctly; XP amount is within expected roll range after pipeline execution
- [x] 13.3 Add test: adventure fixture with invalid template raises `ContentLoadError` with the template path in the message
- [x] 13.4 Add test: `stat_change` effect with template amount applies correct delta via mock pipeline execution
- [x] 13.5 Add test: `oscilla validate` CLI command exits 0 on valid template fixture; exits non-zero and prints error on invalid template fixture

## 14. Documentation

- [x] 14.1 Update `docs/authors/content-authoring.md`: add a "Dynamic Templates" section covering Jinja2 syntax overview, all built-in functions and filters with examples, pronoun placeholder reference table, `oscilla validate` usage for template errors
- [x] 14.2 Create `docs/authors/pronouns.md`: pronoun system overview, all supported placeholder words and capitalisation variants, verb agreement table, example adventure snippets, how to add custom pronoun sets via `CharacterConfig`
- [x] 14.3 Add `pronouns.md` to the table of contents in `docs/authors/README.md`
- [x] 14.4 Update `docs/dev/game-engine.md`: `GameTemplateEngine` class and lifecycle, `ExpressionContext` and `PlayerContext` structure, how templates are precompiled and cached, how `_validate_templates()` integrates with `load()`, adding new built-in functions or filters

## 15. Testlandia Content — Template System Region

- [x] 15.1 Create `content/testlandia/regions/template-system/template-system.yaml` — region manifest; verify it appears in `oscilla validate --game testlandia`
- [x] 15.2 Create `content/testlandia/regions/template-system/locations/pronoun-selection/pronoun-selection.yaml` — location manifest
- [x] 15.3 Create `content/testlandia/regions/template-system/locations/pronoun-selection/adventures/choose-pronouns.yaml` — choice adventure that presents all three built-in pronoun sets by name and uses a `stat_set` to store the selection in a `pronoun_slot` hidden stat; verify the adventure loads and runs in the TUI
- [x] 15.4 Create `content/testlandia/regions/template-system/locations/narrative-test/narrative-test.yaml` — location manifest
- [x] 15.5 Create `content/testlandia/regions/template-system/locations/narrative-test/adventures/personalized-greeting.yaml` — narrative adventure that uses `{{ player.name }}`, `{{ player.level }}`, `{they}`, `{Their}`, `{their}`, `{is}`, and `{are}`; verify correct rendering for she/her, he/him, and they/them players
- [x] 15.6 Create `content/testlandia/regions/template-system/locations/variable-rewards/variable-rewards.yaml` — location manifest
- [x] 15.7 Create `content/testlandia/regions/template-system/locations/variable-rewards/adventures/treasure-hunt.yaml` — adventure with `xp_grant { amount: "{{ roll(10, 50) }}" }` and `stat_change { stat: gold, amount: "{{ roll(1, 20) }}" }`; verify XP and gold vary across multiple plays
- [x] 15.8 Create `content/testlandia/regions/template-system/locations/conditional-narrative/conditional-narrative.yaml` — location manifest
- [x] 15.9 Create `content/testlandia/regions/template-system/locations/conditional-narrative/adventures/fame-check.yaml` — adventure with `{% if player.milestones.has('hero-of-testlandia') %}` hero branch and else fallback; verify both branches render correctly
- [x] 15.10 Run `oscilla validate --game testlandia` and confirm exit code 0 after all template-system content is in place
- [x] 15.11 Perform manual QA from the Testlandia Integration checklist in the design document: pronoun selection round-trip for all three built-in sets, variable reward variance, milestone-conditional narrative branching
