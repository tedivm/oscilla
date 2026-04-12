## ADDED Requirements

### Requirement: SSE events are persisted to character_session_output during a session

All SSE events emitted by `WebCallbacks` during an adventure session SHALL be accumulated and persisted to the `character_session_output` table after the SSE stream closes. Rows are keyed by `iteration_id` and ordered by `position` (0-based integer). The full event dict is stored in `content_json`.

Rows are cleared:

- On `POST /play/begin` before the new adventure starts (replacing the previous session's output).
- On `POST /play/abandon`.

A server process crash between events does NOT cause data loss for events already committed.

#### Scenario: Session output is written after stream closes

- **WHEN** `POST /play/begin` completes and the SSE stream closes
- **THEN** `character_session_output` contains one row per emitted event for the iteration, ordered by `position`

#### Scenario: Session output is cleared on new begin

- **WHEN** `POST /play/begin` is called a second time on the same character
- **THEN** session output from the previous session is deleted before the new stream starts

---

### Requirement: GET /characters/{id}/play/current returns pending state for crash recovery

`GET /characters/{id}/play/current` SHALL be an authenticated endpoint that returns `PendingStateRead` (HTTP 200). The endpoint SHALL return HTTP 404 for unowned characters.

`PendingStateRead` SHALL contain:

- `character_id: UUID`
- `session_output: List[Dict[str, Any]]` — all persisted session events in `position` order
- `pending_event: Dict[str, Any] | None` — the last event in `session_output` if its type is one of `choice`, `ack_required`, `text_input`, or `skill_menu`; otherwise `None`

This endpoint is the crash-recovery entry point: after a browser refresh, the frontend calls it to determine whether an adventure is in progress and what decision is awaiting input.

#### Scenario: Returns session_output and pending_event for an in-progress adventure

- **GIVEN** an adventure was started and paused at a `choice` event
- **WHEN** `GET /play/current` is called
- **THEN** `session_output` contains all events up to and including the `choice` event
- **AND** `pending_event` is the `choice` event

#### Scenario: Returns empty session_output and null pending_event for a fresh character

- **GIVEN** a character with no active session output
- **WHEN** `GET /play/current` is called
- **THEN** `session_output` is `[]` and `pending_event` is `null`

#### Scenario: Returns 404 for an unowned character

- **GIVEN** character `{id}` belongs to user B
- **WHEN** user A calls `GET /play/current`
- **THEN** the response has HTTP 404

---

### Requirement: POST /play/advance correctly resumes from persisted step_index

When `POST /play/advance` is called, the pipeline SHALL be re-constructed from scratch using the persisted `adventure_step_index` and `adventure_step_state`. `WebCallbacks` SHALL be initialized with the pre-loaded decision input from the request body. When the pipeline re-runs from the step index and calls the same decision method that paused the previous run, `WebCallbacks` SHALL return the pre-loaded value (resume mode) instead of pausing again.

#### Scenario: Advance resumes correctly after GET /play/current

- **GIVEN** an adventure paused at a `choice` event (step_index N)
- **WHEN** `POST /play/advance` is called with `{"choice": 1}`
- **THEN** the pipeline re-runs from step N, the choice step returns 1, and the adventure continues to the next decision point or completion
