# Design: MU3 — Adventure Execution API

## Context

The adventure pipeline (`AdventurePipeline`) in `oscilla/engine/pipeline.py` is a coroutine that drives an ordered sequence of step handlers. It currently depends on the `TUICallbacks` protocol — the interface through which the pipeline produces player-facing output and receives player decisions. The only existing implementation is `TextualTUI`, which is wired to the terminal.

This change introduces the second implementation of this interface: `WebCallbacks`, which buffers output as Server-Sent Events and suspends the pipeline at each decision point. The SSE stream is closed after each batch of narrative output; the next HTTP request resumes the pipeline from the persisted `adventure_step_index`.

This is the "Run-Until-Decision" model: the pipeline runs until it hits `show_menu`, `wait_for_ack`, `input_text`, or `show_skill_menu`, then it raises an internal `DecisionPauseException` that unwinds the coroutine call stack, terminates the pipeline task, and allows the SSE stream to close cleanly. State is already persisted to the DB via the `on_state_change("step_start", ...)` callback before each step, so the pipeline can be re-created from scratch on the next request.

This change also renames `TUICallbacks` to `UICallbacks` throughout the engine. This is a purely mechanical rename — no method signatures change — but it must happen here, before `WebCallbacks` is introduced, to establish the correct naming in all new code.

---

## Goals / Non-Goals

**Goals:**

- `TUICallbacks` → `UICallbacks` rename across the entire engine (pipeline, step handlers, TUI concrete class, test fixtures).
- `WebCallbacks` — implements `UICallbacks`, emits SSE events via an `asyncio.Queue`, accumulates output to `character_session_output`.
- `character_session_output` — new SQLAlchemy table and Alembic migration.
- `GET /characters/{id}/play/current` — crash recovery endpoint.
- `POST /characters/{id}/play/begin` → SSE `StreamingResponse`.
- `POST /characters/{id}/play/advance` → SSE `StreamingResponse`.
- `POST /characters/{id}/play/abandon` — exits current adventure.
- `POST /characters/{id}/play/takeover` — force-releases stale session lock.
- `POST /characters/{id}/navigate` — location navigation.
- `GET /characters/{id}/overworld` — full overworld state read.
- Web session lock — `session_token` reused; `409 Conflict` includes `acquired_at`.
- SSE event type contract locked: `narrative`, `ack_required`, `choice`, `combat_state`, `text_input`, `skill_menu`, `adventure_complete`, `error`. All events include a `context` field.

**Non-Goals:**

- Frontend UI (MU4/MU5).
- TUI execution path changes beyond the protocol rename — the TUI is functionally unchanged.
- WebSocket transport — SSE is the only transport in this change.

---

## Decisions

### D1: `TUICallbacks` renamed to `UICallbacks`

**Decision:** `oscilla/engine/pipeline.py` renames the `TUICallbacks` Protocol class to `UICallbacks`. All type hint references across the engine are updated. `TextualTUI` (the existing terminal implementation) is updated to implement `UICallbacks`. Test fixtures in `tests/engine/conftest.py` are updated.

This is a find-and-replace. Files affected:

- `oscilla/engine/pipeline.py` — Protocol class definition and `AdventurePipeline.__init__` type hint
- `oscilla/engine/steps/*.py` — any step handler that type-hints `TUICallbacks`
- `oscilla/engine/tui.py` — `TextualTUI` doc/comment references
- `tests/engine/conftest.py` — `MockTUI` type hint

No method signatures change. The rename is mechanical and verified by running `make mypy_check` after.

---

### D2: `DecisionPauseException` unwinds the pipeline at decision points

**Decision:** A new internal exception `DecisionPauseException` is raised by `WebCallbacks` at every method that requires player input (`show_menu`, `wait_for_ack`, `input_text`, `show_skill_menu`). Before raising, the method puts the corresponding SSE event on the queue and then puts a sentinel `None` to signal the SSE consumer that the stream should close.

```python
class DecisionPauseException(Exception):
    """Raised by WebCallbacks to unwind the pipeline at a decision point.

    This is not an error — it is the normal shutdown mechanism for a web
    session after narrative output has been streamed and the next player
    decision has been emitted as an SSE event.
    """
    pass
```

The pipeline task (run as `asyncio.create_task`) completes with this exception. The SSE generator's `finally` block catches and silences it:

```python
# In the SSE generator
try:
    await pipeline_task
except DecisionPauseException:
    pass  # Expected — pipeline paused at a decision point
```

State persistence is guaranteed because `on_state_change("step_start")` fires before each step, and `on_state_change("combat_round")` fires after each combat round. By the time `show_menu` or `wait_for_ack` is called, the correct `adventure_step_index` and `adventure_step_state` are already committed.

**Why an exception is the right mechanism here:**

The pipeline is a deeply-nested async coroutine. Step handlers call `show_menu()` and `wait_for_ack()` as ordinary `await` expressions — they expect to receive the player's decision as a return value before continuing. In the TUI this works because the terminal blocks until the player presses a key. In the web model it cannot work that way: the player's decision arrives in a _separate HTTP request_ minutes or hours later. There is no mechanism in Python to suspend a coroutine mid-execution, persist it across process boundaries, and resume it from another request — without either keeping the coroutine alive in memory (infeasible across requests) or serializing it (unreliable, see alternatives below).

Given that the coroutine cannot be preserved, it must be terminated. The only question is how to terminate it cleanly from inside a deeply-nested call stack. The options are:

1. **An exception that unwinds the stack** — what this design does. The callback raises; the stack unwinds naturally; the task completes. The SSE generator, which owns the `create_task`, catches the exception in its `finally` block. This is the same pattern Python uses for `StopIteration` (generator termination) and `asyncio.CancelledError` (coroutine cancellation) — exceptions as a first-class mechanism for controlled early exit from a call stack.

2. **Return-value propagation** — callbacks return a `PauseSignal` sentinel instead of raising. Every step handler that calls a callback must inspect the return value and propagate the sentinel upward. Every layer of the pipeline between the callback call site and the task root must participate. This is structurally equivalent to the exception approach — the stack still unwinds — but requires every intermediate call site to be aware of the pause concept. Missing one propagation point silently breaks the mechanism without raising an error.

The exception approach is strictly safer: an unhandled `DecisionPauseException` propagates to the task boundary by default. A missed sentinel return check silently continues execution with a garbage value.

**Alternatives considered:**

- **`asyncio.Event` suspension** — pipeline calls `await resume_event.wait()`; the next `POST /play/advance` request sets the event. Requires the coroutine to remain alive in memory between the two HTTP requests. Without sticky session routing (requests from the same player always go to the same server process) or coroutine serialization, this is not viable. Even with sticky routing it leaks memory for abandoned sessions and makes horizontal scaling fragile.

- **Coroutine serialization** — pickle the suspended coroutine to the DB or Redis between requests and restore it on advance. Python coroutines are not reliably serializable with the standard library; `cloudpickle` can do it but behavior is version-sensitive and breaks on any closure over non-serializable objects. Deserializing arbitrary pickled objects is also a security risk (arbitrary code execution). Rejected on reliability and security grounds.

- **Full state-machine refactor** — eliminate the coroutine model; each step returns a `StepResult` that encodes what to do next, all state is explicit, and the pipeline can be re-entered from any point with no coroutine needed. This is architecturally clean but requires rewriting the entire engine, breaking the TUI path, and coordinating with every step handler author. Deferred as a possible future architecture; not viable within MU3 scope.

---

### D3: `WebCallbacks` uses `asyncio.Queue` for producer-consumer SSE streaming

**Decision:** `WebCallbacks` holds an `asyncio.Queue[dict | None]`. Each output method puts a serializable event dict. The sentinel `None` signals end-of-stream. The pipeline task and the SSE generator run concurrently via `asyncio.create_task`.

```python
from asyncio import Queue, create_task, sleep
from typing import Any, Dict, List

class WebCallbacks:
    """UICallbacks implementation for the web execution path.

    Emits SSE events via an asyncio Queue and accumulates session output
    records for crash recovery.
    """

    def __init__(
        self,
        location_ref: str | None,
        location_name: str | None,
        region_name: str | None,
        # Pre-loaded player decisions for resume requests. On an advance request the
        # pipeline re-runs from adventure_step_index, reaching the same decision point
        # that paused the previous run. Providing the input here causes the callback to
        # return the value immediately rather than pausing again.
        player_choice: int | None = None,
        player_ack: bool | None = None,
        player_text_input: str | None = None,
        player_skill_choice: int | None = None,
    ) -> None:
        self._queue: Queue[Dict[str, Any] | None] = Queue()
        self._session_output: List[Dict[str, Any]] = []
        self._context = {
            "location_ref": location_ref,
            "location_name": location_name,
            "region_name": region_name,
        }
        self._player_choice = player_choice
        self._player_ack = player_ack
        self._player_text_input = player_text_input
        self._player_skill_choice = player_skill_choice

    async def show_text(self, text: str) -> None:
        event = {"type": "narrative", "data": {"text": text, "context": self._context}}
        await self._queue.put(event)
        self._session_output.append(event)
        await sleep(0)  # yield to SSE consumer

    async def show_menu(self, prompt: str, options: List[str]) -> int:
        if self._player_choice is not None:
            # Resume request — return the pre-loaded choice and do not pause.
            choice = self._player_choice
            self._player_choice = None
            return choice
        event = {"type": "choice", "data": {"prompt": prompt, "options": options, "context": self._context}}
        await self._queue.put(event)
        self._session_output.append(event)
        await self._queue.put(None)  # sentinel
        raise DecisionPauseException

    async def show_combat_round(
        self,
        player_hp: int,
        enemy_hp: int,
        player_name: str,
        enemy_name: str,
    ) -> None:
        event = {
            "type": "combat_state",
            "data": {
                "player_hp": player_hp,
                "enemy_hp": enemy_hp,
                "player_name": player_name,
                "enemy_name": enemy_name,
                "context": self._context,
            },
        }
        await self._queue.put(event)
        self._session_output.append(event)
        await sleep(0)

    async def wait_for_ack(self) -> None:
        if self._player_ack is not None:
            # Resume request — consume the ack and do not pause.
            self._player_ack = None
            return
        event = {"type": "ack_required", "data": {"context": self._context}}
        await self._queue.put(event)
        self._session_output.append(event)
        await self._queue.put(None)  # sentinel
        raise DecisionPauseException

    async def input_text(self, prompt: str) -> str:
        if self._player_text_input is not None:
            # Resume request — return the pre-loaded text and do not pause.
            value = self._player_text_input
            self._player_text_input = None
            return value
        event = {"type": "text_input", "data": {"prompt": prompt, "context": self._context}}
        await self._queue.put(event)
        self._session_output.append(event)
        await self._queue.put(None)  # sentinel
        raise DecisionPauseException

    async def show_skill_menu(self, skills: List[Dict[str, Any]]) -> int | None:
        if self._player_skill_choice is not None:
            # Resume request — return the pre-loaded skill choice and do not pause.
            choice = self._player_skill_choice
            self._player_skill_choice = None
            return choice
        event = {"type": "skill_menu", "data": {"skills": skills, "context": self._context}}
        await self._queue.put(event)
        self._session_output.append(event)
        await self._queue.put(None)  # sentinel
        raise DecisionPauseException

    @property
    def session_output(self) -> List[Dict[str, Any]]:
        return self._session_output
```

`await sleep(0)` after each `show_text` and `show_combat_round` yields control to the event loop, allowing the SSE generator to send the event before the pipeline continues to the next step. Without this yield, all events would be batched and sent at once when the pipeline finally suspends.

---

### D4: SSE endpoint uses `asyncio.create_task` for pipeline concurrency

**Decision:** The FastAPI SSE endpoint creates a pipeline task and an async generator that drains the queue:

```python
import asyncio
import json
from fastapi.responses import StreamingResponse

async def _run_pipeline_and_stream(
    pipeline: AdventurePipeline,
    web_cb: WebCallbacks,
    session: AsyncSession,
    iteration: CharacterIterationRecord,
) -> AsyncIterator[str]:
    """Async generator that runs the pipeline and yields SSE-formatted strings."""
    pipeline_task = asyncio.create_task(pipeline.run())
    try:
        while True:
            event = await web_cb.queue.get()
            if event is None:
                break
            yield f"event: {event['type']}\ndata: {json.dumps(event['data'])}\n\n"
    finally:
        if not pipeline_task.done():
            pipeline_task.cancel()
        try:
            await pipeline_task
        except (asyncio.CancelledError, DecisionPauseException):
            pass
        except Exception:
            logger.exception("Pipeline task raised an unexpected exception.")
    # Persist session output to DB after stream closes
    await _persist_session_output(session, iteration.id, web_cb.session_output)

@router.post("/characters/{id}/play/begin")
async def begin_adventure(
    id: UUID,
    body: BeginAdventureRequest,
    current_user: Annotated[UserRecord, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    request: Request,
) -> StreamingResponse:
    # Ownership check, lock acquisition, pipeline construction omitted for brevity
    return StreamingResponse(
        _run_pipeline_and_stream(pipeline, web_cb, session, iteration),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
```

`X-Accel-Buffering: no` disables nginx response buffering, which would otherwise hold SSE events in a buffer before sending them to the browser, breaking the streaming effect.

---

### D5: Session lock reuses `session_token` column

**Decision:** `CharacterIterationRecord.session_token` (already exists, used by the TUI crash-recovery path) is repurposed for web session locking. When a web session acquires the lock, it writes a new `UUID` to `session_token` and the current UTC timestamp to `session_token_acquired_at` (a new nullable `DateTime` column added by migration).

The existing TUI `acquire_session_lock` and `release_session_lock` functions in `oscilla/services/character.py` are **unchanged** — they continue to use the always-succeeds steal behavior for offline TUI sessions. Three new web-specific service functions are added:

- `acquire_web_session_lock(session, iteration_id, token, stale_threshold_minutes) -> datetime | None` — returns `None` on success, or `acquired_at` datetime if a live session exists (caller returns 409).
- `release_web_session_lock(session, iteration_id, token) -> None` — clears `session_token` and `session_token_acquired_at`; no-op if token does not match.
- `force_acquire_web_session_lock(session, iteration_id, token) -> None` — always acquires, logging the takeover; clears orphaned adventure state.

A stale lock is defined as: `session_token` is not null, `session_token_acquired_at` is more than `stale_session_threshold_minutes` (default 10, configurable) in the past. The `409 Conflict` response includes:

```python
class SessionConflictRead(BaseModel):
    detail: str
    acquired_at: datetime
    character_id: UUID
```

This allows the frontend to display "Session active since X — take over?" without additional requests.

`POST /characters/{id}/play/takeover`:

1. Verifies the requesting user owns the character.
2. Calls `force_acquire_web_session_lock(...)`, which logs the takeover, clears orphaned adventure state, writes the new token and timestamp.
3. Returns `PendingStateRead` (same shape as `GET /characters/{id}/play/current`) so the frontend can resume without a second round-trip.

**Note:** `session_token_acquired_at` is a new column. The migration adds it as nullable; existing rows with non-null `session_token` will have `null` for `acquired_at`, which means any existing lock is invisible to the stale-lock check — a conservative and safe failure mode (the lock appears perpetual until the takeover endpoint is used).

---

### D6: `character_session_output` table scoped to iteration

**Decision:** Session output rows are keyed by `iteration_id` (not `character_id`) because prestige creates a new iteration. If a player prestiges, the old session output is automatically orphaned and does not appear in the new character sheet.

Rows are cleared on adventure completion (`adventure_complete` event) and on `POST /play/abandon`. The `GET /play/current` endpoint returns these rows in `position` order as the session output log.

The `content_json` column uses `JSON` type (consistent with `adventure_step_state`). This is one of the rare justified uses of JSON — the event schema is defined by the SSE event type contract and cannot be normalized into fixed columns.

---

## Data Model Changes

### `oscilla/models/character_session_output.py` (new)

```python
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from oscilla.models.base import Base


class CharacterSessionOutputRecord(Base):
    """Persists SSE events produced during the current adventure session.

    Used to restore the narrative log on browser refresh or reconnect.
    Rows are cleared when the adventure completes or is abandoned.
    """

    __tablename__ = "character_session_output"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    iteration_id: Mapped[UUID] = mapped_column(
        ForeignKey("character_iterations.id"), nullable=False, index=True
    )
    # Monotone ordering within a session; starts at 0 per adventure begin
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    content_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(tz=timezone.utc),
    )
```

### `oscilla/models/character_iteration.py` (update)

Add `session_token_acquired_at` column:

```python
session_token_acquired_at: Mapped[datetime | None] = mapped_column(
    DateTime(timezone=True), nullable=True
)
```

---

## API Endpoints

All endpoints under `/characters/{id}/play/` and `/characters/{id}/` require `get_current_user`. Ownership enforcement: raises `404` if the character does not belong to the authenticated user.

### Pydantic Models

```python
class BeginAdventureRequest(BaseModel):
    adventure_ref: str = Field(description="Adventure manifest ref to begin.")

class AdvanceRequest(BaseModel):
    choice: int | None = Field(default=None, ge=1, description="1-based choice index.")
    ack: bool | None = Field(default=None, description="Acknowledgement for ack_required events.")
    text_input: str | None = Field(default=None, description="Text response for text_input events.")
    skill_choice: int | None = Field(default=None, ge=1, description="1-based skill menu choice.")

class NavigateRequest(BaseModel):
    location_ref: str = Field(description="Destination location ref.")

class PendingStateRead(BaseModel):
    character_id: UUID
    pending_event: Dict[str, Any] | None  # The last SSE event (choice/ack_required/etc.)
    session_output: List[Dict[str, Any]]  # Ordered SSE events for the current session

class OverworldStateRead(BaseModel):
    character_id: UUID
    current_location: str | None
    current_location_name: str | None
    current_region_name: str | None
    available_adventures: List[AdventureOptionRead]
    navigation_options: List[LocationOptionRead]
    region_graph: RegionGraphRead  # nodes + edges for future map rendering
```

### Endpoint Table

| Method | Path                             | Response             | Notes                |
| ------ | -------------------------------- | -------------------- | -------------------- |
| `GET`  | `/characters/{id}/play/current`  | `PendingStateRead`   | Crash recovery       |
| `POST` | `/characters/{id}/play/begin`    | `text/event-stream`  | Starts adventure     |
| `POST` | `/characters/{id}/play/advance`  | `text/event-stream`  | Submits decision     |
| `POST` | `/characters/{id}/play/abandon`  | `204`                | Exits adventure      |
| `POST` | `/characters/{id}/play/takeover` | `PendingStateRead`   | Force-acquires lock  |
| `POST` | `/characters/{id}/navigate`      | `OverworldStateRead` | Location navigation  |
| `GET`  | `/characters/{id}/overworld`     | `OverworldStateRead` | Overworld state read |

---

## SSE Event Contract

All events carry `context: {location_ref, location_name, region_name}`.

```
event: narrative
data: {"text": "You push open the iron door.", "context": {...}}

event: ack_required
data: {"context": {...}}

event: choice
data: {"prompt": "What do you do?", "options": ["Fight", "Flee"], "context": {...}}

event: combat_state
data: {"player_hp": 42, "enemy_hp": 18,
       "player_name": "Aldric", "enemy_name": "Goblin Chieftain", "context": {...}}

event: text_input
data: {"prompt": "What is your name?", "context": {...}}

event: skill_menu
data: {"skills": [{"ref": "...", "name": "...", "description": "..."}], "context": {...}}

event: adventure_complete
data: {"outcome": "victory", "context": {...}}

event: error
data: {"message": "An unexpected error occurred. Please try again."}
```

SSE responses include HTTP headers: `Content-Type: text/event-stream`, `Cache-Control: no-cache`, `X-Accel-Buffering: no`.

---

## Migrations

Two Alembic migrations:

1. **`character_session_output` table** — new table creation; fully additive.
2. **`CharacterIterationRecord.session_token_acquired_at`** — add nullable `DateTime` column; fully additive.

Both compatible with SQLite and PostgreSQL.

---

## Testing Philosophy

- **Unit tests** for `WebCallbacks`: verify each method puts the correct event dict on the queue; verify `DecisionPauseException` is raised at each decision method; verify sentinel `None` is added before the exception.
- **Unit tests** for `UICallbacks` rename: mypy passes; no `TUICallbacks` references remain outside test fixtures that explicitly test for backward compatibility.
- **Integration tests** for each SSE endpoint using FastAPI `TestClient` (sync client with `stream=True` for SSE) and in-memory SQLite DB.
  - `begin_adventure`: returns SSE events; pipeline advances; session output written.
  - `advance`: resumes from persisted step_index; emits correct events.
  - `abandon`: clears adventure state; session output cleared.
  - `takeover`: stale lock cleared; new lock acquired; returns PendingStateRead.
  - Ownership enforcement: 404 for another user's character.
- **Integration tests** for overworld endpoints: `GET /overworld` returns correct location, adventures, navigation; `POST /navigate` updates location.
- **Crash recovery test**: simulate mid-adventure page refresh — `GET /play/current` returns session_output and pending_event; advancing from that state continues correctly.
- All fixture content uses minimal in-process `ContentRegistry` — no reference to `content/` directory.
- `mock_tui` fixture is used in all pipeline tests; `WebCallbacks` is tested separately.

---

## Documentation Plan

| Document                           | Audience   | Content                                                                                                                                                      |
| ---------------------------------- | ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `docs/dev/api.md` (update)         | Developers | Adventure execution endpoints; SSE event type contract with field-level docs; session locking and takeover flow; crash recovery mechanism                    |
| `docs/dev/game-engine.md` (update) | Developers | `UICallbacks` protocol (replacing `TUICallbacks`); `WebCallbacks` implementation; `DecisionPauseException` mechanics; pipeline task lifecycle in web context |

---

## Risks / Trade-offs

| Risk                                                                                                                                                                                               | Mitigation                                                                                                                                                                                                                                  |
| -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `asyncio.create_task` + `StreamingResponse` — task may outlive the HTTP connection if the client disconnects                                                                                       | `finally` block in the generator cancels the task; FastAPI calls `aclose()` on the generator when the connection closes                                                                                                                     |
| `await sleep(0)` starvation — if the pipeline emits many events rapidly, the SSE consumer may not drain fast enough and queue grows large                                                          | Bounded queue (`maxsize=100`) can be added; pipeline task backs up naturally via `await queue.put()` blocking semantics                                                                                                                     |
| `input_text` response value — `WebCallbacks.input_text` raises `DecisionPauseException` and never returns a value; the pipeline step that calls it will never get a response in the current design | The next `POST /play/advance` carries `text_input` in the request body; on resume, the pipeline is re-run from `step_index` which re-calls `input_text`; `WebCallbacks` on the resume request returns the provided value instead of raising |
| `/play/takeover` abused as a multi-tab coordinator                                                                                                                                                 | Takeover is restricted to the character's owner and logs the event; rate limiting (MU6) will add additional friction                                                                                                                        |
| Session output rows accumulate if a player never completes an adventure                                                                                                                            | Rows are cleared on abandon; a future cleanup job can purge rows older than N days per uncompleted adventure                                                                                                                                |
