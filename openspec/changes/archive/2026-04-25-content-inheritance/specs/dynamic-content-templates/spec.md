# Dynamic Content Templates

## MODIFIED Requirements

### Requirement: Templates have access to a read-only ExpressionContext

Templates SHALL receive an `ExpressionContext` at render time containing a `PlayerContext` (read-only projection of `CharacterState`), an optional `CombatContextView`, a `GameContext` (read-only projection of `GameSpec`), an optional `InGameTimeView` exposed as `ingame_time`, and a `this` dict exposing the current manifest's `properties`. Templates SHALL NOT be able to mutate any field on these objects.

The `PlayerContext` SHALL expose:

- `player.name` — character name (str)
- `player.iteration` — current game iteration (int)
- `player.stats["<name>"]` — any stat from CharacterConfig, including both stored AND derived stats (dict-subscript access)
- `player.milestones.has("<name>")` — milestone membership check (bool)
- `player.pronouns.<field>` — all pronoun fields (see pronoun-system spec)

The `PlayerContext` SHALL NOT expose `player.level`, `player.hp`, or `player.max_hp` as first-class fields. Games that declare these stats in `CharacterConfig` access them via `player.stats['level']`, `player.stats['hp']`, etc.

The `GameContext` SHALL expose:

- `game.season_hemisphere` — `"northern"` or `"southern"`; defaults to `"northern"` when the game manifest does not declare it
- `game.timezone` — IANA timezone name string (e.g. `"America/New_York"`), or `None` when the game manifest does not declare a timezone

The `ingame_time` field SHALL expose an `InGameTimeView` when the game has a `time:` block configured, and `None` otherwise. Full specification of `ingame_time` properties is in the `ingame-time-templates` spec.

The `this` field SHALL expose a `Dict[str, int | float | str | bool]` populated from the current manifest's `properties` dict. When no properties are set, `this` SHALL be an empty dict.

#### Scenario: Template accesses player name

- **WHEN** `{{ player.name }}` is rendered with a `PlayerContext` where `name = "Alex"`
- **THEN** the rendered output contains `"Alex"`

#### Scenario: Template accesses a stat by name

- **WHEN** `{{ player.stats['gold'] }}` is rendered with `stats = {"gold": 150}`
- **THEN** the rendered output contains `"150"`

#### Scenario: Template accesses a nonexistent stat

- **WHEN** a manifest template accesses `player.stats['nonexistent']` and `nonexistent` is not in `CharacterConfig`
- **THEN** `load()` raises a `ContentLoadError` during mock render

#### Scenario: Template accesses an invalid player property

- **WHEN** a manifest template accesses `player.inventory` (a property not in `PlayerContext`)
- **THEN** `load()` raises a `ContentLoadError` during mock render

#### Scenario: Combat context is available inside combat steps

- **WHEN** an effect or branch inside a `CombatStep` uses `{{ combat.turn }}`
- **THEN** `load()` validates it successfully and it renders correctly at runtime

#### Scenario: Combat context is unavailable outside combat steps

- **WHEN** a `NarrativeStep` template accesses `{{ combat.enemy_hp }}`
- **THEN** `load()` raises a `ContentLoadError` identifying the non-combat context

#### Scenario: Template accesses game season_hemisphere

- **WHEN** `{{ game.season_hemisphere }}` is rendered for a game with `season_hemisphere: southern`
- **THEN** the rendered output contains `"southern"`

#### Scenario: Template accesses invalid game property

- **WHEN** a manifest template accesses `game.xp_thresholds` (a property not in `GameContext`)
- **THEN** `load()` raises a `ContentLoadError` during mock render

#### Scenario: Template accesses ingame_time when time is configured

- **WHEN** a game has a `time:` block and a template renders `{{ ingame_time.game_ticks }}`
- **THEN** the rendered output contains the current `game_ticks` value

#### Scenario: Template guards ingame_time when time is not configured

- **WHEN** a game has no `time:` block and a template contains `{% if ingame_time %}{{ ingame_time.game_ticks }}{% endif %}`
- **THEN** the block is skipped and no error is raised

#### Scenario: Template accesses this property value

- **WHEN** `{{ this.get('damage_die', 4) }}` is rendered with `this = {"damage_die": 6}`
- **THEN** the rendered output contains `"6"`

#### Scenario: Template uses this.get() default when key missing

- **WHEN** `{{ this.get('damage_die', 4) }}` is rendered with `this = {}`
- **THEN** the rendered output contains `"4"`
