## ADDED Requirements

### Requirement: POST /characters/{id}/play/begin starts an adventure and streams SSE events

`POST /characters/{id}/play/begin` SHALL be an authenticated endpoint that accepts `BeginAdventureRequest` and returns a `StreamingResponse` with `Content-Type: text/event-stream`.

`BeginAdventureRequest` SHALL contain:

- `adventure_ref: str` — the manifest ref of the adventure to start

The endpoint SHALL:

1. Enforce character ownership (return HTTP 404 for unowned characters).
2. Attempt to acquire a web session lock; return HTTP 409 with `SessionConflictRead` if a live session exists.
3. Validate `adventure_ref` exists in the loaded registry; return HTTP 422 if not found.
4. Clear any existing session output for the iteration.
5. Construct a `WebCallbacks` instance and an `AdventurePipeline`.
6. Return the SSE stream via `_run_pipeline_and_stream`.

The response SHALL include headers: `Cache-Control: no-cache`, `X-Accel-Buffering: no`.

#### Scenario: Streams narrative and decision events for a valid adventure

- **WHEN** an authenticated owner calls `POST /play/begin` with a valid adventure_ref
- **THEN** the response is `200 OK` with `Content-Type: text/event-stream`
- **AND** the stream contains at least one `narrative` event followed by a decision event

#### Scenario: Returns 422 for an unknown adventure_ref

- **WHEN** `POST /play/begin` is called with `{"adventure_ref": "nonexistent"}`
- **THEN** the response has HTTP 422

#### Scenario: Returns 404 for an unowned character

- **WHEN** user B calls `POST /play/begin` on a character owned by user A
- **THEN** the response has HTTP 404

#### Scenario: Returns 401 when unauthenticated

- **WHEN** `POST /play/begin` is called without a Bearer token
- **THEN** the response has HTTP 401

---

### Requirement: POST /characters/{id}/play/advance resumes from a decision point

`POST /characters/{id}/play/advance` SHALL be an authenticated endpoint accepting `AdvanceRequest` and returning a `StreamingResponse` with `Content-Type: text/event-stream`.

`AdvanceRequest` SHALL contain all optional decision fields:

- `choice: int | None` — 1-based menu choice (for `choice` events)
- `ack: bool | None` — acknowledgement (for `ack_required` events)
- `text_input: str | None` — text response (for `text_input` events)
- `skill_choice: int | None` — 1-based skill selection (for `skill_menu` events)

The endpoint SHALL return HTTP 422 if no active adventure exists on the iteration. It SHALL construct `WebCallbacks` with the provided decision pre-loaded and re-run the pipeline from the persisted `adventure_step_index`.

#### Scenario: Resumes a paused adventure with a valid choice

- **WHEN** an adventure is paused at a `choice` event and the owner calls `POST /play/advance` with `{"choice": 1}`
- **THEN** the stream contains subsequent events continuing the adventure from the chosen branch

#### Scenario: Returns 422 when no active adventure exists

- **WHEN** `POST /play/advance` is called on a character with no active adventure
- **THEN** the response has HTTP 422

---

### Requirement: POST /characters/{id}/play/abandon exits the current adventure

`POST /characters/{id}/play/abandon` SHALL be an authenticated endpoint that clears the active adventure, clears all session output, releases the web session lock, and returns HTTP 204.

#### Scenario: Clears adventure state and returns 204

- **WHEN** an owner calls `POST /play/abandon` during an active adventure
- **THEN** the response has HTTP 204
- **AND** subsequent `GET /play/current` returns empty `session_output` and null `pending_event`
- **AND** subsequent `GET /characters/{id}` has null `active_adventure`

---

### Requirement: SSE event type contract is locked

All SSE events emitted by the adventure execution endpoints SHALL conform to the following type contract. All events carry a `context` object:

```
event: narrative
data: {"text": "...", "context": {"location_ref": ..., "location_name": ..., "region_name": ...}}

event: ack_required
data: {"context": {...}}

event: choice
data: {"prompt": "...", "options": ["...", "..."], "context": {...}}

event: combat_state
data: {"player_hp": ..., "enemy_hp": ..., "player_name": "...", "enemy_name": "...", "context": {...}}

event: text_input
data: {"prompt": "...", "context": {...}}

event: skill_menu
data: {"skills": [{"ref": "...", "name": "...", "description": "..."}], "context": {...}}

event: adventure_complete
data: {"outcome": "...", "context": {...}}

event: error
data: {"message": "An unexpected error occurred. Please try again."}
```

The event type set SHALL only be extended — never reduced — for the lifetime of the platform.

#### Scenario: combat_state event contains only the fields available from show_combat_round

- **GIVEN** a combat step is running
- **WHEN** the SSE stream is produced
- **THEN** each `combat_state` event contains `player_hp`, `enemy_hp`, `player_name`, `enemy_name`, and `context` — and does NOT contain `player_max_hp`, `enemy_max_hp`, or `round`

---

### Requirement: WebCallbacks implements UICallbacks with dual pause-or-resume behavior

`WebCallbacks` SHALL implement the `UICallbacks` protocol. Each decision method (`show_menu`, `wait_for_ack`, `input_text`, `show_skill_menu`) SHALL operate in one of two modes:

- **Pause mode** (default, initial request): emit the corresponding SSE event onto the queue, append to `session_output`, put the sentinel `None`, and raise `DecisionPauseException`.
- **Resume mode** (advance request): when the corresponding pre-loaded decision input is set on the `WebCallbacks` instance, return the value immediately without putting any event or raising.

Non-decision methods (`show_text`, `show_combat_round`) SHALL always emit their event and yield to the event loop via `await asyncio.sleep(0)`.

#### Scenario: show_menu in pause mode emits choice event and raises

- **WHEN** `show_menu` is called on a fresh `WebCallbacks` (no pre-loaded choice)
- **THEN** a `choice` event is on the queue, sentinel `None` follows, and `DecisionPauseException` is raised

#### Scenario: show_menu in resume mode returns without pausing

- **WHEN** `show_menu` is called with `player_choice=2` set on construction
- **THEN** the integer `2` is returned, no event is put on the queue, and no exception is raised
