## 1. Calendar Utilities

- [x] 1.1 Update `oscilla/engine/calendar_utils.py`: replace `_SEASON_MONTHS` with `_SEASON_MONTHS_N` and `_SEASON_MONTHS_S` tables and add `hemisphere: str = "northern"` parameter to `season()`
- [x] 1.2 Add unit tests for `season()` hemisphere parameter in `tests/engine/test_calendar_utils.py` — verify northern and southern results for all four season boundaries

## 2. Game Manifest Model

- [x] 2.1 Add `season_hemisphere: Literal["northern", "southern"] = "northern"` field to `GameSpec` in `oscilla/engine/models/game.py`
- [x] 2.2 Add `Literal` to the `typing` import in `oscilla/engine/models/game.py` if not already present
- [x] 2.3 Verify existing game.yaml files in `content/` load without errors after the model change (run `make pytest`)

## 3. Condition Models

- [x] 3.1 Add `_resolve_month()` and `_resolve_weekday()` normalisation helpers to `oscilla/engine/models/base.py`
- [x] 3.2 Add `SeasonIsCondition` model to `oscilla/engine/models/base.py`
- [x] 3.3 Add `MoonPhaseIsCondition` model to `oscilla/engine/models/base.py`
- [x] 3.4 Add `ZodiacIsCondition` model to `oscilla/engine/models/base.py`
- [x] 3.5 Add `ChineseZodiacIsCondition` model to `oscilla/engine/models/base.py`
- [x] 3.6 Add `MonthIsCondition` model with `@model_validator` normalisation to `oscilla/engine/models/base.py`
- [x] 3.7 Add `DayOfWeekIsCondition` model with `@model_validator` normalisation to `oscilla/engine/models/base.py`
- [x] 3.8 Add `DateIsCondition` model with `@model_validator` normalisation to `oscilla/engine/models/base.py`
- [x] 3.9 Add `TimeBetweenCondition` model with `pattern` validation on `start`/`end` fields to `oscilla/engine/models/base.py`
- [x] 3.10 Register all 8 new condition models in the `Condition` annotated union in `oscilla/engine/models/base.py`

## 4. Condition Evaluator

- [x] 4.1 Add `import datetime` and `from oscilla.engine import calendar_utils` to `oscilla/engine/conditions.py`
- [x] 4.2 Add all 8 new condition model classes to the import list from `oscilla.engine.models.base` in `oscilla/engine/conditions.py`
- [x] 4.3 Add `case SeasonIsCondition` branch to the `evaluate()` match block — reads hemisphere from `registry.game.spec.season_hemisphere` when available
- [x] 4.4 Add `case MoonPhaseIsCondition` branch to `evaluate()`
- [x] 4.5 Add `case ZodiacIsCondition` branch to `evaluate()`
- [x] 4.6 Add `case ChineseZodiacIsCondition` branch to `evaluate()`
- [x] 4.7 Add `case MonthIsCondition` branch to `evaluate()`
- [x] 4.8 Add `case DayOfWeekIsCondition` branch to `evaluate()`
- [x] 4.9 Add `case DateIsCondition` branch to `evaluate()`
- [x] 4.10 Add `case TimeBetweenCondition` branch to `evaluate()` with midnight-wrap logic and zero-duration warning

## 5. Template Engine — GameContext

- [x] 5.1 Add `GameContext` frozen dataclass to `oscilla/engine/templates.py` (field: `season_hemisphere: str = "northern"`)
- [x] 5.2 Add `game: GameContext` field (with `field(default_factory=GameContext)`) to `ExpressionContext` in `oscilla/engine/templates.py`
- [x] 5.3 Verify `field` is imported from `dataclasses` in `oscilla/engine/templates.py`
- [x] 5.4 Add `_MockGame` class to `oscilla/engine/templates.py` for load-time template validation
- [x] 5.5 Update `build_mock_context()` to include `game=_MockGame()` and override `season` with `_MockGame.season_hemisphere`-aware closure
- [x] 5.6 Update `GameTemplateEngine.render()` to include `game=ctx.game` in render context and override `season` with hemisphere-aware closure
- [x] 5.7 Update `GameContext` import in `oscilla/engine/pipeline.py` — add `GameContext` to the template import line
- [x] 5.8 Update `AdventurePipeline._build_context()` in `oscilla/engine/pipeline.py` to construct `GameContext(season_hemisphere=...)` from registry
- [x] 5.9 Update fallback `ExpressionContext` construction in `oscilla/engine/steps/effects.py` `run_effect()` to include `game=GameContext(season_hemisphere=...)`

## 6. Tests — Condition Evaluator

- [x] 6.1 Create `tests/engine/test_calendar_conditions.py` with `freeze_date` and `freeze_datetime` helpers that monkeypatch `oscilla.engine.conditions.datetime`
- [x] 6.2 Add true/false tests for `SeasonIsCondition` (northern hemisphere)
- [x] 6.3 Add true test for `SeasonIsCondition` with southern hemisphere registry fixture
- [x] 6.4 Add true/false tests for `MoonPhaseIsCondition`
- [x] 6.5 Add true/false tests for `ZodiacIsCondition`
- [x] 6.6 Add true/false tests for `ChineseZodiacIsCondition`
- [x] 6.7 Add true/false tests for `MonthIsCondition` with both integer and string inputs
- [x] 6.8 Add parse-time error test for invalid string month name in `MonthIsCondition`
- [x] 6.9 Add true/false tests for `DayOfWeekIsCondition` with both integer and string inputs
- [x] 6.10 Add true/false tests for `DateIsCondition` without year (annual match)
- [x] 6.11 Add true/false tests for `DateIsCondition` with year (exact match and wrong year)
- [x] 6.12 Add tests for `TimeBetweenCondition`: same-day window (inside and outside), midnight-wrapping window (true after start, true before end, false in gap), zero-duration false
- [x] 6.13 Add composition test: `all` containing a `MonthIsCondition` and a `MoonPhaseIsCondition`

## 7. Tests — Template Engine

- [x] 7.1 Add test to `tests/engine/test_templates.py` verifying `ExpressionContext` default `game` is `GameContext(season_hemisphere="northern")`
- [x] 7.2 Add test verifying `GameContext(season_hemisphere="southern")` is stored and accessible on `ExpressionContext`
- [x] 7.3 Add test verifying that `{{ game.season_hemisphere }}` renders correctly with a southern-hemisphere `GameContext`
- [x] 7.4 Add test verifying `{{ game.unknown_field }}` raises `ContentLoadError` during mock render

## 8. Documentation

- [x] 8.1 Create `docs/authors/calendar-conditions.md` covering: all 8 predicates with YAML examples; `season_hemisphere` game.yaml setting; hemisphere behavior; `time_between` midnight-wrap; `date_is` annual vs. one-off; `month_is`/`day_of_week_is` int vs. string; server local time note; composition examples
- [x] 8.2 Add `calendar-conditions.md` link to the table of contents in `docs/authors/README.md`
- [x] 8.3 Update `openspec/specs/condition-evaluator/spec.md` by syncing the delta from `changes/calendar-conditions/specs/condition-evaluator/spec.md`
- [x] 8.4 Update `openspec/specs/dynamic-content-templates/spec.md` by syncing the delta from `changes/calendar-conditions/specs/dynamic-content-templates/spec.md`

## 9. Testlandia Content

- [x] 9.1 Create `content/testlandia/regions/conditions/locations/calendar/calendar.yaml` — a new Location manifest named `test-calendar` in the `conditions` region, listing all calendar test adventures
- [x] 9.2 Create `content/testlandia/regions/conditions/locations/calendar/adventures/test-moon-phase-show.yaml` — an unconditional adventure that renders current date, season, moon phase, zodiac, Chinese zodiac, day name, and month name using template functions; verifies template functions work end-to-end
- [x] 9.3 Create `content/testlandia/regions/conditions/locations/calendar/adventures/test-season-is-spring.yaml` — adventure unlocked only by `season_is: spring`; text confirms spring detection
- [x] 9.4 Create `content/testlandia/regions/conditions/locations/calendar/adventures/test-season-is-summer.yaml` — adventure unlocked only by `season_is: summer`; text confirms summer detection
- [x] 9.5 Create `content/testlandia/regions/conditions/locations/calendar/adventures/test-season-is-autumn.yaml` — adventure unlocked only by `season_is: autumn`; text confirms autumn detection
- [x] 9.6 Create `content/testlandia/regions/conditions/locations/calendar/adventures/test-season-is-winter.yaml` — adventure unlocked only by `season_is: winter`; text confirms winter detection
- [x] 9.7 Create `content/testlandia/regions/conditions/locations/calendar/adventures/test-month-is.yaml` — adventure unlocked by `month_is: "April"` (string form) with text confirming it is April; verifies string month name parsing
- [x] 9.8 Create `content/testlandia/regions/conditions/locations/calendar/adventures/test-time-between.yaml` — adventure unlocked by `time_between: {start: "09:00", end: "17:00"}` representing "business hours"; text explains the window and notes server local time
- [x] 9.9 Create `content/testlandia/regions/conditions/locations/calendar/adventures/test-zodiac-is.yaml` — adventure unlocked by `zodiac_is: "Aries"` (April 5 falls in Aries); text shows current zodiac via template
- [x] 9.10 Create `content/testlandia/regions/conditions/locations/calendar/adventures/test-moon-phase-composition.yaml` — adventure unlocked by `all: [month_is: 4, moon_phase_is: <current april phase>]`; demonstrates multi-condition calendar composition; acceptance: adventure appears only when both conditions are true
- [x] 9.11 Run `make pytest` to confirm all testlandia content loads without errors after additions
- [x] 9.12 Manually verify testlandia: navigate to the Calendar Conditions Lab location, confirm `test-moon-phase-show` is always available and renders all calendar fields correctly
