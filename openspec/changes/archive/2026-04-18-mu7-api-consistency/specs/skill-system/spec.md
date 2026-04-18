## MODIFIED Requirements

### Requirement: SkillRead carries description and cooldown state

`SkillRead`, as returned by `GET /characters/{id}`, SHALL contain:

- `ref: str` — skill manifest reference
- `display_name: str | None` — human-readable skill name from the skill manifest
- `description: str | None` — skill description from the manifest; `None` when absent or empty
- `on_cooldown: bool` — `True` when `skill_tick_expiry[ref] > state.internal_ticks`; `False` otherwise
- `cooldown_remaining_ticks: int | None` — `skill_tick_expiry[ref] - state.internal_ticks` when `on_cooldown` is `True`; `None` otherwise

Real-time cooldown expiry (`skill_real_expiry`) SHALL NOT be exposed in this model.

#### Scenario: on_cooldown is true when tick expiry is in the future

- **GIVEN** a character whose skill `"fireball"` has `skill_tick_expiry["fireball"] = 100` and `internal_ticks = 80`
- **WHEN** `GET /characters/{id}` is called
- **THEN** the `SkillRead` for `"fireball"` has `on_cooldown: true` and `cooldown_remaining_ticks: 20`

#### Scenario: on_cooldown is false when no cooldown is active

- **GIVEN** a character who knows skill `"fireball"` with `skill_tick_expiry` not set for that ref
- **WHEN** `GET /characters/{id}` is called
- **THEN** the `SkillRead` for `"fireball"` has `on_cooldown: false` and `cooldown_remaining_ticks: null`

#### Scenario: on_cooldown is false when tick expiry is in the past

- **GIVEN** a character whose skill `"fireball"` has `skill_tick_expiry["fireball"] = 50` and `internal_ticks = 80`
- **WHEN** `GET /characters/{id}` is called
- **THEN** the `SkillRead` for `"fireball"` has `on_cooldown: false` and `cooldown_remaining_ticks: null`
