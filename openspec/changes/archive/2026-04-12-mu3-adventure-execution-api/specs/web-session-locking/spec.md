## ADDED Requirements

### Requirement: Web session locking prevents concurrent sessions on the same character

A character SHALL be lockable by at most one web session at a time. When a web session starts (via `POST /play/begin` or `POST /play/takeover`), it writes a unique `session_token` and `session_token_acquired_at` timestamp to the `CharacterIterationRecord`. A second session attempting to lock the same character SHALL receive HTTP 409 if the existing lock is not stale.

A lock is considered **stale** when `session_token_acquired_at` is older than `settings.stale_session_threshold_minutes` (default 10 minutes). A stale lock is silently overwritten. A null `session_token_acquired_at` on an existing lock is treated as perpetual (never stale) — it is only reachable if the lock was written before the column was added.

#### Scenario: First session acquires the lock successfully

- **WHEN** no session lock is held on an iteration and `POST /play/begin` is called
- **THEN** `session_token` and `session_token_acquired_at` are written to the iteration row
- **AND** the SSE stream begins normally

#### Scenario: Second session returns 409 when a live lock exists

- **WHEN** session A holds an unexpired lock and session B calls `POST /play/begin` on the same character
- **THEN** the response has HTTP 409 with a `SessionConflictRead` body containing `acquired_at`

#### Scenario: Stale lock is silently overwritten

- **WHEN** an existing `session_token_acquired_at` is older than `stale_session_threshold_minutes`
- **THEN** the new session acquires the lock without a 409 response

---

### Requirement: POST /characters/{id}/play/takeover force-acquires the session lock

`POST /characters/{id}/play/takeover` SHALL be an authenticated endpoint that unconditionally acquires the session lock for the requested character and returns `PendingStateRead` (HTTP 200).

The endpoint SHALL:

1. Verify the requesting user owns the character (HTTP 404 otherwise).
2. Call `force_acquire_web_session_lock`, which logs the prior token at WARNING level and clears orphaned adventure state (`adventure_ref`, `adventure_step_index`, `adventure_step_state`).
3. Return the current session output and pending event so the frontend can resume without an extra round-trip.

#### Scenario: Takeover succeeds and returns pending state

- **WHEN** a live lock is held and the character's owner calls `POST /play/takeover`
- **THEN** the response has HTTP 200 with `PendingStateRead`
- **AND** the new `session_token` is written and `session_token_acquired_at` is refreshed

#### Scenario: Takeover returns 404 for a non-owner

- **WHEN** user B calls `POST /play/takeover` on user A's character
- **THEN** the response has HTTP 404

---

### Requirement: 409 Conflict response includes lock acquisition timestamp

When `POST /play/begin` returns HTTP 409, the response body SHALL be a `SessionConflictRead` object containing:

- `detail: str` — human-readable explanation
- `acquired_at: datetime` — when the existing lock was acquired
- `character_id: UUID` — the affected character

This allows the frontend to display "Session active since X — take over?" without an additional request.

#### Scenario: 409 body contains acquired_at

- **GIVEN** session A acquired the lock at time T
- **WHEN** session B calls `POST /play/begin` and receives 409
- **THEN** the response body contains `acquired_at` equal to T (within clock precision)

---

### Requirement: Session lock is released on adventure completion and abandonment

The web session lock SHALL be released when:

1. The adventure pipeline emits an `adventure_complete` event (lock released inside `_run_pipeline_and_stream` after stream closes).
2. `POST /play/abandon` is called explicitly.

#### Scenario: Lock is cleared after adventure_complete

- **WHEN** an adventure completes and the SSE stream closes
- **THEN** `session_token` and `session_token_acquired_at` are both null on the iteration row

#### Scenario: Lock is cleared on abandon

- **WHEN** the character owner calls `POST /play/abandon`
- **THEN** `session_token` and `session_token_acquired_at` are both null on the iteration row
