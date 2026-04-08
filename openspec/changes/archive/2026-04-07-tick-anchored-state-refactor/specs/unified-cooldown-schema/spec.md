## ADDED Requirements

### Requirement: Single Cooldown model used by adventures and skills

The `Cooldown` Pydantic model SHALL be defined in `oscilla/engine/models/adventure.py` and SHALL serve as the cooldown schema for both `AdventureSpec` and `SkillSpec`. The `SkillCooldown` model SHALL be removed. All cooldown configurations across the content system SHALL use this single model.

The `Cooldown` model SHALL have the following fields:

- `ticks: int | str | None` — internal_ticks elapsed since last use required before reuse. Template strings are accepted.
- `game_ticks: int | str | None` — game_ticks elapsed since last use. Template strings are accepted. Not supported for skill cooldowns (logged as warning, ignored).
- `seconds: int | str | None` — real-world seconds elapsed since last use. Template strings are accepted.
- `turns: int | str | None` — combat turns before reuse. Only valid with `scope: "turn"`. Template strings are accepted.
- `scope: Literal["turn"] | None` — `"turn"` means per-combat only; `None` (default) means persistent across sessions.

All constraints are AND-ed: if a `Cooldown` specifies both `ticks: 5` and `seconds: 3600`, both must have elapsed before the skill or adventure is usable again.

The model SHALL enforce:

1. When `scope == "turn"`, only `turns` may be set; `ticks`, `game_ticks`, `seconds` SHALL be rejected with a validation error.
2. When `scope != "turn"`, `turns` SHALL be rejected with a validation error.
3. At least one of `ticks`, `game_ticks`, `seconds`, `turns` SHALL be non-None; an empty cooldown is a validation error.

#### Scenario: Valid persistent ticks cooldown

- **WHEN** `Cooldown(ticks=5)` is constructed
- **THEN** the model is valid with `ticks=5`, `scope=None`

#### Scenario: Valid per-turn cooldown

- **WHEN** `Cooldown(scope="turn", turns=3)` is constructed
- **THEN** the model is valid

#### Scenario: Turn scope with ticks field is rejected

- **WHEN** `Cooldown(scope="turn", turns=2, ticks=5)` is constructed
- **THEN** a validation error is raised mentioning incompatible fields

#### Scenario: turns field without turn scope is rejected

- **WHEN** `Cooldown(ticks=5, turns=2)` is constructed
- **THEN** a validation error is raised

#### Scenario: Empty cooldown is rejected

- **WHEN** `Cooldown()` is constructed with no fields set
- **THEN** a validation error is raised

#### Scenario: Template string is accepted in ticks field

- **WHEN** `Cooldown(seconds="{{ SECONDS_PER_DAY }}")` is constructed
- **THEN** the model is valid with `seconds="{{ SECONDS_PER_DAY }}"`

#### Scenario: Multiple constraints are AND-ed

- **WHEN** `Cooldown(ticks=5, seconds=3600)` is set on an adventure and the player has completed it 6 ticks ago but only 1800 seconds ago
- **THEN** the adventure is not eligible (seconds constraint not satisfied)

---

### Requirement: Template constants for time expressions

The template rendering context SHALL include the following integer constants accessible in any template expression, including cooldown field strings:

- `SECONDS_PER_MINUTE = 60`
- `SECONDS_PER_HOUR = 3600`
- `SECONDS_PER_DAY = 86400`
- `SECONDS_PER_WEEK = 604800`

These constants SHALL be part of `SAFE_GLOBALS` in `oscilla/engine/templates.py` and SHALL be available in all template evaluation contexts, not just text narratives.

#### Scenario: SECONDS_PER_DAY available in cooldown template

- **WHEN** a skill declares `cooldown: seconds: "{{ SECONDS_PER_DAY }}"` and the template is evaluated
- **THEN** the result is 86400

#### Scenario: Template constant available in narrative text

- **WHEN** a narrative step uses `{{ SECONDS_PER_HOUR / 60 }}` in its text
- **THEN** the text renders with value 60.0 (or similar numeric output)

#### Scenario: Constants are available at load-time mock validation

- **WHEN** a template containing `SECONDS_PER_DAY` is validated at content load time
- **THEN** no load error is raised
