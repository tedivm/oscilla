## Why

The engine hard-codes a single game per content directory, making it impossible for a single installation to host multiple games or for developers to switch between them without swapping `CONTENT_PATH`. Developers also lack a structured sandbox for manually exercising engine features — narrative branches, stat mutations, combat difficulty, condition gates — without relying on The Kingdom's story content.

## What Changes

- **BREAKING** `CONTENT_PATH` is replaced by `GAMES_PATH` and now points to a *game library root* — a directory whose immediate subdirectories are individual game packages. The existing `content/` directory is restructured accordingly.
- **BREAKING** `CharacterRecord` gains a `game_name` column; the uniqueness constraint changes from `(user_id, name)` to `(user_id, game_name, name)`. A migration is required.
- `oscilla game` gains a `--game GAME_NAME` flag. When multiple games are present and no flag is given, a TUI game-selection screen is shown before character selection.
- `oscilla validate` validates all games by default; a new `--game` flag restricts it to one.
- `--reset-db` deletes characters scoped to the selected game only.
- Two new adventure effects are added: `stat_change` (numeric delta) and `stat_set` (assign any typed value). Both are validated against `CharacterConfig` at content load time.
- `add_xp()` grows level-down support: negative XP drains levels, HP is capped at the new `max_hp`, and XP is clamped at 0 (level 1 is the floor). Returns a tuple of `(levels_gained, levels_lost)`.
- A new developer game, **Testlandia**, is added under `content/testlandia/`. It exercises every engine feature across structured test realms with a stress-test `CharacterConfig` covering `int`, `float`, `bool`, and null-default `str` stat types.
- A `ROADMAP.md` entry is added to flag integer overflow / underflow as a future hardening concern.

## Capabilities

### New Capabilities

- `multi-game-library`: Content directory is a library of named game packages. The loader scans subdirectories, and the CLI presents a game-selection screen when multiple games are present. `GAMES_PATH` replaces `CONTENT_PATH`.
- `stat-mutation-effects`: Two new adventure effect types — `stat_change` (delta on int/float stats) and `stat_set` (absolute assignment for any typed stat) — validated against `CharacterConfig` at load time.
- `level-down`: `add_xp()` supports negative deltas that can reduce level and `max_hp`. XP is clamped at 0; level 1 is the floor. The effects dispatcher reports de-level events to the TUI.
- `testlandia`: Developer sandbox game package with realms covering character manipulation, combat, condition gates, narrative choices, and item operations.

### Modified Capabilities

- `manifest-system`: `CONTENT_PATH` setting renamed to `GAMES_PATH`; the loader now scans a game library root rather than a single game root.
- `player-persistence`: `CharacterRecord` gains `game_name`; uniqueness and all service queries become game-scoped.
- `cli-game-loop`: `game` command gains `--game` flag and game-selection TUI screen; `validate` gains `--game` flag; `--reset-db` becomes game-scoped.

## Impact

- **`oscilla/conf/settings.py`** — rename `content_path` → `games_path`, update default
- **`oscilla/engine/loader.py`** — new `load_games(path)` function; single-game `load()` retained for internal use
- **`oscilla/engine/character.py`** — `add_xp()` return type changes; level-down loop added
- **`oscilla/engine/steps/effects.py`** — `stat_change` / `stat_set` handlers; de-level TUI messages
- **`oscilla/engine/models/adventure.py`** — `StatChangeEffect` and `StatSetEffect` Pydantic models
- **`oscilla/models/character.py`** — add `game_name` column, update unique constraint
- **`oscilla/services/character.py`** — all queries gain `game_name` parameter
- **`oscilla/cli.py`** — `--game` flag, game-selection screen, updated `validate`
- **`oscilla/engine/tui.py`** — new `GameSelectScreen`
- **`db/versions/`** — new Alembic migration
- **`content/`** — restructured into `content/the-kingdom/` and `content/testlandia/`
- **`ROADMAP.md`** — new file noting integer overflow hardening as a future concern
