# Player Persistence

## Purpose

Defines how `CharacterState` is serialized to and deserialized from a relational database, including mid-adventure checkpointing, optimistic locking, and content-drift resilience.

## ADDED Requirements

### Requirement: CharacterState is serializable to a plain dict

`CharacterState` SHALL provide a `to_dict()` method that returns a JSON-serializable `Dict[str, Any]` representation of the entire character state. All nested types (`AdventurePosition`, `CharacterStatistics`, sets, UUIDs) SHALL be converted to JSON-native types (dicts, lists, strings).

#### Scenario: Round-trip serialization

- **WHEN** `CharacterState.to_dict()` is called on a fully populated state
- **THEN** the result is a dict that can be passed to `json.dumps()` without error

---

### Requirement: CharacterState is deserializable from a dict with content-drift resilience

`CharacterState` SHALL provide a `from_dict(data, character_config)` classmethod. It SHALL reconstruct a `CharacterState` from the serialized dict, reconciling the saved `stats` bag against the current `CharacterConfigManifest`:

- Stats present in config but absent in the saved dict SHALL be added with their `default` value from the config.
- Stats present in the saved dict but absent from the current config SHALL be silently dropped and a `WARNING` logged for each dropped key.

#### Scenario: Stats match config exactly

- **WHEN** the saved dict contains exactly the stats defined in the current CharacterConfig
- **THEN** the loaded state has identical stats with no changes

#### Scenario: New stat added to config

- **WHEN** the current CharacterConfig defines a stat `"charisma"` not present in the saved dict
- **THEN** the loaded state has `stats["charisma"]` set to the stat's `default` value from the config

#### Scenario: Removed stat dropped from save

- **WHEN** the saved dict contains a stat `"luck"` that is not in the current CharacterConfig
- **THEN** the loaded state has no `"luck"` key in `stats` and a WARNING is logged

---

### Requirement: Stale active_adventure reference is cleared on load

If `active_adventure` in the saved dict references an adventure that does not exist in the provided `ContentRegistry`, the loaded `CharacterState` SHALL have `active_adventure = None` and a `WARNING` SHALL be logged identifying the missing adventure reference.

#### Scenario: Adventure ref no longer exists

- **WHEN** the saved dict has `active_adventure.adventure_ref = "goblin-cave"` and the registry has no such adventure
- **THEN** the loaded character has `active_adventure = None` and a WARNING is logged

#### Scenario: Adventure ref still valid

- **WHEN** the saved dict has `active_adventure.adventure_ref = "goblin-cave"` and that adventure exists in the registry
- **THEN** the loaded character has `active_adventure` fully restored including `step_index` and `step_state`

---

### Requirement: CharacterRecord ORM model stores character identity

A `CharacterRecord` SQLAlchemy model (`oscilla/models/character.py`) SHALL map the `characters` table — the stable identity record that persists across all prestige runs:

**Columns:**

- `id`: UUID primary key
- `user_id`: UUID FK → `users.id`, NOT NULL
- `name`: TEXT NOT NULL (unique per user — enforced by `uq_character_user_name`)
- `created_at`: DATETIME NOT NULL
- `updated_at`: DATETIME NOT NULL

A `UNIQUE(user_id, name)` database constraint (`uq_character_user_name`) prevents duplicate character names per user. There is no `version` column on `characters` — optimistic locking is only needed on the high-frequency `character_iterations` table.

---

### Requirement: CharacterIterationRecord ORM model stores per-run state

A `CharacterIterationRecord` SQLAlchemy model SHALL map the `character_iterations` table. Each row represents one prestige run. The current active run has `is_active = TRUE`; completed runs have `is_active = FALSE` and a non-null `completed_at`. A partial unique index on `(character_id) WHERE is_active = TRUE` enforces at most one active run per character. Old iteration rows are **never deleted** — they form the historical record used for aggregate stats.

**Scalar columns** on `character_iterations` (indexed, queryable):

- `id`: UUID primary key
- `character_id`: UUID FK → `characters.id`, NOT NULL
- `iteration`: INTEGER NOT NULL (0 = first run, 1 = after first prestige, …)
- `is_active`: BOOLEAN NOT NULL — TRUE for the current run; FALSE for all completed runs
- `level`: INTEGER NOT NULL DEFAULT 1
- `xp`: INTEGER NOT NULL DEFAULT 0
- `hp`: INTEGER NOT NULL
- `max_hp`: INTEGER NOT NULL
- `character_class`: TEXT, nullable
- `current_location`: TEXT, nullable
- `adventure_ref`: TEXT, nullable
- `adventure_step_index`: INTEGER, nullable
- `adventure_step_state`: JSON, nullable — the only JSON column; holds mid-step combat scratch space cleared at adventure end
- `started_at`: DATETIME NOT NULL
- `completed_at`: DATETIME, nullable
- `version`: INTEGER (optimistic lock column — managed by `version_id_col`)

Configure `__mapper_args__ = {"version_id_col": version}` on `CharacterIterationRecord`. A UNIQUE constraint on `(character_id, iteration)` and a partial unique index on `(character_id) WHERE is_active = TRUE` SHALL be defined at the database level.

**Child tables** (one row per entity, all keyed by `iteration_id` FK):

- `character_iteration_stat_values`: composite PK `(iteration_id, stat_name)`; `stat_value REAL NULL` — stored as a native numeric column; NULL for stats whose value is explicitly unset.
- `character_iteration_inventory`: composite PK `(iteration_id, item_ref)`; `quantity INTEGER NOT NULL`.
- `character_iteration_equipment`: composite PK `(iteration_id, slot)`; `item_ref TEXT NOT NULL`.
- `character_iteration_milestones`: composite PK `(iteration_id, milestone_ref)`.
- `character_iteration_quests`: composite PK `(iteration_id, quest_ref)`; `status TEXT NOT NULL` ("active" or "completed"); `stage TEXT` nullable.
- `character_iteration_statistics`: composite PK `(iteration_id, stat_type, entity_ref)`; `count INTEGER NOT NULL DEFAULT 0`. `stat_type` is one of "enemies_defeated", "locations_visited", or "adventures_completed".

All child tables SHALL have `cascade="all, delete-orphan"` on the SQLAlchemy relationship from `CharacterIterationRecord`.

#### Scenario: New character creates iteration 0

- **WHEN** `save_character(session, character_state)` is called with a character that has no existing rows
- **THEN** a new `characters` row is inserted and a `character_iterations` row is inserted with `iteration = 0` and `completed_at = NULL`, and all child rows are seeded from the state's current values

#### Scenario: Existing active iteration is updated through targeted writes

- **WHEN** `update_scalar_fields(session, iteration_id, xp=1400, level=6)` is called after an adventure
- **THEN** only the `character_iterations` row is updated (xp and level columns); the `version` column increments; no child table rows are touched
- **AND WHEN** `set_stat(session, iteration_id, "strength", 15)` is called
- **THEN** only the `character_iteration_stat_values` row for `stat_name = "strength"` is upserted

---

### Requirement: Targeted write functions update individual data domains

`oscilla/services/character.py` SHALL provide one write function per child data domain. Each function MUST write only the database rows relevant to the domain it manages — it MUST NOT re-write unrelated tables.

| Function | Write behavior |
|---|---|
| `update_scalar_fields(session, iteration_id, **fields)` | UPDATE `character_iterations` scalars; triggers `version_id_col` increment |
| `set_stat(session, iteration_id, stat_name, value)` | Upsert one `character_iteration_stat_values` row; `value` is `int \| float \| None`, stored as REAL |
| `set_inventory_item(session, iteration_id, item_ref, quantity)` | Upsert (quantity > 0) or delete (quantity == 0) one `character_iteration_inventory` row |
| `equip_item(session, iteration_id, slot, item_ref)` | Upsert one `character_iteration_equipment` row |
| `unequip_item(session, iteration_id, slot)` | Delete one `character_iteration_equipment` row if it exists |
| `add_milestone(session, iteration_id, milestone_ref)` | Idempotent insert into `character_iteration_milestones` |
| `set_quest(session, iteration_id, quest_ref, status, stage)` | Upsert one `character_iteration_quests` row |
| `increment_statistic(session, iteration_id, stat_type, entity_ref, delta=1)` | Atomic upsert-increment on `character_iteration_statistics` |
| `save_adventure_progress(session, iteration_id, adventure_ref, step_index, step_state)` | UPDATE the three adventure columns on `character_iterations`; only service function that writes `adventure_step_state` |

#### Scenario: Inventory upsert removes row when quantity reaches zero

- **WHEN** `set_inventory_item(session, iteration_id, "healing-potion", 0)` is called
- **THEN** the `character_iteration_inventory` row for `item_ref = "healing-potion"` is deleted

#### Scenario: add_milestone is idempotent

- **WHEN** `add_milestone(session, iteration_id, "found-the-map")` is called twice with the same `milestone_ref`
- **THEN** no error is raised and exactly one row exists in `character_iteration_milestones` for that `milestone_ref`

#### Scenario: increment_statistic accumulates without a read

- **WHEN** `increment_statistic(session, iteration_id, "enemies_defeated", "goblin", 3)` is called on a row that already has `count = 4`
- **THEN** the row is updated to `count = 7` atomically using `INSERT ... ON CONFLICT DO UPDATE SET count = count + excluded.count`

---

### Requirement: prestige_character() transitions to a new iteration

`prestige_character(session, character_id, character_config)` in `oscilla/services/character.py` SHALL:

1. Load the active iteration row via `WHERE character_id = X AND is_active = TRUE`.
2. Set `is_active = FALSE, completed_at = now()` on that row.
3. Count existing `character_iterations` rows for the character to derive the next `iteration` ordinal.
4. Insert a new `character_iterations` row with `iteration = count`, `is_active = TRUE`, `completed_at = NULL`, and a fresh state seeded from `character_config` defaults.

This function is defined in the service layer now but is not wired to any CLI or TUI trigger — the prestige mechanic itself belongs to a future change.

#### Scenario: Prestige preserves history

- **WHEN** `prestige_character()` is called on a character that is currently on iteration 0
- **THEN** the original `character_iterations` row has `is_active = FALSE` and a non-null `completed_at`, and the new `character_iterations` row has `iteration = 1`, `is_active = TRUE`, and `completed_at = NULL`

---

### Requirement: load_all_iterations() returns full run history

`load_all_iterations(session, character_id) -> List[CharacterIterationRecord]` in `oscilla/services/character.py` SHALL return all iteration rows for the given character ordered by `iteration ASC`. This allows callers to compute aggregate stats (total XP earned, milestone counts across all runs, per-run comparisons) without additional queries.

#### Scenario: Multiple iterations returned in order

- **WHEN** a character has completed 2 prestige runs and is currently on iteration 2
- **THEN** `load_all_iterations()` returns 3 rows in order: `iteration = 0`, `iteration = 1`, `iteration = 2`

---

### Requirement: Optimistic locking prevents silent overwrites on scalar writes

The `character_iterations` table SHALL use a `version` integer column managed by SQLAlchemy's `version_id_col` mapper argument. When two concurrent sessions both attempt to call `update_scalar_fields()` or `save_adventure_progress()` against the same active iteration row, the second write SHALL raise a `StaleDataError`. The caller SHALL reload the iteration from DB and retry.

Child table upserts (`set_stat()`, `set_inventory_item()`, etc.) are idempotent by composite PK via `INSERT ... ON CONFLICT DO UPDATE` and do not go through `version_id_col`.

#### Scenario: Concurrent scalar write raises StaleDataError

- **WHEN** session A and session B both load the active iteration row with `version = 5`, session A calls `update_scalar_fields()` (row is now `version = 6`), then session B calls `update_scalar_fields()`
- **THEN** session B's write raises `StaleDataError`

---

### Requirement: Session soft-lock detects and recovers from dead processes

`character_iterations` SHALL have one nullable column: `session_token TEXT`. `acquire_session_lock(session, iteration_id, token)` in `oscilla/services/character.py` SHALL always succeed and SHALL:

1. **Free lock** — `session_token IS NULL`: write `session_token = token`.
2. **Prior session died** — `session_token` is non-NULL: log a `WARNING` naming the old token, clear `adventure_ref`, `adventure_step_index`, and `adventure_step_state` to `NULL`, then set `session_token = token`.

`acquire_session_lock()` SHALL never raise an exception or block a new session from starting.

`release_session_lock(session, iteration_id, token)` SHALL set `session_token = NULL` conditionally on `session_token = token` using a raw `UPDATE` (not an ORM load, so it does not touch `version_id_col`).

`GameSession` SHALL use `async with GameSession(...) as session:` semantics: `__aexit__` MUST call `close()` which calls `release_session_lock()`.

#### Scenario: Clean lock acquisition

- **WHEN** no session currently holds the lock (`session_token IS NULL`) for the active iteration
- **THEN** `acquire_session_lock()` sets `session_token` and returns without error

#### Scenario: Dead-process lock is stolen and adventure state is cleared

- **WHEN** `session_token` is non-NULL (simulating a process that died without releasing the lock)
- **THEN** `acquire_session_lock()` overwrites `session_token` with the new token, sets `adventure_ref = NULL`, `adventure_step_index = NULL`, `adventure_step_state = NULL`, and logs a `WARNING` containing the old token

#### Scenario: Release is a no-op after lock is stolen

- **WHEN** `release_session_lock()` is called with a token that no longer matches `session_token` (lock was taken by a newer session)
- **THEN** zero rows are updated and the DB row is unaffected

---

### Requirement: SQLite WAL mode is enabled

When the database URL resolves to a SQLite file, the engine SHALL execute `PRAGMA journal_mode=WAL` on connect to enable Write-Ahead Logging and allow concurrent readers alongside writers.

#### Scenario: WAL pragma fires on SQLite connection

- **WHEN** the async engine connects to a SQLite database
- **THEN** `PRAGMA journal_mode=WAL` is executed before any ORM operation

---

### Requirement: SQLite database path is auto-derived from content_path

When `DATABASE_URL` is not set in the environment, `DatabaseSettings` SHALL compute the database URL as `sqlite+aiosqlite:///<content_path.parent>/saves.db` in a `@model_validator(mode="after")`. If `DATABASE_URL` is explicitly set, it SHALL take precedence without modification.

#### Scenario: No DATABASE_URL set

- **WHEN** `DATABASE_URL` env var is not set and `content_path` is `/home/user/my-game/content`
- **THEN** `settings.database_url` equals `sqlite+aiosqlite:////home/user/my-game/saves.db`

#### Scenario: DATABASE_URL explicitly set

- **WHEN** `DATABASE_URL` env var is `postgresql+asyncpg://localhost/oscilla`
- **THEN** `settings.database_url` equals `postgresql+asyncpg://localhost/oscilla` unchanged
