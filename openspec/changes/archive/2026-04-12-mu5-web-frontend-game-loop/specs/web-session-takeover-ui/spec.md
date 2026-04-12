# Web Session Takeover UI

## Purpose

Specifies the frontend flow for detecting and recovering from stale session locks. When `POST /play/begin` or `/play/advance` returns HTTP 409, the server has an active session lock from another tab or a crashed session. The UI presents a non-blocking modal that shows the lock age and offers a "Take over" action, allowing the player to forcibly acquire the session.

---

## Requirements

### Requirement: 409 response triggers the conflict modal, not an error banner

When `gameSession.begin()` or `gameSession.advance()` catches an `ApiError` with `status === 409`, the play page SHALL set `showConflictModal = true` and populate `conflictAcquiredAt` from the error body's `acquired_at` field. The store SHALL NOT set `mode: "overworld"` or `state.error` on a 409 — the 409 is a soft conflict, not a fatal error. The `ErrorBanner` in the root layout SHALL NOT be triggered.

The backend returns the 409 body as a JSON object conforming to `SessionConflictRead`: `{ detail: string, acquired_at: string (ISO 8601), character_id: string }`.

#### Scenario: 409 on begin shows the conflict modal

- **GIVEN** another session holds the lock acquired 2 minutes ago
- **WHEN** the player clicks "Begin" on an adventure
- **THEN** `fetchSSE` throws `ApiError(status=409)` before the stream begins
- **AND** `showConflictModal` is set to `true`
- **AND** `SessionConflictModal` renders with "Active since 2 minutes ago"
- **AND** `NarrativeLog` and `LoadingSpinner` are NOT shown

#### Scenario: 409 on advance also shows the conflict modal

- **GIVEN** the player submitted a choice and the lock was taken before the server processed it
- **WHEN** `gameSession.advance()` receives a 409
- **THEN** the same conflict modal flow fires
- **AND** the existing `narrativeLog` content is preserved in the store (mode does not change to `"overworld"`)

---

### Requirement: SessionConflictModal is non-blocking

`SessionConflictModal.svelte` SHALL render as an overlay above the overworld or adventure content — NOT as a full-page modal that replaces the underlying screen. This allows the player to see the overworld state while deciding whether to take over. The modal SHALL display the lock age as a human-readable relative time.

#### Scenario: modal overlays overworld content

- **GIVEN** `showConflictModal === true`
- **WHEN** the play page renders
- **THEN** `OverworldView` (or `NarrativeLog`) is visible behind the modal overlay
- **AND** the player can read the overworld state to decide whether to take over

---

### Requirement: Take over calls POST /play/takeover and resumes the session

When the player clicks "Take over this session", the play page SHALL call `apiFetch<PendingStateRead>("POST", "/characters/{id}/play/takeover")`. On success it SHALL close the modal and call `gameSession.init(playState)` with the returned state to restore the adventure from whatever point the previous session left off. On error it SHALL render an `ErrorBanner` inside the modal.

#### Scenario: successful takeover restores adventure state

- **GIVEN** `SessionConflictModal` is open
- **WHEN** the player clicks "Take over this session"
- **THEN** `POST /characters/{id}/play/takeover` is called
- **AND** the modal closes
- **AND** `gameSession.init(playState)` is called with the takeover response
- **AND** the play screen reflects the restored narrative log and pending decision

---

### Requirement: Cancel closes the modal without changing session state

When the player clicks "Cancel", `showConflictModal` SHALL be set to `false` and no API call SHALL be made. The `gameSession` store SHALL remain in whatever mode it was before the conflict was detected.

#### Scenario: cancel returns to overworld without API call

- **GIVEN** `SessionConflictModal` is open and `$gameSession.mode === "overworld"`
- **WHEN** the player clicks "Cancel"
- **THEN** the modal closes
- **AND** `$gameSession.mode` remains `"overworld"`
- **AND** no additional network requests are made
