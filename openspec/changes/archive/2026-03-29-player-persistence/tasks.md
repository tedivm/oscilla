## 0. Rename Existing Engine Identifiers

- [x] 0.1 Use `git mv oscilla/engine/player.py oscilla/engine/character.py` to rename the source module
- [x] 0.2 Rename `PlayerState` → `CharacterState` throughout the codebase (class definition and all import sites)
- [x] 0.3 Rename `PlayerStatistics` → `CharacterStatistics` throughout the codebase
- [x] 0.4 Rename `new_player()` classmethod → `new_character()` on `CharacterState`
- [x] 0.5 Update all import statements across `oscilla/engine/`, `oscilla/services/`, and `oscilla/cli.py` to use `oscilla.engine.character` and the new class names
- [x] 0.6 Use `git mv tests/engine/test_player.py tests/engine/test_character.py` to rename the test module
- [x] 0.7 Update all references inside `tests/` to use `CharacterState`, `CharacterStatistics`, and `new_character()`
- [x] 0.8 Run `make tests` to confirm all existing tests pass after the renames before proceeding
- [x] 0.9 Rename `prestige_count` → `iteration` on `CharacterState` (maps to `character_iterations.iteration` in the DB); update `to_dict()` / `from_dict()` keys accordingly

## 1. Database Schema and Migrations

- [x] 1.1 Add `UserRecord` ORM model (`oscilla/models/user.py`) with `id`, `user_key`, `created_at` columns
- [x] 1.2 Add `CharacterRecord` ORM model (`oscilla/models/character.py`) with identity-only columns: `id`, `user_id` (NOT NULL FK → users), `name`, `created_at`, `updated_at`; add `UNIQUE(user_id, name)` constraint as `uq_character_user_name` via `__table_args__`
- [x] 1.3 Add `CharacterIterationRecord` ORM model in `oscilla/models/character_iteration.py` mapping the `character_iterations` table: `id`, `character_id` (FK → characters), `iteration` (INTEGER — 0-based prestige run number), `is_active` (BOOLEAN NOT NULL — TRUE for the current run), scalar run columns (`level`, `xp`, `hp`, `max_hp`, `character_class`, `current_location`), active adventure scalars (`adventure_ref`, `adventure_step_index`), `adventure_step_state` (JSON nullable — only remaining JSON column), `started_at`, `completed_at` (nullable — set when run ends), `version`, `session_token` (TEXT nullable); configure `__mapper_args__ = {"version_id_col": version}`, UNIQUE constraint on `(character_id, iteration)`, and a partial unique index on `(character_id) WHERE is_active = TRUE`
- [x] 1.4 Add `CharacterIterationStatValue` ORM model in the same file: composite PK `(iteration_id FK, stat_name TEXT)`; `stat_value REAL NULL` (stored as a native numeric column; NULL for explicitly unset stats); `relationship` back to `CharacterIterationRecord.stat_values`
- [x] 1.5 Add `CharacterIterationInventory` model: composite PK `(iteration_id FK, item_ref TEXT)`; `quantity INTEGER NOT NULL`; relationship back to `inventory_rows`
- [x] 1.6 Add `CharacterIterationEquipment` model: composite PK `(iteration_id FK, slot TEXT)`; `item_ref TEXT NOT NULL`; relationship back to `equipment_rows`
- [x] 1.7 Add `CharacterIterationMilestone` model: composite PK `(iteration_id FK, milestone_ref TEXT)`; relationship back to `milestone_rows`
- [x] 1.8 Add `CharacterIterationQuest` model: composite PK `(iteration_id FK, quest_ref TEXT)`; `status TEXT NOT NULL` ("active"|"completed"); `stage TEXT` nullable; relationship back to `quest_rows`
- [x] 1.9 Add `CharacterIterationStatistic` model: composite PK `(iteration_id FK, stat_type TEXT, entity_ref TEXT)`; `count INTEGER NOT NULL DEFAULT 0`; relationship back to `statistic_rows`
- [x] 1.10 Run `make create_migration MESSAGE="add persistence schema"` to autogenerate the first Alembic migration
- [x] 1.11 Review and verify the generated migration handles both SQLite and PostgreSQL correctly (all nine tables: `users`, `characters`, `character_iterations`, and the six `character_iteration_*` child tables; composite PKs on child tables; UNIQUE constraint on `character_iterations(character_id, iteration)`; partial unique index on `character_iterations(character_id) WHERE is_active = TRUE`; nullable `session_token` column on `character_iterations`)
- [x] 1.12 Run `make run_migrations` to apply the migration to the development database
- [x] 1.13 Run `make document_schema` to regenerate the database schema documentation in `docs/dev/database.md`

## 2. Settings — Auto-Derive SQLite URL

- [x] 2.1 Change `database_url` field in `DatabaseSettings` (`oscilla/conf/db.py`) to `str | None` with default `None`
- [x] 2.2 Add a `@model_validator(mode="after")` to `DatabaseSettings` that sets `database_url` to `sqlite+aiosqlite:///<content_path.parent>/saves.db` when the field is `None`
- [x] 2.3 Move `content_path` into `DatabaseSettings` (or adjust so the validator can access it) — or move the validator to the combined `Settings` class where both fields are available
- [x] 2.4 Update `db/env.py` (Alembic) to use the same auto-derive logic so `make create_migration` generates against the correct SQLite path
- [x] 2.5 Enable SQLite WAL mode in `oscilla/services/db.py` by adding an `@event.listens_for(engine.sync_engine, "connect")` hook that executes `PRAGMA journal_mode=WAL` for SQLite connections

## 3. CharacterState Serialization

- [x] 3.1 Add `to_dict() -> Dict[str, Any]` method to `CharacterState` that serializes all fields to JSON-native types (UUIDs as strings, sets as lists, nested dataclasses as dicts)
- [x] 3.2 Add `from_dict(data: Dict[str, Any], character_config: CharacterConfigManifest, registry: ContentRegistry | None = None) -> CharacterState` classmethod to `CharacterState`
- [x] 3.3 Implement content-drift resilience in `from_dict()`: add missing stats with defaults, drop unknown stats with `logger.warning`
- [x] 3.4 Implement stale adventure ref detection in `from_dict()`: if `registry` is provided and `active_adventure.adventure_ref` is not in the registry, set `active_adventure = None` and log a `WARNING`

## 4. Persistence Service Layer

- [x] 4.1 Create `oscilla/services/user.py` with `derive_tui_user_key() -> str` and `get_or_create_user(session, user_key) -> UserRecord`
- [x] 4.2 Create `oscilla/services/character.py` with `save_character(session, character_state) -> None` — initial INSERT only; creates `CharacterRecord`, `CharacterIterationRecord` at `iteration = 0`, and seeds all child rows from state values; raises `IntegrityError` if character already exists
- [x] 4.3 Add `load_character(session, character_id, character_config, registry=None) -> CharacterState | None` to `oscilla/services/character.py`; eagerly load all six child table relationships; delegate content-drift resolution to `CharacterState.from_dict()`
- [x] 4.4 Add `list_characters_for_user(session, user_id) -> List[CharacterRecord]` to `oscilla/services/character.py`, ordered by `updated_at DESC`
- [x] 4.5 Add `get_character_by_name(session, user_id, name) -> CharacterRecord | None` to `oscilla/services/character.py`
- [x] 4.6 Add `prestige_character(session, character_id, character_config) -> CharacterIterationRecord` to `oscilla/services/character.py`: load the active iteration via `WHERE character_id = X AND is_active = TRUE`, set `is_active = FALSE, completed_at = now()` on that row, count existing iterations to derive the new ordinal, then insert a new `CharacterIterationRecord` with `iteration = count`, `is_active = TRUE`, `completed_at = NULL`, and fresh child rows seeded from `character_config` defaults
- [x] 4.7 Add `load_all_iterations(session, character_id) -> List[CharacterIterationRecord]` to `oscilla/services/character.py`, ordered by `iteration ASC`
- [x] 4.8 Add `update_scalar_fields(session, iteration_id, **fields) -> None`: load the `CharacterIterationRecord` ORM object, apply `**fields` as attribute assignments, commit (triggers `version_id_col` increment)
- [x] 4.9 Add `set_stat(session, iteration_id, stat_name, value: int | float | None) -> None`: upsert one `character_iteration_stat_values` row; store `value` directly as REAL (no encoding)
- [x] 4.10 Add `set_inventory_item(session, iteration_id, item_ref, quantity) -> None`: upsert (quantity > 0) or delete (quantity == 0) one `character_iteration_inventory` row using `INSERT ... ON CONFLICT DO UPDATE`
- [x] 4.11 Add `equip_item(session, iteration_id, slot, item_ref) -> None` and `unequip_item(session, iteration_id, slot) -> None`: upsert or delete one `character_iteration_equipment` row
- [x] 4.12 Add `add_milestone(session, iteration_id, milestone_ref) -> None`: idempotent insert into `character_iteration_milestones` using `INSERT ... ON CONFLICT DO NOTHING`
- [x] 4.13 Add `set_quest(session, iteration_id, quest_ref, status, stage=None) -> None`: upsert one `character_iteration_quests` row
- [x] 4.14 Add `increment_statistic(session, iteration_id, stat_type, entity_ref, delta=1) -> None`: atomic upsert-increment using `INSERT ... ON CONFLICT DO UPDATE SET count = count + excluded.count`
- [x] 4.15 Add `save_adventure_progress(session, iteration_id, adventure_ref, step_index, step_state) -> None`: update the three adventure columns on `character_iterations` using `update_scalar_fields()` (the only function that writes `adventure_step_state`)
- [x] 4.16 Add `acquire_session_lock(session, iteration_id, token) -> None`: always succeeds; free lock (NULL) → set token; non-NULL token → log WARNING, clear adventure columns, set token
- [x] 4.17 Add `release_session_lock(session, iteration_id, token) -> None`: set `session_token = NULL` conditionally on `session_token = token` using a raw `UPDATE` to avoid touching `version_id_col`

## 5. PersistCallback Protocol and Pipeline Integration

- [x] 5.1 Define `PersistCallback` Protocol in `oscilla/engine/pipeline.py` with the event-tagged async signature
- [x] 5.2 Add `on_state_change: PersistCallback | None = None` parameter to `AdventurePipeline.__init__`
- [x] 5.3 Add helper `_checkpoint(event)` async method to `AdventurePipeline` that calls `on_state_change` if not None
- [x] 5.4 Call `_checkpoint("step_start")` before each step dispatch in the pipeline loop
- [x] 5.5 Call `_checkpoint("combat_round")` after each combat round resolution in `run_combat`
- [x] 5.6 Call `_checkpoint("adventure_end")` after all outcome effects are applied and `active_adventure` is set to `None`, before `run()` returns

## 6. GameSession Orchestrator

- [x] 6.1 Create `oscilla/engine/session.py` with `GameSession` class holding `registry`, `character`, `db_session`, and `tui` references
- [x] 6.2 Implement `GameSession.start()`: derive user key, get-or-create user, run character selection logic (0 → create, 1 → auto-load, N → menu)
- [x] 6.3 Implement character selection menu via `TUICallbacks` with character name, level, class, last-played, and `[+] New Character` option
- [x] 6.4 Implement `GameSession._create_new_character(name: str | None)`: use provided name or prompt via TUI, call `CharacterState.new_character()`, save immediately
- [x] 6.5 Implement `GameSession._on_state_change(state, event)` as the `PersistCallback` implementation: hold `_last_saved_state: CharacterState | None`; diff incoming state against snapshot; call only the targeted write functions for changed domains; snapshot state after successful writes; handle `StaleDataError` with one reload-and-retry
- [x] 6.6 Implement `GameSession.run_adventure(adventure_ref)` that builds `AdventurePipeline` with `self._on_state_change` as the callback and runs it
- [x] 6.7 Handle `--character-name` filtering in `start()`: if name matches existing character auto-load it; if no match create a new character with that name
- [x] 6.8 Add `_session_token: str = str(uuid4())` and `_iteration_id: UUID | None` to `GameSession.__init__`
- [x] 6.9 In `GameSession.start()`, after loading or creating the character, call `acquire_session_lock(session, iteration_id, self._session_token)`
- [x] 6.10 Implement `GameSession.close()`: call `release_session_lock()` if `_iteration_id` is set; wire into `__aenter__`/`__aexit__` so the CLI uses `async with GameSession(...) as session:` to guarantee cleanup on exception

## 7. CLI Integration

- [x] 7.1 Add `--character-name: str | None` option to the `oscilla game` Typer command
- [x] 7.2 Update the `game` command to instantiate `GameSession`, call `start()`, and pass `character_name` through
- [x] 7.3 Remove the `new_player()` in-memory initialization from the current CLI game command
- [x] 7.4 Ensure the `game` command uses `@syncify` to wrap the async `GameSession.start()` and game loop

## 8. Unit Tests — Serialization

- [x] 8.1 Create `tests/engine/test_character_persistence.py`
- [x] 8.2 Test `CharacterState.to_dict()` round-trips all fields without error
- [x] 8.3 Test `from_dict()` with matching config produces identical state
- [x] 8.4 Test `from_dict()` with new stat in config injects default value
- [x] 8.5 Test `from_dict()` with removed stat drops the key and logs a WARNING
- [x] 8.6 Test `from_dict()` with unknown `active_adventure.adventure_ref` clears the adventure and logs a WARNING

## 9. Unit Tests — Pipeline Persistence

- [x] 9.1 Create `tests/engine/test_pipeline_persist.py`
- [x] 9.2 Test that pipeline with `on_state_change=None` runs to completion without error
- [x] 9.3 Test that `step_start` callback fires before each step dispatch
- [x] 9.4 Test that `combat_round` callback fires after each combat round
- [x] 9.5 Test that `adventure_end` callback fires once after effects are applied and `active_adventure` is None

## 10. Service/Integration Tests

- [x] 10.1 Create `tests/services/test_user_service.py`
- [x] 10.2 Test `derive_tui_user_key()` returns `USER@hostname` format; test fallback to LOGNAME and to "unknown"
- [x] 10.3 Test `get_or_create_user()` creates on first call and returns the same row on second call
- [x] 10.4 Create `tests/services/test_character_service.py`
- [x] 10.5 Test `save_character()` inserts a new row on first call
- [x] 10.6 Test that calling `save_character()` a second time for the same `character_id` raises `IntegrityError`
- [x] 10.7 Test `load_character()` returns `None` for unknown `character_id`
- [x] 10.8 Test `load_character()` returns a `CharacterState` matching what was saved
- [x] 10.9 Test that manually bumping the `version` column before a second save raises `StaleDataError`
- [x] 10.10 Add an `async_session` test fixture using `sqlite+aiosqlite:///:memory:` with all migrations applied
- [x] 10.11 Test `prestige_character()` flips `is_active = FALSE` on the old iteration, sets `completed_at`, inserts a new iteration row with `is_active = TRUE` and the correct ordinal
- [x] 10.12 Test `load_all_iterations()` returns all iteration rows in `iteration ASC` order, including both completed and active rows
- [x] 10.13 Test `acquire_session_lock()` acquires a free lock (token is NULL) and sets `session_token`
- [x] 10.14 Test `acquire_session_lock()` steals a non-NULL token (dead process), clears adventure columns, and logs a WARNING
- [x] 10.15 Test `release_session_lock()` clears the lock when token matches; is a no-op when token does not match

- [x] 11.1 Create `tests/engine/test_game_session.py`
- [x] 11.2 Test `GameSession.start()` with no existing characters creates a user and character row
- [x] 11.3 Test `GameSession.start()` with one existing character auto-loads it
- [x] 11.4 Test `GameSession.start()` with multiple existing characters invokes the character selection callback
- [x] 11.5 Test `GameSession.run_adventure()` triggers DB saves at `step_start`, `combat_round`, and `adventure_end`
- [x] 11.6 Test crash recovery: seed DB with `active_adventure` mid-step; `start()` loads it correctly including `step_state`
- [x] 11.7 Test `StaleDataError` in `_on_state_change()` triggers one reload-and-retry and ultimately saves

## 12. Documentation

- [x] 12.1 Update `docs/dev/database.md` with schema overview (all nine tables: `users`, `characters`, `character_iterations`, and the six `character_iteration_*` child tables), column layout rationale, iteration model and prestige lifecycle, child table design, migration workflow, optimistic locking, and SQLite WAL mode
- [x] 12.2 Update `docs/dev/game-engine.md` with `GameSession` class description, `PersistCallback` protocol, save event taxonomy, and content-drift resilience behaviour
- [x] 12.3 Update `docs/dev/settings.md` with auto-derive SQLite URL behaviour, `DATABASE_URL` override, and TUI vs web configuration differences
- [x] 12.4 Update `docs/dev/cli.md` with `--character-name` flag, character selection flow, and user identity derivation
