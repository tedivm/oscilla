# Active Adventure Guard

## Purpose

Specifies the `require_no_active_adventure` FastAPI dependency that prevents state-mutating requests from being processed while a character has a live web session lock. This guards against silent state corruption from concurrent mutations on a character whose engine state is actively being written by the play router.

---

## Requirements

### Requirement: require_no_active_adventure blocks state-mutating requests when a session lock is live

The `require_no_active_adventure` FastAPI dependency SHALL:

1. Accept `character_id: UUID` and a database session as parameters.
2. Load the active `CharacterIterationRecord` for the character.
3. If the record has a non-null `session_token`, raise `HTTPException(status_code=409)` with a structured detail body:

   ```json
   { "code": "active_adventure", "character_id": "<uuid>" }
   ```

4. If the record has `session_token: null` or no active iteration exists, allow the request to proceed.

The dependency SHALL be applied to `PATCH /characters/{id}` only. `DELETE /characters/{id}` SHALL NOT use this dependency — a player may always delete a character they own regardless of adventure state.

The dependency SHALL NOT be applied to any endpoint in the play router. The play router manages session locks directly and must not be blocked by this guard.

The `code: "active_adventure"` field in the structured 409 body allows frontend clients to distinguish this conflict from any other 409 response and redirect the user to the play screen.

#### Scenario: Dependency raises 409 when session_token is set

- **GIVEN** a character whose active iteration has a non-null `session_token`
- **WHEN** the `require_no_active_adventure` dependency is evaluated for that character
- **THEN** an `HTTPException` with status 409 is raised
- **AND** the detail body is `{"code": "active_adventure", "character_id": "<uuid>"}`

#### Scenario: Dependency allows the request when session_token is null

- **GIVEN** a character whose active iteration has `session_token: null`
- **WHEN** the `require_no_active_adventure` dependency is evaluated
- **THEN** no exception is raised and execution continues

#### Scenario: Dependency allows the request when no active iteration exists

- **GIVEN** a character ID with no active iteration record
- **WHEN** the `require_no_active_adventure` dependency is evaluated
- **THEN** no exception is raised and execution continues
