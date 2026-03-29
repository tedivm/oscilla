## Why

The game engine runs entirely in memory with no way to save or resume a character's progress. Every session starts from scratch, making it unsuitable for real play. Persistence is the foundational capability that makes Oscilla a usable game rather than a demo.

## What Changes

- Rename existing engine identifiers that use "player" to use "character" throughout: `PlayerState` → `CharacterState`, `PlayerStatistics` → `CharacterStatistics`, `new_player()` → `new_character()`, and `oscilla/engine/player.py` → `oscilla/engine/character.py`
- Introduce `users`, `characters`, and `character_iterations` tables via SQLAlchemy ORM and a first Alembic migration; all per-run state (stats, inventory, milestones, xp, level, etc.) lives in `character_iterations` so each prestige run accumulates as a separate, preserved row — enabling aggregate lifetime stats without data loss
- Add `to_dict()` / `from_dict()` serialization to `CharacterState` with content-drift resilience (new stats get defaults, removed stats are dropped)
- Wire an event-tagged `PersistCallback` protocol into `AdventurePipeline` for mid-adventure checkpointing (`step_start`, `combat_round`, `adventure_end`)
- Introduce a `GameSession` orchestrator (`oscilla/engine/session.py`) that owns the DB session, content registry, character state, and save lifecycle for the TUI
- Add a persistence service layer (`oscilla/services/character.py`) with `save_character()` / `load_character()` functions using optimistic locking (`version` column)
- Auto-derive the SQLite database path from `content_path.parent / "saves.db"` in `Settings` when `DATABASE_URL` is not explicitly set
- Lazy-create a TUI user identity from `USER@hostname`; support `--character-name` CLI flag to address a specific character
- Character selection menu on TUI startup when the user has multiple characters; `[+] New Character` option always present

## Capabilities

### New Capabilities

- `player-persistence`: Save and load character state (`CharacterState`) to/from a relational database (SQLite or PostgreSQL), with prestige-aware iteration history, mid-adventure checkpointing, optimistic locking, content-drift resilience, and character selection for both TUI and web contexts.
- `user-identity`: Resolve a stable user identity for the TUI from system environment variables (`USER@hostname`) with CLI override, and model it as a `users` table row with a `user_key` unique key.
- `game-session`: A `GameSession` orchestrator that ties content loading, character state, database persistence, and adventure pipeline execution together for the TUI game loop.

### Modified Capabilities

- `adventure-pipeline`: The pipeline gains an optional `on_state_change` `PersistCallback` parameter. The callback signature and event taxonomy (`step_start`, `combat_round`, `adventure_end`) are a new requirement on the pipeline contract.
- `cli-game-loop`: The TUI startup sequence gains user identity resolution, character selection or creation, and session lifecycle management as required behavior.

## Impact

- **New dependencies**: `aiosqlite` (already remapped in `services/db.py`), `asyncpg` (already remapped) — both implied by existing code; no new packages needed for core persistence
- **`oscilla/models/`**: New `character.py` (`CharacterRecord` identity model and `CharacterIterationRecord` per-run model) and `user.py` (`UserRecord`)
- **`oscilla/engine/player.py`** → **`oscilla/engine/character.py`**: renamed; `PlayerState` → `CharacterState`, `PlayerStatistics` → `CharacterStatistics`, `new_player()` → `new_character()`; `CharacterState` gains serialization methods
- **`tests/engine/test_player.py`** → **`tests/engine/test_character.py`**: renamed to match source module
- **`oscilla/engine/pipeline.py`**: Optional `PersistCallback` parameter added
- **`oscilla/engine/session.py`**: New file — `GameSession` class
- **`oscilla/services/character.py`**: New file — character persistence service functions
- **`oscilla/conf/settings.py`** / **`oscilla/conf/db.py`**: Auto-derive SQLite URL from content path
- **`db/versions/`**: First Alembic migration (`users`, `characters`, and `character_iterations` tables)
- **`oscilla/cli.py`**: `--character-name` flag, character select/create flow
