## Why

Character state currently records timestamps and cooldown progress using three different, inconsistent approaches: ISO date strings (day-precision only), adventure-count countdowns that are never decremented (a live bug), and a mix of internal-tick and game-tick tracking with no shared schema. This inconsistency makes it impossible to express "how long ago" comparisons on milestones, prevents sub-day real-world cooldowns, and silently breaks adventure-scoped skill cooldowns. Fixing this now, before any live content package relies on the broken behavior, unifies all time tracking onto a clean two-track model (internal ticks + real-world seconds) and introduces a single reusable `Cooldown` schema used everywhere.

## What Changes

- **BREAKING** `CharacterState.milestones` changes from `Set[str]` to `Dict[str, int]` — values are the `internal_ticks` value at which the milestone was granted. Existing `has_milestone()` API is preserved. `grant_milestone()` now records the tick.
- **BREAKING** `CharacterState.adventure_last_completed_on` (ISO date string) is removed and replaced by `adventure_last_completed_real_ts: Dict[str, int]` (Unix timestamp in seconds).
- **BREAKING** `adventure_last_completed_at_ticks` internal `__game__` prefix hack renamed to a clean `adventure_last_completed_game_ticks: Dict[str, int]` field.
- **BREAKING** Adventure cooldown fields (`cooldown_days`, `cooldown_ticks`, `cooldown_game_ticks`) replaced by a single nested `cooldown: Cooldown | None` field on `AdventureSpec`.
- **BREAKING** Skill `SkillCooldown(scope, count)` model replaced by the shared `Cooldown` model.
- **BREAKING** `CharacterState.skill_cooldowns` (adventure-count countdown) removed; replaced by `skill_tick_expiry: Dict[str, int]` and `skill_real_expiry: Dict[str, int]` (absolute expiry timestamps set at skill use time).
- Bug fix: `tick_skill_cooldowns()` method (defined but never called — skill cooldowns were silently non-functional) is deleted; expiry-timestamp storage makes countdown ceremony unnecessary.
- New `Cooldown` Pydantic model shared by both adventures and skills: `ticks`, `game_ticks`, `seconds`, `turns` (all template-processable `int | str | None`), plus `scope: Literal["turn"] | None`.
- Template constants added to the template rendering context: `SECONDS_PER_MINUTE`, `SECONDS_PER_HOUR`, `SECONDS_PER_DAY`, `SECONDS_PER_WEEK` — enabling authored cooldown expressions like `seconds: "{{ SECONDS_PER_DAY * 3 }}"`.
- New condition: `milestone_ticks_elapsed` — evaluates how many internal ticks have passed since a named milestone was granted, with `gte`/`lte` comparators. Enables "time since event" narrative conditions.
- `deprecated cooldown_adventures` migration removed (it already auto-migrated to `cooldown_ticks`; nested schema replaces it cleanly).
- Testlandia updated to demonstrate all new capabilities.

## Capabilities

### New Capabilities

- `milestone-timestamps`: Milestones now record the internal tick at grant time; a new `milestone_ticks_elapsed` condition enables comparisons like "at least N ticks since milestone X was granted".
- `unified-cooldown-schema`: Single `Cooldown` model used by both adventures and skills, supporting `ticks`, `game_ticks`, `seconds`, and `turns` constraints that are AND-ed together. Template-processable fields with template constants in context.

### Modified Capabilities

- `player-state`: `CharacterState` field renames and type changes — milestone dict, removed `skill_cooldowns`, new expiry fields, timestamp fields.
- `adventure-repeat-controls`: Adventure cooldown fields collapse from three flat scalars + deprecated field to a single nested `cooldown:` object. Real-world cooldown goes from day-precision ISO date to second-precision Unix timestamp.
- `combat-skills`: Skill cooldown storage changes from adventure-count countdown to absolute expiry timestamps; `SkillCooldown` model replaced by shared `Cooldown`.
- `condition-evaluator`: New `milestone_ticks_elapsed` condition type added to the condition union.
- `dynamic-content-templates`: New template constants (`SECONDS_PER_*`) added to the rendering context.

## Impact

**Code changes:**

- `oscilla/engine/character.py` — field renames, type changes, `tick_skill_cooldowns()` removal
- `oscilla/engine/models/base.py` — `MilestoneTicksElapsedCondition` added to condition union
- `oscilla/engine/models/adventure.py` — flat cooldown fields replaced by `cooldown: Cooldown | None`; `Cooldown` model defined here or moved to `models/cooldown.py`
- `oscilla/engine/models/skill.py` — `SkillCooldown` replaced by `Cooldown`
- `oscilla/engine/conditions.py` — `milestone_ticks_elapsed` evaluator branch added
- `oscilla/engine/session.py` — `adventure_last_completed_on` write replaced with `adventure_last_completed_real_ts` Unix timestamp
- `oscilla/engine/pipeline.py` — `adventure_last_completed_at_ticks` rename; cooldown evaluation updated
- `oscilla/engine/actions.py` — skill cooldown read/write updated to expiry-timestamp model
- `oscilla/engine/steps/combat.py` — skill cooldown read/write updated
- `oscilla/engine/templates.py` — `SECONDS_PER_*` constants injected into template context

**Content:**

- `content/testlandia/` — adventure cooldown YAML updated to nested schema; new adventures demonstrating `milestone_ticks_elapsed` and `seconds`-based cooldowns

**No new dependencies required.** No database migration required (no live deployments).
