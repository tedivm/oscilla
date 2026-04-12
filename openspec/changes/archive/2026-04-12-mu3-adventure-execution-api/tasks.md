## 1. Settings

- [x] 1.1 Add `stale_session_threshold_minutes: int = Field(default=10, description="Minutes after which a web session lock is considered stale and eligible for takeover.")` to the `Settings` class in `oscilla/conf/settings.py` under the existing `# Auth` block; add `STALE_SESSION_THRESHOLD_MINUTES=10` with an inline comment to `.env.example`; run `make tests` to confirm all checks pass

## 2. `TUICallbacks` → `UICallbacks` Protocol Rename

- [x] 2.1 In `oscilla/engine/pipeline.py`: rename the `TUICallbacks` Protocol class to `UICallbacks`; update the module docstring comment that references `TUICallbacks`; update the `tui: TUICallbacks` type hint in `AdventurePipeline.__init__` to `tui: UICallbacks`

- [x] 2.2 Update every import site of `TUICallbacks` to import `UICallbacks` instead, and update every `tui: TUICallbacks` parameter annotation — files: `oscilla/engine/steps/choice.py`, `oscilla/engine/steps/combat.py`, `oscilla/engine/steps/effects.py`, `oscilla/engine/steps/narrative.py`, `oscilla/engine/steps/passive.py`, `oscilla/engine/quest_engine.py`, `oscilla/engine/session.py`, `oscilla/engine/actions.py`

- [x] 2.3 In `tests/engine/conftest.py`: update the `MockTUI` class docstring and any `TUICallbacks` type-hint reference to use `UICallbacks`; verify no file in the project still contains the string `TUICallbacks` (outside archive directories)

- [x] 2.4 Run `make mypy_check` and confirm zero type errors; run `make pytest` and confirm all existing engine tests continue to pass

## 3. DB Migration — `session_token_acquired_at`

- [x] 3.1 Add `session_token_acquired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)` to `CharacterIterationRecord` in `oscilla/models/character_iteration.py` immediately after the existing `session_token` column; add `datetime` to imports if not already present

- [x] 3.2 Run `make create_migration MESSAGE="add session_token_acquired_at to character_iterations"` and verify the generated migration under `db/versions/` adds one nullable `DateTime(timezone=True)` column to `character_iterations` in `upgrade()` and drops it in `downgrade()`; run `make check_ungenerated_migrations` to confirm clean state; run `make document_schema` to update `docs/dev/database.md`

## 4. DB Model + Migration — `character_session_output`

- [x] 4.1 Create `oscilla/models/character_session_output.py` with `CharacterSessionOutputRecord` exactly as specified in `design.md`: table `character_session_output`, columns `id` (UUID PK, default uuid4), `iteration_id` (UUID FK → `character_iterations.id`, not null, indexed), `position` (Integer, not null), `event_type` (String, not null), `content_json` (JSON, not null), `created_at` (DateTime timezone=True, not null, default `datetime.now(tz=timezone.utc)`); include module docstring explaining the crash-recovery purpose

- [x] 4.2 Import `CharacterSessionOutputRecord` in `oscilla/models/__init__.py` (or whichever aggregation module Alembic's `env.py` uses to discover models) so autogenerate picks it up

- [x] 4.3 Run `make create_migration MESSAGE="add character_session_output table"` and verify the generated migration creates the `character_session_output` table with an index on `iteration_id` and a foreign key to `character_iterations` in `upgrade()` and drops it in `downgrade()`; run `make check_ungenerated_migrations`; run `make document_schema`

## 5. Service Functions — Web Session Locking and Session Output

- [x] 5.1 In `oscilla/services/character.py`, add `acquire_web_session_lock(session: AsyncSession, iteration_id: UUID, token: str, stale_threshold_minutes: int) -> datetime | None` immediately below the existing `release_session_lock` function: select the `CharacterIterationRecord` by `iteration_id`; if `session_token` is not None AND (`session_token_acquired_at` is None OR `now - session_token_acquired_at < timedelta(minutes=stale_threshold_minutes)`), return `session_token_acquired_at` (or `datetime.now(tz=timezone.utc)` as fallback if `acquired_at` is None) — the caller should respond with 409; otherwise (lock is free or stale) set `session_token = token` and `session_token_acquired_at = datetime.now(tz=timezone.utc)`, commit, and return `None`

- [x] 5.2 Add `release_web_session_lock(session: AsyncSession, iteration_id: UUID, token: str) -> None`: raw UPDATE on `CharacterIterationRecord` setting `session_token = NULL` and `session_token_acquired_at = NULL` WHERE `id == iteration_id AND session_token == token`; commit; no-op if token does not match (same safety as existing `release_session_lock`)

- [x] 5.3 Add `force_acquire_web_session_lock(session: AsyncSession, iteration_id: UUID, token: str) -> None`: unconditionally acquires the lock — select the iteration, log WARNING naming the prior token if non-null, clear `adventure_ref`, `adventure_step_index`, `adventure_step_state` (orphan protection), set `session_token = token` and `session_token_acquired_at = datetime.now(tz=timezone.utc)`, commit

- [x] 5.4 Add `save_session_output(session: AsyncSession, iteration_id: UUID, events: List[Dict[str, Any]]) -> None` in `oscilla/services/character.py`: first DELETE all existing rows where `iteration_id == iteration_id` (full replace), then INSERT one `CharacterSessionOutputRecord` per event with `position` = 0-based index, `event_type` = `event["type"]`, `content_json` = the full event dict; commit

- [x] 5.5 Add `get_session_output(session: AsyncSession, iteration_id: UUID) -> List[Dict[str, Any]]`: SELECT all `CharacterSessionOutputRecord` WHERE `iteration_id == iteration_id` ORDER BY `position` ASC; return `[row.content_json for row in rows]`

- [x] 5.6 Add `clear_session_output(session: AsyncSession, iteration_id: UUID) -> None`: DELETE all rows in `character_session_output` WHERE `iteration_id == iteration_id`; commit

- [x] 5.7 Add unit tests in `tests/services/test_character_session.py` (create file): (a) `acquire_web_session_lock` returns `None` when no lock held and writes token + acquired_at; (b) returns datetime when a live session exists (within threshold); (c) returns `None` and overwrites when a stale session exists (beyond threshold); (d) `release_web_session_lock` clears both columns when token matches; (e) `release_web_session_lock` is a no-op when token does not match; (f) `force_acquire_web_session_lock` unconditionally acquires and clears adventure state; (g) `save_session_output` / `get_session_output` round-trip preserves order and content; (h) `clear_session_output` removes all rows for the iteration

## 6. `WebCallbacks` Implementation

- [x] 6.1 Create `oscilla/engine/web_callbacks.py` with `DecisionPauseException` and `WebCallbacks` exactly as specified in `design.md` D2 and D3, including: the class docstring, `asyncio.Queue`-backed event buffer, `_session_output` accumulator, `_context` dict, the four optional resume-input parameters (`player_choice`, `player_ack`, `player_text_input`, `player_skill_choice`), `show_text`, `show_menu`, `wait_for_ack`, `show_combat_round`, `input_text`, `show_skill_menu` methods, `session_output` property, and the `@property queue` accessor used by the SSE generator; import `UICallbacks` from `oscilla.engine.pipeline`; annotate `WebCallbacks` as implementing `UICallbacks`

- [x] 6.2 Create `tests/engine/test_web_callbacks.py` with unit tests: (a) `show_text` puts a `narrative` event on the queue and appends to `session_output`; (b) `show_menu` puts a `choice` event and sentinel, then raises `DecisionPauseException`; (c) `show_menu` in resume mode (player_choice set) returns the choice without putting events or raising; (d) `wait_for_ack` puts `ack_required` and sentinel, then raises; (e) `wait_for_ack` in resume mode (player_ack=True) returns without pausing; (f) `input_text` puts `text_input` and sentinel, then raises; (g) `input_text` in resume mode (player_text_input set) returns the string; (h) `show_skill_menu` puts `skill_menu` and sentinel, then raises; (i) `show_skill_menu` in resume mode returns the choice; (j) `show_combat_round` puts a `combat_state` event with correct fields; (k) `session_output` contains exactly the non-sentinel events after a sequence of calls

## 7. Adventure Execution Router (`/play/` endpoints)

- [x] 7.1 Create `oscilla/routers/play.py` with all Pydantic request/response models listed in `design.md`: `BeginAdventureRequest` (adventure_ref: str with Field description), `AdvanceRequest` (choice: int | None ge=1, ack: bool | None, text_input: str | None, skill_choice: int | None ge=1 — all optional with Field descriptions and `default=None`), `PendingStateRead` (character_id: UUID, pending_event: Dict[str, Any] | None, session_output: List[Dict[str, Any]]), `SessionConflictRead` (detail: str, acquired_at: datetime, character_id: UUID); import `get_current_user` from `oscilla.dependencies.auth` and `get_db` from `oscilla.conf.db`

- [x] 7.2 Implement `GET /characters/{character_id}/play/current` in `oscilla/routers/play.py`: ownership check (404 if not owner); load active iteration_id; return `PendingStateRead` with `session_output = await get_session_output(...)` and `pending_event = session_output[-1] if session_output and session_output[-1]["type"] in {"choice", "ack_required", "text_input", "skill_menu"} else None`

- [x] 7.3 Implement `POST /characters/{character_id}/play/begin` as a `StreamingResponse` returning `text/event-stream`: ownership check; call `acquire_web_session_lock`, if it returns a datetime raise `HTTPException(409, ...)` with `SessionConflictRead` body; load character state + registry; clear any existing session output; construct `WebCallbacks` with location context; construct `AdventurePipeline` from `oscilla.engine.session` with the `begin` adventure ref; call `_run_pipeline_and_stream` as defined in design D4; include `Cache-Control: no-cache` and `X-Accel-Buffering: no` headers

- [x] 7.4 Implement `POST /characters/{character_id}/play/advance` as a `StreamingResponse`: same ownership + lock flow; construct `WebCallbacks` with the request's choice/ack/text_input/skill_choice pre-loaded for the resume pattern; construct pipeline from persisted `adventure_step_index`; call `_run_pipeline_and_stream`; return 422 if no active adventure exists on the iteration

- [x] 7.5 Implement `POST /characters/{character_id}/play/abandon`: ownership check; clear `adventure_ref`, `adventure_step_index`, `adventure_step_state` via `update_scalar_fields`; call `clear_session_output`; release session lock via `release_web_session_lock`; return `204 No Content`

- [x] 7.6 Implement `POST /characters/{character_id}/play/takeover`: ownership check; call `force_acquire_web_session_lock` (always succeeds); load session output and return `PendingStateRead`; return `200 OK`

- [x] 7.7 Register the play router in `oscilla/www.py`: `app.include_router(play_router, tags=["play"])`; note that the play router does not require a prefix because its paths already include `/characters/{id}/play/`

## 8. Overworld Router (`/overworld` and `/navigate` endpoints)

- [x] 8.1 Create `oscilla/routers/overworld.py` with Pydantic models: `NavigateRequest` (location_ref: str with Field description), `AdventureOptionRead` (ref: str, display_name: str, description: str), `LocationOptionRead` (ref: str, display_name: str, is_current: bool), `RegionGraphNode` (id: str, label: str, kind: str), `RegionGraphEdge` (source: str, target: str, label: str), `RegionGraphRead` (nodes: List[RegionGraphNode], edges: List[RegionGraphEdge]), `OverworldStateRead` (character_id: UUID, current_location: str | None, current_location_name: str | None, current_region_name: str | None, available_adventures: List[AdventureOptionRead], navigation_options: List[LocationOptionRead], region_graph: RegionGraphRead)

- [x] 8.2 Implement `GET /characters/{character_id}/overworld`: ownership check; load character state; resolve `current_location_name` and `current_region_name` from registry; build `available_adventures` by listing all `AdventurePoolEntry` items in the current location's `adventures` list and resolving display names from `registry.adventures`; build `navigation_options` by listing all locations in `registry.locations` whose `region` matches the character's current region, marking `is_current` for the active location; build `region_graph` from `oscilla.engine.graph.build_world_graph` scoped to the character's current region using `_filter_to_neighborhood` (already in `graph.py`); return `OverworldStateRead`

- [x] 8.3 Implement `POST /characters/{character_id}/navigate`: ownership check; validate `body.location_ref` exists in `registry.locations` and belongs to an accessible region (location `effective_unlock` condition evaluates to true for the character state); if invalid return 422 with descriptive detail; update `current_location` via `update_scalar_fields`; return `OverworldStateRead` (same as GET /overworld for the new location state)

- [x] 8.4 Register the overworld router in `oscilla/www.py`: `app.include_router(overworld_router, tags=["overworld"])`

## 9. Testing

- [x] 9.1 Create `tests/routers/test_play.py` (add `tests/routers/__init__.py` if it does not exist) with integration tests using `TestClient` and the in-memory SQLite test database fixture: (a) `GET /play/current` returns `PendingStateRead` with empty session_output for a fresh character; (b) `POST /play/begin` with a valid adventure_ref returns SSE events including at least one `narrative` event and a final decision event; (c) `POST /play/begin` with an invalid adventure_ref returns 422; (d) `POST /play/begin` on a locked character returns 409 with `SessionConflictRead`; (e) `POST /play/advance` after a `choice` event returns SSE events continuing the adventure; (f) `POST /play/advance` with no active adventure returns 422; (g) `POST /play/abandon` clears adventure state and returns 204; (h) `POST /play/takeover` acquires the lock and returns `PendingStateRead`; (i) all endpoints return 404 when called with another user's character_id; (j) all endpoints return 401 when called unauthenticated; use the testlandia fixture content with a minimal test adventure that has at least one narrative step followed by a choice step

- [x] 9.2 Create `tests/routers/test_overworld.py`: (a) `GET /overworld` returns `OverworldStateRead` with correct location name for a character with a set `current_location`; (b) `GET /overworld` returns null location fields for a character with no `current_location`; (c) `POST /navigate` with a valid location_ref updates `current_location` and returns the new overworld state; (d) `POST /navigate` with an unknown location_ref returns 422; (e) `POST /navigate` to a locked location (failing `effective_unlock`) returns 422; (f) all endpoints return 404 for another user's character; (g) all endpoints return 401 unauthenticated

- [x] 9.3 Add a crash recovery integration test to `tests/routers/test_play.py`: (a) call `POST /play/begin`, collect all SSE events up to the decision event; (b) without calling advance, call `GET /play/current`; (c) assert `session_output` matches the events from begin, `pending_event` is the final decision event; (d) call `POST /play/advance` with the correct decision and confirm the adventure resumes

- [x] 9.4 Run `make tests` and confirm all checks (pytest, ruff, black, mypy, dapperdata, tomlsort) pass with zero errors

## 10. Documentation

- [x] 10.1 Update `docs/dev/api.md` to add an "Adventure Execution" section documenting all six `/play/` endpoints: request/response schemas, SSE event type contract with field-level documentation for each event type, session locking and takeover flow, the `409 Conflict` response shape, and crash recovery mechanism (`GET /play/current` → `POST /play/advance`)

- [x] 10.2 Update `docs/dev/api.md` to add an "Overworld" section documenting `GET /overworld` and `POST /navigate`: `OverworldStateRead` schema, `RegionGraphRead` structure and intended use, `navigation_options` filtering, unlock condition enforcement

- [x] 10.3 Update `docs/dev/game-engine.md` to add a "Web Execution Path" section covering: `UICallbacks` protocol (replacing `TUICallbacks`), `WebCallbacks` dual-mode behavior (pause vs. resume), `DecisionPauseException` as a first-class control flow mechanism, the `asyncio.Queue` producer-consumer pattern, and the `_run_pipeline_and_stream` generator lifecycle

## 11. Testlandia Content

The adventure execution API requires at least one testlandia location with SSE-verifiable adventures. The goal is comprehensive manual QA coverage: a developer should be able to exercise every SSE event type, test crash recovery, test lock conflict, and navigate between locations.

- [x] 11.1 Create `content/testlandia/regions/api-test/api-test.yaml` — a new `Region` manifest with `displayName: "API Test Area"` and `description: "Minimal region for testing the web adventure execution API."` with no parent or unlock conditions

- [x] 11.2 Create `content/testlandia/regions/api-test/locations/api-hub/api-hub.yaml` — a `Location` manifest with `displayName: "API Hub"`, `region: api-test`, and an `adventures` pool containing exactly three adventures: `api-sse-events` (weight 1), `api-crash-recovery` (weight 1), `api-skill-menu` (weight 1)

- [x] 11.3 Create `content/testlandia/regions/api-test/locations/api-secondary/api-secondary.yaml` — a second `Location` manifest with `displayName: "API Secondary Location"` and `region: api-test`; no adventures; this location exists to allow navigation testing between two locations in the same region

- [x] 11.4 Create `content/testlandia/regions/api-test/locations/api-hub/adventures/api-sse-events.yaml` — a linear adventure that exercises all non-decision SSE event types in sequence: one `narrative` step (produces `narrative` event), one `combat` step against a weak enemy (produces `combat_state` events and `ack_required` at end), one `choice` step with two options (produces `choice` event); expected outcome: developer can verify all three SSE types appear in order by calling `POST /play/begin` and reading the stream

- [x] 11.5 Create `content/testlandia/regions/api-test/locations/api-hub/adventures/api-crash-recovery.yaml` — a two-step adventure: step 0 is a `narrative` step (auto-advances), step 1 is a `choice` step with two outcomes; design is intentionally simple so a developer can: (a) call `POST /play/begin`, see events stream; (b) call `GET /play/current` and confirm session output matches; (c) call `POST /play/advance` with choice=1 and see the adventure complete; this validates the complete crash-recovery loop

- [x] 11.6 Create `content/testlandia/regions/api-test/locations/api-hub/adventures/api-skill-menu.yaml` — a short adventure with a `passive` step that calls `show_skill_menu` to test the `skill_menu` SSE event type; requires the character to have at least one known skill (ensure the adventure grants a test skill via an effect before the passive step, or document that the developer must grant a skill first)

- [x] 11.7 Run `uv run oscilla content validate --game testlandia` to confirm all new manifests validate; run `uv run oscilla content list --game testlandia --kind Location` to confirm `api-hub` and `api-secondary` appear; run `make pytest` to confirm no test regressions
