## Why

The engine currently hardcodes HP growth, level advancement, and XP thresholds as fixed integers in `game.yaml`, forcing all games into a single progression model and violating the platform's design principle that the engine should never assume what kind of game is being built. Content authors cannot express non-linear XP curves, stat values derived from other stats, or variable growth, and the tight coupling between `xp_grant`, level, and `max_hp` makes it impossible to build systems like pool-based progression, levelless games, or D20-style die-roll HP gains.

## What Changes

- **BREAKING** — `HpFormula` (`base_hp`, `hp_per_level`) is removed from `game.yaml`. Initial HP and HP growth are now authored via `on_character_create` trigger adventures and `stat_change` effects.
- **BREAKING** — `xp_thresholds: List[int]` is removed from `GameSpec`. XP-to-level advancement is now authored using `on_stat_threshold` + trigger adventures.
- **BREAKING** — `xp_grant` effect is removed. Authors use `stat_change` targeting whatever stat they name as their XP equivalent.
- **BREAKING** — `CharacterState.level`, `.xp`, `.hp`, and `.max_hp` are removed as standalone hardcoded fields. Games that want these concepts declare them as stats in `character_config.yaml`.
- **BREAKING** — `player.level`, `player.hp`, and `player.max_hp` are removed from `PlayerContext`. These move to `player.stats["level"]`, `player.stats["hp"]`, etc., alongside all other author-defined stats.
- `StatDefinition` gains an optional `derived: str` field — a Jinja2 template string evaluated on read, never stored. Derived stats are read-only.
- The content loader rejects any `stat_change` or `stat_set` effect that targets a derived stat.
- Derived stats participate in the `on_stat_threshold` trigger system: after any stored stat changes, the engine re-evaluates all derived stats and fires threshold triggers for any that crossed a boundary.
- `on_stat_threshold` is extended to fire once per threshold crossed when multiple thresholds are crossed in a single stat change (multi-cross support).
- `on_level_up` built-in trigger name is removed. Games with a level system use `on_stat_threshold` entries on their `level` stat.
- New template functions added: `roll_pool(n, sides)`, `keep_highest(pool, n)`, `keep_lowest(pool, n)`, `count_successes(pool, threshold)`, `explode(pool, sides)`, `roll_fudge(n)`, `weighted_roll(options, weights)`, `d4()`, `d6()`, `d8()`, `d10()`, `d12()`, `d20()`, `d100()`, `ordinal(n)`, `signed(n)`, `stat_mod(n)`. (`lerp`, `average`, and other interpolation/statistics utilities are deferred to the Extended Template Primitives roadmap item.)
- `StatThresholdTrigger` gains an optional `fire_mode: Literal["each", "highest"]` field (default `"each"`). `each` fires once per threshold crossed in a single mutation ascending; `highest` fires only the single highest crossed threshold. Mixed modes on the same stat operate independently.
- `StatDefinition` gains an optional `stat_context: Literal["stored", "effective"]` field (default `"stored"`), applicable only when `derived` is set. `stored` sees raw stored stats only; `effective` sees `effective_stats()` including equipment bonuses and passive effects.

## Capabilities

### New Capabilities

- `derived-stats`: A stat declared with `derived:` is computed from a Jinja2 template at read time. Its value is never stored directly; the template is evaluated against the same `ExpressionContext` used by adventure templates. Derived stats participate in threshold detection — the engine tracks a shadow value to detect changes and fire triggers.
- `template-functions-extended`: New built-in functions available in all template expressions, covering dice pools, die-shorthand aliases, display helpers, and numeric utilities.

### Modified Capabilities

- `player-state`: Remove `level`, `xp`, `hp`, `max_hp` as hardcoded fields. These become author-declared stats. `prestige_count` and `name` remain as fixed fields. All existing fixed-field references in serialization and the DB layer must be updated.
- `dynamic-content-templates`: `PlayerContext` loses `player.level`, `player.hp`, `player.max_hp` as first-class attributes; they become accessible via `player.stats["level"]` etc. New template functions registered in `SAFE_GLOBALS`.
- `triggered-adventures`: `on_level_up` built-in trigger name is removed. `on_stat_threshold` gains multi-cross behavior (fires once per boundary crossed, not once per stat change). Derived stat changes are also eligible to fire `on_stat_threshold`.
- `stat-mutation-effects`: `xp_grant` effect is removed. `stat_change` and `stat_set` gain a load-time validation rule rejecting derived stats as targets.

## Impact

- `oscilla/engine/models/game.py` — remove `HpFormula`, `xp_thresholds`, update `GameSpec`
- `oscilla/engine/models/character_config.py` — add `derived: str | None` and `stat_context: "stored" | "effective"` to `StatDefinition`
- `oscilla/engine/character.py` — remove `level`, `xp`, `hp`, `max_hp` fields; remove `add_xp()`; add derived stat shadow tracking; update `new_character()`; update `to_dict()` / `from_dict()`
- `oscilla/engine/templates.py` — update `PlayerContext`; add new `SAFE_GLOBALS` functions
- `oscilla/engine/steps/effects.py` — remove `XpGrantEffect` handler; update `StatChangeEffect` / `StatSetEffect` to reject derived targets; add derived-stat re-evaluation after every stat mutation
- `oscilla/engine/loader.py` — remove `on_level_up` from allowed trigger keys; add validation rejecting writes to derived stats; extend `on_stat_threshold` to accept derived stat names
- `oscilla/engine/tui.py` — remove hardcoded `player.level`, `player.xp`, `player.hp`, `player.max_hp` reads; replace with `player.stats` lookups using engine-standard stat names
- `db/versions/` — migration to remove `level`, `xp`, `hp`, `max_hp` columns; these values move to the `stats` JSON column
- `content/testlandia/` — update `character_config.yaml` to declare `level`, `xp`, `hp`, `max_hp` as stats; update `game.yaml` to remove `hp_formula`, `xp_thresholds`; add `on_character_create` and `on_stat_threshold` trigger adventures for progression
- All existing game content and tests that reference `player.level`, `player.hp`, `player.max_hp`, or `xp_grant` must be updated

### Testlandia QA Content

Testlandia must be updated to demonstrate and validate all new capabilities:

- Declare `xp`, `level`, `hp`, `max_hp`, and `constitution` as stats in `character_config.yaml`
- Declare a `derived` stat `constitution_bonus` with formula `{{ floor((player.stats["constitution"] - 10) / 2) }}`
- Declare a `derived` stat `level` using `on_stat_threshold` thresholds for XP
- Add an `on_character_create` trigger adventure that sets starting `hp` and `max_hp`
- Add `on_stat_threshold` entries for the XP stat that fire an `on-level-up` adventure
- The `on-level-up` adventure uses `roll_pool`, `keep_highest`, and `d8()` to compute HP gain and show the dice result in narrative text
- Add a "Stat Formula Showcase" adventure that exercises `roll_pool`, `count_successes`, `d20()`, `ordinal()`, `signed()`, and `weighted_roll()` in its narrative text so authors can see the output
- Try to trigger a `stat_change` on a derived stat via a "bad-derived-write" adventure and confirm the content loader rejects it at load time (fixture only, not wired into testlandia's game)
