## Why

Content authors have no way to gate adventures, steps, or effects on real-world time — the date, month, season, day of the week, time of day, moon phase, or zodiac sign. The template engine already exposes `season()`, `moon_phase()`, `zodiac_sign()`, and related functions via `calendar_utils.py`, but the condition evaluator has no corresponding predicates. This means authors can vary *text* based on the calendar but cannot vary *adventure availability* or *branching behavior* — a significant expressive gap. The calendar utilities were explicitly built to be shared with the condition evaluator; this change completes that design intent.

## What Changes

- **New condition predicates**: `season_is`, `moon_phase_is`, `zodiac_is`, `chinese_zodiac_is`, `month_is`, `day_of_week_is`, `date_is`, and `time_between` — all composable with existing `all`/`any`/`not` branch nodes.
- **New Pydantic condition models** for each predicate added to `oscilla/engine/models/base.py` and registered in the `Condition` union.
- **New evaluator cases** in `oscilla/engine/conditions.py` dispatching to `calendar_utils` functions.
- **Season hemisphere configuration**: a new `season_hemisphere` field on `GameSpec` in `game.yaml` (`northern` | `southern`, default `northern`); the `season_is` predicate and `season()` template function both respect this setting.
- **Game config accessible to templates**: the template `ExpressionContext` gains a `GameContext` projection (read-only view of `GameSpec`) so template authors can reference game-level settings — including hemisphere — without passing them explicitly as arguments.
- **Updated `condition-evaluator` spec** to document the new predicates with scenarios.
- **Updated `dynamic-content-templates` spec** to document the `GameContext` and `season_hemisphere`-aware `season()` function.
- **New author documentation**: a dedicated `docs/authors/calendar-conditions.md` guide.
- **Testlandia content**: new adventures exercising each calendar predicate for manual QA.

## Capabilities

### New Capabilities

- `calendar-conditions`: Real-world time predicates for the condition evaluator — season, moon phase, zodiac, date, month, day of week, and time of day.

### Modified Capabilities

- `condition-evaluator`: New leaf predicate requirements added (`season_is`, `moon_phase_is`, `zodiac_is`, `chinese_zodiac_is`, `month_is`, `day_of_week_is`, `date_is`, `time_between`).
- `dynamic-content-templates`: New `GameContext` object in the expression context; `season()` function respects `game.season_hemisphere`.

## Impact

- **`oscilla/engine/models/base.py`**: New condition model classes and union registration.
- **`oscilla/engine/conditions.py`**: New `case` branches in the `evaluate()` match block.
- **`oscilla/engine/models/game.py`**: New `season_hemisphere` field on `GameSpec`.
- **`oscilla/engine/templates.py`**: `ExpressionContext` gains `game: GameContext`; `season()` reads hemisphere from context.
- **`oscilla/engine/calendar_utils.py`**: `season()` gains optional `hemisphere` parameter.
- **`content/testlandia/`**: New adventures and/or steps exercising calendar predicates.
- **No database migrations required.** No player state changes. No TUI changes.
- **No new dependencies.** All calendar logic already exists in `calendar_utils.py`.
