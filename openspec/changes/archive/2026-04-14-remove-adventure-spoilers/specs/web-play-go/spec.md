# Spec: Web Play Go

## Purpose

Defines the `POST /characters/{id}/play/go` endpoint — the sole adventure-start endpoint on the web API. The player sends a location ref; the engine validates accessibility, evaluates the eligible pool, selects an adventure via weighted random, and streams the result. The frontend never learns which adventure was chosen, how many were eligible, or what any adventure is named.

## Requirements

### Requirement: POST /characters/{id}/play/go selects and begins an adventure

`POST /characters/{id}/play/go` SHALL be an authenticated endpoint that accepts a JSON body `{ "location_ref": "<ref>" }` and returns a `text/event-stream` SSE response (HTTP 200) on success.

The endpoint SHALL:

1. Validate the `location_ref` exists in the registry. Return HTTP 422 if unknown.
2. Load the character's current state. Return HTTP 404 if not found.
3. Validate the location is accessible to this character by evaluating its unlock conditions against the loaded character state. Return HTTP 422 if the conditions fail.
4. Evaluate the eligible adventure pool: for each entry in the location's `adventures` list, evaluate `entry.requires` via the condition evaluator and call `player.is_adventure_eligible(adventure_ref, spec, now_ts)`. An entry is eligible only if both checks pass.
5. If the eligible pool is empty, return HTTP 422.
6. Perform weighted random selection from the eligible pool using `entry.weight` values.
7. Acquire a web session lock. Return HTTP 409 if the lock is held by an active session.
8. Run the selected adventure through the SSE pipeline.

The endpoint SHALL NOT disclose the selected adventure ref, name, description, or pool size in any HTTP response header or body field outside the SSE narrative stream.

There is no other adventure-start endpoint. `POST /play/begin` does not exist.

#### Scenario: begins an adventure at a location with eligible pool entries

- **GIVEN** a location `"test-location"` with at least one eligible adventure exists in the registry
- **WHEN** `POST /play/go` is called with `{ "location_ref": "test-location" }`
- **THEN** the response has HTTP 200 `text/event-stream`
- **AND** the stream contains at least one SSE event

#### Scenario: returns 422 for an unknown location_ref

- **GIVEN** `"nonexistent-location"` is not in the registry
- **WHEN** `POST /play/go` is called with `{ "location_ref": "nonexistent-location" }`
- **THEN** the response has HTTP 422

#### Scenario: returns 422 for a locked location

- **GIVEN** `"test-location-locked"` has an unlock condition the character does not meet
- **WHEN** `POST /play/go` is called with `{ "location_ref": "test-location-locked" }`
- **THEN** the response has HTTP 422

#### Scenario: returns 422 when no adventures are eligible at the location

- **GIVEN** a location `"test-location-empty"` with no adventures in its pool, or all adventures ineligible
- **WHEN** `POST /play/go` is called with `{ "location_ref": "test-location-empty" }`
- **THEN** the response has HTTP 422

#### Scenario: returns 409 when a session lock is already held

- **GIVEN** a live session lock exists for the character
- **WHEN** `POST /play/go` is called
- **THEN** the response has HTTP 409 with a `SessionConflictRead` body

#### Scenario: returns 404 for an unowned character

- **GIVEN** character `{id}` belongs to user B
- **WHEN** user A calls `POST /play/go`
- **THEN** the response has HTTP 404

---

### Requirement: Pool selection uses weighted random consistent with TUI behavior

The eligibility filter and weighted random selection in `POST /play/go` SHALL be identical to the selection logic in `oscilla/engine/tui.py`. Specifically:

- Entries are filtered by `evaluate(entry.requires, player, registry)` AND `player.is_adventure_eligible(adventure_ref, spec, now_ts)`.
- `random.choices(population=eligible, weights=[e.weight for e in eligible], k=1)` determines the winner.
- The `now_ts` value is `int(time.time())` at the time of the request.

#### Scenario: selection respects requires conditions

- **GIVEN** a location with two adventures where adventure A is gated by a condition the character does not meet
- **WHEN** `POST /play/go` is called
- **THEN** only adventure B is eligible; adventure A is never started

#### Scenario: selection respects repeat controls

- **GIVEN** a location where the only pool adventure has `repeatable: false` and the character has already completed it
- **WHEN** `POST /play/go` is called
- **THEN** the response has HTTP 422 (no eligible adventures)
